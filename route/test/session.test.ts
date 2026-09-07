// 非功能验收:单会话状态内存常驻;崩溃恢复后从记忆存储重建(≤2s);
// 路由+注入全流程 ≤100ms;全部调度决策留审计日志。
import assert from 'node:assert/strict';
import { describe, it } from 'node:test';
import { mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { App } from '../src/app.ts';

describe('会话状态与崩溃恢复', () => {
  it('恢复:新进程从快照重建会话(≤2s),剧情上下文保持 100% 不串台', async () => {
    const root = mkdtempSync(join(tmpdir(), 'route-recover-'));
    const dataDir = join(root, 'data');
    try {
      // "进程 A":正常服务
      const appA = new App({ dataDir, configDir: null });
      await appA.dispatch({
        session_id: 'sess-1',
        utterance: '我昨天教会小熊什么来着',
        script_state: { plot: '朝会', scene: '金銮殿', role: '小皇上', act: 2 },
      });
      await appA.dispatch({
        session_id: 'sess-1',
        utterance: '那再教我一个新词吧',
        script_state: { act: 3 },
      });
      await appA.dispatch({ session_id: 'sess-2', utterance: '你好呀,小P' });
      appA.sessions.flushSync();
      const turnsBefore = appA.sessions.get('sess-1').turns.length;
      const scriptBefore = appA.sessions.get('sess-1').script_state;
      const wordsBefore = appA.sessions.get('sess-1').today_words;
      appA.shutdown();

      // "进程 B":崩溃后重启恢复
      const appB = new App({ dataDir, configDir: null });
      const recovery = appB.recover();
      try {
        assert.ok(recovery.elapsed_ms <= 2000, `恢复耗时 ${recovery.elapsed_ms.toFixed(1)}ms 超过 2s`);
        assert.equal(recovery.restored, 2);
      const restored = appB.sessions.get('sess-1');
      assert.equal(restored.minister_on_duty, 'laonie', '值守大臣状态恢复(第2轮学词意图后为老颞)');
        assert.equal(restored.turns.length, turnsBefore, '对话轮逐条恢复');
        assert.deepEqual(restored.script_state, scriptBefore, '剧本状态恢复(上下文保持率 100%)');
        assert.deepEqual(restored.today_words, wordsBefore, '今日已学词恢复');

        // 恢复后的会话继续用:注入包应带着恢复的剧情状态
        const resp = await appB.dispatch({ session_id: 'sess-1', utterance: '小熊还记得昨天吗' });
        assert.equal(resp.minister, 'ahai');
        assert.equal(resp.ctx_bundle.script_state.act, 3);
        assert.ok(resp.ctx_bundle.recent_turns.length >= 2, '恢复的历史对话进入注入包');
      } finally {
        appB.shutdown();
      }
    } finally {
      rmSync(root, { recursive: true, force: true });
    }
  });

  it('无快照的会话恢复报告 found=false,不报错', () => {
    const t = { root: mkdtempSync(join(tmpdir(), 'route-x-')) };
    try {
      const app = new App({ dataDir: join(t.root, 'data'), configDir: null });
      try {
        assert.deepEqual(app.rebuildSession('ghost'), { found: false });
        const r = app.recover();
        assert.equal(r.restored, 0);
      } finally {
        app.shutdown();
      }
    } finally {
      rmSync(t.root, { recursive: true, force: true });
    }
  });
});

describe('审计日志(非功能)', () => {
  it('每次 dispatch 留痕:路由理由/注入摘要/写库结果', async () => {
    const t = await import('./util.ts').then((m) => m.makeTestApp());
    try {
      await t.app.dispatch({
        session_id: 's1',
        utterance: '我昨天教会小熊什么来着',
        memory_write: [{ store: 'episodic', kind: 'dialogue', payload: { text: '昨天教了苹果这个词' } }],
      });
      const records = t.app.audit.query({ type: 'dispatch' });
      assert.equal(records.length, 1);
      const rec = records[0]!;
      assert.equal(rec.route!.intent, 'memory');
      assert.equal(rec.route!.minister, 'ahai');
      assert.ok(rec.route!.reason.length > 0, '路由理由必须留痕');
      assert.ok(rec.ctx_summary!.budget > 0);
      assert.equal(rec.write_results!.length, 1);
      assert.equal(rec.write_results![0]!.ok, true);
      // 按类型过滤
      assert.equal(t.app.audit.query({ type: 'memory_write' }).length, 1);
    } finally {
      t.dispose();
    }
  });
});
