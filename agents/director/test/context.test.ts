// FR-G03 验收:注入包含剧本状态/最近10轮/今日已学词/情绪分;token 预算分级(闲聊500/任务1500);
// 生成延迟 ≤50ms。
import assert from 'node:assert/strict';
import { describe, it } from 'node:test';
import { ContextBuilder } from '../src/context.ts';
import { DEFAULT_BUDGETS } from '../src/config.ts';
import type { SessionState } from '../src/session.ts';

function bigSession(turnCount: number, textLen = 100): SessionState {
  return {
    session_id: 's1',
    minister_on_duty: 'xiaop',
    script_state: { plot: '朝会', scene: '金銮殿', role: '小皇上', act: 3 },
    turns: Array.from({ length: turnCount }, (_, i) => ({
      ts: 1_700_000_000_000 + i * 1000,
      role: i % 2 === 0 ? 'child' : 'minister',
      minister: 'xiaop',
      text: '这是一段比较长的对话内容'.repeat(textLen) + `#${i}`,
    })),
    today_words: Array.from({ length: 40 }, (_, i) => `词语${i}`),
    emotion: { valence: 0.6, arousal: 0.4 },
    created_at: 0,
    updated_at: 0,
  };
}

describe('FR-G03 上下文注入包', () => {
  it('注入包含四要素:剧本状态/最近10轮/今日已学词/情绪分', () => {
    const cb = new ContextBuilder(DEFAULT_BUDGETS);
    const { bundle } = cb.build(bigSession(30), 'memory', { minister: 'ahai' });
    assert.deepEqual(Object.keys(bundle.script_state).sort(), ['act', 'plot', 'role', 'scene']);
    assert.ok(bundle.recent_turns.length <= 10);
    assert.ok(bundle.recent_turns.length > 0, '预算充足时应装满最近对话');
    assert.ok(bundle.today_words.length > 0);
    assert.equal(bundle.emotion.valence, 0.6);
    assert.equal(bundle.intent, 'memory');
    assert.equal(bundle.minister, 'ahai');
  });

  it('最近 10 轮按时间升序,取最新一轮结尾', () => {
    const cb = new ContextBuilder(DEFAULT_BUDGETS);
    const session = bigSession(30, 6);
    const { bundle } = cb.build(session, 'memory', { minister: 'ahai' });
    assert.ok(bundle.recent_turns.length >= 1);
    const ts = bundle.recent_turns.map((t) => t.ts);
    assert.deepEqual([...ts].sort((a, b) => a - b), ts, '应保持时间升序');
    assert.ok(ts[ts.length - 1]! > ts[0]!);
    const lastIdx = session.turns[session.turns.length - 1]!.text;
    assert.equal(bundle.recent_turns[bundle.recent_turns.length - 1]!.text, lastIdx, '应包含最新一轮');
  });

  it('token 预算分级:闲聊 500 / 任务 1500', () => {
    const cb = new ContextBuilder(DEFAULT_BUDGETS);
    assert.equal(cb.resolveBudget('chitchat'), 500);
    assert.equal(cb.resolveBudget('memory'), 1500);
    assert.equal(cb.resolveBudget('comfort'), 1500);
    assert.equal(cb.resolveBudget('chitchat', true), 300, '澄清模式 300');
  });

  it('闲聊预算 500 生效:超长会话被裁剪且不超预算', () => {
    const cb = new ContextBuilder(DEFAULT_BUDGETS);
    const { bundle } = cb.build(bigSession(30, 200), 'chitchat', { minister: 'xiaop' });
    assert.equal(bundle.budget, 500);
    assert.ok(bundle.tokens_used <= 500, `tokens_used=${bundle.tokens_used}`);
    assert.ok(bundle.notes.some((n) => n.includes('裁剪')));
    // 最新一轮强制保留(必要时截断),注入包永不空对话
    assert.equal(bundle.recent_turns.length, 1);
    const newest = bundle.recent_turns[0]!;
    assert.ok(newest.text.startsWith('这是一段'));
    assert.ok(newest.text.endsWith('…'), '截断应带省略标记');
  });

  it('任务预算 1500 生效', () => {
    const cb = new ContextBuilder(DEFAULT_BUDGETS);
    const { bundle } = cb.build(bigSession(30, 200), 'word', { minister: 'laonie' });
    assert.equal(bundle.budget, 1500);
    assert.ok(bundle.tokens_used <= 1500);
    assert.ok(bundle.recent_turns.length >= 1, '预算不足时也必须注入最新一轮');
  });

  it('注入包生成延迟 ≤50ms(验收线,p95)', () => {
    const cb = new ContextBuilder(DEFAULT_BUDGETS);
    const session = bigSession(30);
    for (let i = 0; i < 300; i++) {
      cb.build(session, i % 2 ? 'memory' : 'chitchat', { minister: 'ahai' });
    }
    const stats = cb.latencyStats();
    assert.ok(stats.p95 <= 50, `p95=${stats.p95.toFixed(3)}ms 超过 50ms`);
    assert.ok(stats.samples === 300);
  });
});
