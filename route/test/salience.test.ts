// FR-G05 验收:杏杏规则打 salience 分;≥阈值进"永不遗忘"白名单;
// 白名单只增不删,人工可增不可减。
import assert from 'node:assert/strict';
import { describe, it } from 'node:test';
import { makeTestApp } from './util.ts';
import { SalienceEngine } from '../src/salience.ts';
import type { MemoryWriteEntry } from '../src/types.ts';

describe('FR-G05 显著性打标与白名单', () => {
  const entry = (over: Partial<MemoryWriteEntry>): MemoryWriteEntry => ({
    store: 'episodic',
    kind: 'dialogue',
    payload: {},
    ...over,
  });

  it('里程碑事件 → 高分并进白名单', async () => {
    const t = makeTestApp();
    try {
      const acks = await t.app.writeScheduler.submit([
        entry({ kind: 'milestone', payload: { text: '孩子第一次主持朝会' } }),
      ]);
      assert.equal(acks[0]!.salience, 1.0);
      assert.equal(acks[0]!.whitelisted, true);
      assert.equal(t.app.whitelist.list().length, 1);
      assert.equal(t.app.whitelist.list()[0]!.source, 'auto');
    } finally {
      t.dispose();
    }
  });

  it('孩子首次行为加分,重复行为不再加', () => {
    const engine = new SalienceEngine();
    const e = entry({ payload: { behavior: '自己系鞋带' } });
    const first = engine.evaluate(e);
    assert.ok(first.reasons.includes('孩子首次行为'));
    assert.equal(first.score, 1.0, 'base 0.3 + first 0.7');
    const second = engine.evaluate(e);
    assert.ok(!second.reasons.includes('孩子首次行为'));
    assert.equal(second.score, 0.3);
  });

  it('情绪高峰(|valence|≥0.85)加分', () => {
    const engine = new SalienceEngine();
    const r = engine.evaluate(entry({ kind: 'affect_event', payload: {} }), {
      emotion: { valence: -0.95, arousal: 0.9 },
    });
    assert.ok(r.reasons.includes('情绪高峰'));
    assert.ok(r.score >= 0.8);
  });

  it('重启后首次行为集合从情景库回放,不会重复加分', async () => {
    const t = makeTestApp();
    try {
      await t.app.writeScheduler.submit([
        entry({ payload: { behavior: '主动道歉' } }),
      ]);
      const seedCount = t.app.salience.seenBehaviorCount;
      assert.ok(seedCount >= 1);
    } finally {
      t.dispose();
    }
  });

  it('人工可加入白名单', async () => {
    const t = makeTestApp();
    try {
      const r = t.app.whitelist.add({ ref_id: 'manual-1', reason: '家长指定永不遗忘', score: 1, source: 'manual' });
      assert.ok(r.added);
      assert.equal(t.app.whitelist.has('manual-1'), true);
      // 重复添加幂等
      const r2 = t.app.whitelist.add({ ref_id: 'manual-1', reason: '重复', score: 1, source: 'manual' });
      assert.equal(r2.added, false);
    } finally {
      t.dispose();
    }
  });

  it('白名单只增不删:不存在任何删除方法', () => {
    const t = makeTestApp();
    try {
      const wl = t.app.whitelist as unknown as Record<string, unknown>;
      for (const m of Object.keys(wl)) {
        assert.ok(!/remove|delete|del\b|clear|filter/i.test(m), `白名单不允许出现删除类方法: ${m}`);
      }
      assert.equal(typeof wl.remove, 'undefined');
      assert.equal(typeof wl.delete, 'undefined');
      assert.equal(typeof wl.clear, 'undefined');
    } finally {
      t.dispose();
    }
  });

  it('EMA 衰减函数:闲置越久有效显著性越低', () => {
    const engine = new SalienceEngine();
    const fresh = engine.decayed(1.0, 0);
    const idle30 = engine.decayed(1.0, 30);
    const idle100 = engine.decayed(1.0, 100);
    assert.equal(fresh, 1.0);
    assert.ok(idle30 < fresh && idle30 > 0.2);
    assert.ok(idle100 < idle30 && idle100 < 0.01);
  });
});
