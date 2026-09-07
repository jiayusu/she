// FR-G06 验收:每周批量将阿海情景记忆中"出现≥3 次且评估通过"的词 → 老颞语义层;
// 产出 diff 报告,人工一键确认后生效。
import assert from 'node:assert/strict';
import { describe, it } from 'node:test';
import { makeTestApp, waitFor } from './util.ts';
import type { StoredMemory } from '../src/salience.ts';

function seedWord(
  store: { write(mem: StoredMemory): Promise<void> },
  word: string,
  count: number,
  evals: Array<'passed' | 'failed'> = [],
): Promise<unknown> {
  const writes: Promise<void>[] = [];
  for (let i = 0; i < count; i++) {
    writes.push(
      store.write({
        id: `ep_${word}_${i}`,
        store: 'episodic',
        minister: 'ahai',
        kind: 'word_learned',
        payload: { word, eval: evals[i] },
        salience: 0.3,
        ts: Date.now() - (count - i) * 3600_000,
        last_access: Date.now(),
      }),
    );
  }
  return Promise.all(writes);
}

describe('FR-G06 巩固触发器', () => {
  it('出现≥3 次且评估通过 → 候选;次数不足/评估未通过 → 拒绝', async () => {
    const t = makeTestApp();
    try {
      const episodic = t.app.stores.get('episodic');
      await seedWord(episodic, '苹果', 3, ['passed', 'passed', 'passed']);
      await seedWord(episodic, '香蕉', 2, ['passed', 'passed']);
      await seedWord(episodic, '梨子', 3, ['passed', 'passed', 'failed']);

      const report = t.app.consolidation.runDraft();
      assert.equal(report.status, 'draft');
      assert.deepEqual(report.candidates.map((c) => c.word), ['苹果']);
      assert.equal(report.candidates[0]!.count, 3);
      assert.ok(!report.candidates.some((c) => c.word === '香蕉'), '2 次 < 3 次不巩固');
      assert.ok(!report.candidates.some((c) => c.word === '梨子'), '评估未全过不巩固');
    } finally {
      t.dispose();
    }
  });

  it('同一周内重复触发复用同一份 draft 报告', async () => {
    const t = makeTestApp();
    try {
      await seedWord(t.app.stores.get('episodic'), '西瓜', 3, ['passed', 'passed', 'passed']);
      const r1 = t.app.consolidation.runDraft();
      await waitFor(5);
      const r2 = t.app.consolidation.runDraft();
      assert.equal(r1.id, r2.id);
    } finally {
      t.dispose();
    }
  });

  it('人工一键确认后,词经热更新接口进老颞语义层', async () => {
    const t = makeTestApp();
    try {
      await seedWord(t.app.stores.get('episodic'), '橘子', 4, ['passed', 'passed', 'passed', 'passed']);
      const report = t.app.consolidation.runDraft();
      assert.equal(t.app.kg.hasWord('橘子'), false);

      const { applied } = t.app.consolidation.confirm(report.id);
      assert.equal(applied, 1);
      assert.equal(t.app.kg.hasWord('橘子'), true);
      assert.equal(t.app.kg.getWord('橘子')!.status, 'confirmed');
      assert.equal(t.app.kg.getWord('橘子')!.examples, 4);
      const counters = t.app.metrics.snapshot().counters;
      assert.ok(counters['consolidate_batch{count=1}'] === 1, '埋点 consolidate_batch(count)');
    } finally {
      t.dispose();
    }
  });

  it('已确认的词下次报告进入 existing(不重复巩固)', async () => {
    const t = makeTestApp();
    try {
      await seedWord(t.app.stores.get('episodic'), '葡萄', 3, ['passed', 'passed', 'passed']);
      const r1 = t.app.consolidation.runDraft();
      t.app.consolidation.confirm(r1.id);

      // 第二周场景:手工让缓存过期 —— 直接补一个新的 draft(不同报告 id)
      await seedWord(t.app.stores.get('episodic'), '柚子', 3, ['passed', 'passed', 'passed']);
      const r2 = t.app.consolidation.runDraft();
      assert.notEqual(r2.id, r1.id, '确认后旧 draft 不再复用,应产出新报告');
      assert.ok(r2.existing.includes('葡萄'), '已巩固词入 existing');
      assert.ok(r2.candidates.some((c) => c.word === '柚子'));
    } finally {
      t.dispose();
    }
  });

  it('无候选词时报告状态为 empty', async () => {
    const t = makeTestApp();
    try {
      const report = t.app.consolidation.runDraft();
      assert.equal(report.status, 'empty');
      assert.equal(report.candidates.length, 0);
    } finally {
      t.dispose();
    }
  });
});
