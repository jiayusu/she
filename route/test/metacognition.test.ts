// FR-G07 验收:元认知三 agent(复盘/遗忘剪枝/巩固触发)可观测、可手动触发。
import assert from 'node:assert/strict';
import { describe, it } from 'node:test';
import { makeTestApp } from './util.ts';
import type { StoredMemory } from '../src/salience.ts';

async function seedOldMemory(
  t: ReturnType<typeof makeTestApp>,
  over: Partial<StoredMemory>,
): Promise<void> {
  await t.app.stores.get('episodic').write({
    id: over.id ?? `ep_${Math.random().toString(36).slice(2)}`,
    store: 'episodic',
    minister: 'ahai',
    kind: 'dialogue',
    payload: {},
    salience: 0.3,
    ts: Date.now(),
    last_access: Date.now(),
    ...over,
  });
}

describe('FR-G07 元认知三 agent', () => {
  it('三个任务均已注册,可手动触发且结果可观测', async () => {
    const t = makeTestApp();
    try {
      const names = t.app.jobs.status().map((j) => j.name);
      assert.deepEqual(names.sort(), ['consolidate', 'prune', 'review']);

      const r1 = await t.app.jobs.triggerNow('review');
      assert.ok(r1.ok);
      const r2 = await t.app.jobs.triggerNow('prune');
      assert.ok(r2.ok);
      const r3 = await t.app.jobs.triggerNow('consolidate');
      assert.ok(r3.ok);
      assert.ok(String(r3.summary.report_id).startsWith('cons_'));

      const status = t.app.jobs.status();
      for (const j of status) {
        assert.ok(j.last, `${j.name} 应有最近一次执行结果`);
        assert.ok(j.history.length >= 1);
        assert.ok(j.schedule);
      }
      assert.equal(t.app.jobs.status().find((j) => j.name === 'review')!.last!.ran_at > 0, true);
    } finally {
      t.dispose();
    }
  });

  it('复盘 agent:产出剧情质量报告(意图分布/澄清率/写入成功率)', async () => {
    const t = makeTestApp();
    try {
      await t.app.dispatch({ session_id: 's1', utterance: '我昨天教会小熊什么来着' });
      await t.app.dispatch({ session_id: 's1', utterance: '你好呀' });
      await t.app.dispatch({ session_id: 's1', utterance: '嗯嗯' }); // 低置信 → 澄清

      const r = await t.app.jobs.triggerNow('review');
      assert.ok(r.ok);
      assert.equal(r.summary.dispatches, 3);
      assert.ok((r.summary.intent_distribution as Record<string, number>).memory >= 1);
      assert.ok(Math.abs((r.summary.clarify_rate as number) - 1 / 3) < 1e-9);
      assert.ok((r.summary.memory_write as { success_rate: number }).success_rate === 1);
      assert.ok(['healthy', 'attention'].includes(r.summary.verdict as string));
    } finally {
      t.dispose();
    }
  });

  it('遗忘剪枝:低显著性老记忆被删,新记忆保留,白名单豁免', async () => {
    const t = makeTestApp();
    try {
      const day = 86_400_000;
      await seedOldMemory(t, {
        id: 'old_low',
        salience: 0.3,
        ts: Date.now() - 120 * day,
        last_access: Date.now() - 120 * day,
      }); // 0.3*exp(-6)≈0.0007 → 删
      await seedOldMemory(t, { id: 'fresh', salience: 0.3 }); // 闲置 0 天 → 保留
      await seedOldMemory(t, {
        id: 'old_high',
        salience: 1.0,
        ts: Date.now() - 120 * day,
        last_access: Date.now() - 120 * day,
      });
      t.app.whitelist.add({ ref_id: 'old_high', reason: '里程碑', score: 1, source: 'auto' });
      await seedOldMemory(t, {
        id: 'mid_idle',
        salience: 0.5,
        ts: Date.now() - 30 * day,
        last_access: Date.now() - 30 * day,
      }); // 0.5*exp(-1.5)≈0.112 → 衰减保留

      const r = await t.app.jobs.triggerNow('prune');
      const s = r.summary as unknown as { scanned: number; pruned: number; protected_whitelist: number; decayed: number };
      assert.equal(s.scanned, 4);
      assert.equal(s.pruned, 1);
      assert.equal(s.protected_whitelist, 1);
      assert.equal(s.decayed, 1);

      const episodic = t.app.stores.get('episodic');
      assert.equal(episodic.get('old_low'), null, '低显著性老记忆应被剪枝');
      assert.ok(episodic.get('fresh'), '新记忆保留');
      assert.ok(episodic.get('old_high'), '白名单记忆永不遗忘');
      const mid = episodic.get('mid_idle')!;
      assert.ok(mid.salience < 0.5, '闲置记忆显著性应已衰减');
      assert.ok(mid.salience > 0.05, '未到地板不应删除');
    } finally {
      t.dispose();
    }
  });

  it('巩固触发 agent:每周自动产出 diff 报告(draft,不自动生效)', async () => {
    const t = makeTestApp();
    try {
      const episodic = t.app.stores.get('episodic');
      for (let i = 0; i < 3; i++) {
        await episodic.write({
          id: `ep_樱桃_${i}`,
          store: 'episodic',
          minister: 'ahai',
          kind: 'word_learned',
          payload: { word: '樱桃', eval: 'passed' },
          salience: 0.3,
          ts: Date.now(),
          last_access: Date.now(),
        });
      }
      const r = await t.app.jobs.triggerNow('consolidate');
      assert.ok(r.ok);
      assert.equal(r.summary.status, 'draft');
      assert.equal(r.summary.candidates, 1);
      assert.equal(t.app.kg.hasWord('樱桃'), false, 'draft 不自动写入语义层');
      const confirm = t.app.consolidation.confirm(String(r.summary.report_id));
      assert.equal(confirm.applied, 1);
      assert.equal(t.app.kg.hasWord('樱桃'), true);
    } finally {
      t.dispose();
    }
  });
});
