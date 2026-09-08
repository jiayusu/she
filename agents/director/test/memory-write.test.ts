// FR-G04 验收:按大臣归属分发五库;写失败重试 1 次后入死信队列告警;
// 写入成功率 ≥99.9%;FR-G05 显著性达标入白名单;与 KG 冲突标待审。
import assert from 'node:assert/strict';
import { describe, it } from 'node:test';
import { makeTestApp } from './util.ts';
import type { MemoryWriteEntry } from '../src/types.ts';

describe('FR-G04 记忆写调度', () => {
  it('正常路径:按 store 落库,ack 返回 salience', async () => {
    const t = makeTestApp();
    try {
      const acks = await t.app.writeScheduler.submit([
        { store: 'episodic', kind: 'dialogue', payload: { text: '今天朝会开得很顺利' } },
        { minister: 'laonie', kind: 'fact', payload: { fact: { subject: '小熊', predicate: '喜欢', object: '蜂蜜' } } },
      ]);
      assert.equal(acks.length, 2);
      assert.ok(acks.every((a) => a.ok && a.attempts === 1));
      assert.equal(acks[1]!.store, 'semantic', '从 minister 推导归属库');
      assert.equal(t.app.stores.get('episodic').all().length, 1);
      assert.equal(t.app.stores.get('semantic').all().length, 1);
    } finally {
      t.dispose();
    }
  });

  it('归属校验:store 与 minister 冲突 → 拒绝且不落库', async () => {
    const t = makeTestApp();
    try {
      const acks = await t.app.writeScheduler.submit([
        { store: 'episodic', minister: 'laonie', kind: 'dialogue', payload: {} },
      ]);
      assert.equal(acks[0]!.ok, false);
      assert.match(acks[0]!.error!, /归属不符/);
      assert.equal(t.app.stores.get('episodic').all().length, 0);
    } finally {
      t.dispose();
    }
  });

  it('瞬时失败重试 1 次成功(attempts=2)', async () => {
    const t = makeTestApp();
    try {
      // failEveryNth=2:第 1、3、5…次尝试失败,第 2 次成功
      (t.app.stores.get('episodic') as unknown as { setFault(f: object): void }).setFault({ failEveryNth: 2 });
      const acks = await t.app.writeScheduler.submit([
        { store: 'episodic', kind: 'dialogue', payload: { text: 'x' } },
      ]);
      assert.equal(acks[0]!.ok, true);
      assert.equal(acks[0]!.attempts, 2, '首写失败 + 重试 1 次');
      assert.equal(t.app.stores.get('episodic').all().length, 1);
    } finally {
      t.dispose();
    }
  });

  it('连续失败 → 入死信队列 + 告警事件,可重推恢复', async () => {
    const t = makeTestApp();
    try {
      const alerts: unknown[] = [];
      t.app.bus.on('dlq_alert', (e) => alerts.push(e));
      (t.app.stores.get('episodic') as unknown as { setFault(f: object): void }).setFault({ failEveryNth: 1 });

      const acks = await t.app.writeScheduler.submit([
        { store: 'episodic', kind: 'dialogue', payload: { text: 'x' } },
      ]);
      assert.equal(acks[0]!.ok, false);
      assert.equal(acks[0]!.attempts, 2, '首写 + 重试 1 次后放弃');
      assert.equal(acks[0]!.dead_letter, true);
      assert.equal(t.app.writeScheduler.openDlqCount(), 1);
      assert.equal(alerts.length, 1, '死信必须触发告警');

      // 修复存储后重推
      (t.app.stores.get('episodic') as unknown as { setFault(f: object): void }).setFault({});
      const r = await t.app.writeScheduler.retryDlq();
      assert.equal(r.recovered, 1);
      assert.equal(t.app.writeScheduler.openDlqCount(), 0);
      assert.equal(t.app.stores.get('episodic').all().length, 1);
    } finally {
      t.dispose();
    }
  });

  it('死信当日清零:sweep 重推全部', async () => {
    const t = makeTestApp();
    try {
      (t.app.stores.get('affective') as unknown as { setFault(f: object): void }).setFault({ failEveryNth: 1 });
      await t.app.writeScheduler.submit([
        { store: 'affective', kind: 'affect_event', payload: {} },
        { store: 'affective', kind: 'affect_event', payload: {} },
      ]);
      assert.equal(t.app.writeScheduler.openDlqCount(), 2);
      (t.app.stores.get('affective') as unknown as { setFault(f: object): void }).setFault({});
      const sweep = await t.app.writeScheduler.sweepDlq();
      assert.ok(sweep.cleared);
      assert.equal(sweep.open, 0);
    } finally {
      t.dispose();
    }
  });

  it('写入成功率 ≥99.9%(1% 级瞬时故障 + 重试 1 次,确定性随机源)', async () => {
    const t = makeTestApp();
    try {
      // 尝试级失败率 2%,LCG 固定种子;写级成功率应 ≥99.9%
      let s = 42;
      const rng = (): number => {
        s = (s * 9301 + 49297) % 233280;
        return s / 233280;
      };
      const episodic = t.app.stores.get('episodic');
      (episodic as unknown as { setFault(f: object): void }).setFault({ failureRate: 0.02 });
      (episodic as unknown as { setRng(r: () => number): void }).setRng?.(rng);

      const N = 1000;
      const entries: MemoryWriteEntry[] = Array.from({ length: N }, (_, i) => ({
        store: 'episodic',
        kind: 'dialogue',
        payload: { text: `第${i}句` },
      }));
      const acks = await t.app.writeScheduler.submit(entries);
      const okCount = acks.filter((a) => a.ok).length;
      const rate = okCount / N;
      assert.ok(rate >= 0.999, `写入成功率 ${(rate * 100).toFixed(2)}% < 99.9%(失败 ${N - okCount} 条)`);
      assert.equal(t.app.writeScheduler.openDlqCount(), N - okCount, '失败条目应全部入死信');
    } finally {
      t.dispose();
    }
  });

  it('与 KG 冲突的事实 → 标待审,不直接固化(防幻觉固化)', async () => {
    const t = makeTestApp();
    try {
      t.app.kg.assert({ subject: '小熊', predicate: '最爱吃', object: '蜂蜜', source: 'manual' });
      const acks = await t.app.writeScheduler.submit([
        { store: 'semantic', kind: 'fact', payload: { fact: { subject: '小熊', predicate: '最爱吃', object: '苹果' } } },
      ]);
      assert.equal(acks[0]!.pending_review, true);
      assert.ok(acks[0]!.ok, '待审不算写失败');
      const pending = t.app.kg.listPendingReview();
      assert.equal(pending.length, 1);
      assert.equal(pending[0]!.existing_object, '蜂蜜');
      // 人工审核通过 → 覆盖旧值
      t.app.kg.resolvePendingReview(pending[0]!.id, true);
      assert.equal(t.app.kg.query('小熊')[0]!.object, '苹果');
    } finally {
      t.dispose();
    }
  });
});
