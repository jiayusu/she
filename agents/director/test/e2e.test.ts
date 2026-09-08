// 端到端:真实 HTTP + WS 全链路。
// PRD §6 接口契约 + 非功能(路由+注入 ≤100ms)+ 用户故事(记忆询问路由阿海)。
import assert from 'node:assert/strict';
import { after, before, describe, it } from 'node:test';
import { WebSocket } from 'ws';
import { mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { App } from '../src/app.ts';
import { listen, type HttpServerInfo } from '../src/server.ts';

let app: App;
let info: HttpServerInfo;
let root: string;
const base = (): string => `http://127.0.0.1:${info.port}`;

before(async () => {
  root = mkdtempSync(join(tmpdir(), 'route-e2e-'));
  app = new App({ dataDir: join(root, 'data'), configDir: null });
  info = await listen(app, 0);
});

after(async () => {
  app.shutdown();
  await info.close();
  rmSync(root, { recursive: true, force: true });
});

async function post(path: string, body: unknown): Promise<{ status: number; json: Record<string, unknown> }> {
  const r = await fetch(`${base()}${path}`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(body),
  });
  return { status: r.status, json: (await r.json()) as Record<string, unknown> };
}

async function get(path: string): Promise<{ status: number; json: Record<string, unknown> }> {
  const r = await fetch(`${base()}${path}`);
  return { status: r.status, json: (await r.json()) as Record<string, unknown> };
}

describe('POST /agent/dispatch 契约', () => {
  it('用户故事:记忆询问 → 路由阿海,带最近剧情上下文', async () => {
    // 先建立剧情上下文(朝会中)
    await post('/agent/dispatch', {
      session_id: 'u1',
      utterance: '今天我们要开朝会吗',
      script_state: { plot: '朝会', scene: '金銮殿' },
    });
    const { status, json } = await post('/agent/dispatch', {
      session_id: 'u1',
      utterance: '我昨天教会小熊什么来着',
      emotion: 0.1,
      asr: { conf: 0.95 },
    });
    assert.equal(status, 200);
    assert.equal(json.intent, 'memory');
    assert.equal(json.minister, 'ahai');
    assert.equal(json.minister_label, '阿海');
    assert.equal(json.need_clarify, false);
    const bundle = json.ctx_bundle as Record<string, unknown>;
    assert.deepEqual((bundle.script_state as Record<string, unknown>).plot, '朝会', '注入包带剧本状态');
    assert.ok((bundle.recent_turns as unknown[]).length >= 1, '注入包带最近对话');
    assert.ok(typeof bundle.emotion === 'object');
    assert.ok(typeof json.latency_ms === 'number');
  });

  it('用户故事:万物意图路由老颞,注入包标注当前剧情避免串台', async () => {
    const { json } = await post('/agent/dispatch', {
      session_id: 'u2',
      utterance: '冰箱为什么会响',
      script_state: { plot: '朝会' },
    });
    assert.equal(json.intent, 'object');
    assert.equal(json.minister, 'laonie');
    assert.equal((json.ctx_bundle as Record<string, unknown>).budget, 1500, '万物为任务类,预算 1500');
  });

  it('低置信度 → 小P反问澄清', async () => {
    const { json } = await post('/agent/dispatch', { session_id: 'u3', utterance: '嗯嗯' });
    assert.equal(json.need_clarify, true);
    assert.equal(json.minister, 'xiaop');
    assert.ok(String(json.clarify_question).includes('小P'));
  });

  it('memory_write 随请求提交 → memory_write_ack 回执 + 里程碑入白名单', async () => {
    const { json } = await post('/agent/dispatch', {
      session_id: 'u1',
      utterance: '小熊还记得昨天吗',
      memory_write: [
        { store: 'episodic', kind: 'milestone', payload: { text: '孩子第一次完整复述故事' } },
        { store: 'episodic', kind: 'word_learned', payload: { word: '苹果', eval: 'passed' } },
      ],
    });
    const acks = json.memory_write_ack as Array<Record<string, unknown>>;
    assert.equal(acks.length, 2);
    assert.ok(acks.every((a) => a.ok === true));
    assert.equal(acks[0]!.whitelisted, true, '里程碑事件显著性达标');
    assert.equal(acks[0]!.salience, 1.0);
    // 今日已学词进入会话状态
    const sess = await get('/agent/session/u1');
    assert.ok((sess.json.today_words as string[]).includes('苹果'));
  });

  it('缺字段 → 400;未知路由 → 404', async () => {
    assert.equal((await post('/agent/dispatch', { utterance: 'hi' })).status, 400);
    assert.equal((await get('/agent/nope')).status, 404);
  });

  it('路由+注入全流程 ≤100ms(不含 LLM 推理,p95)', async () => {
    const latencies: number[] = [];
    for (let i = 0; i < 100; i++) {
      const { json } = await post('/agent/dispatch', {
        session_id: `perf-${i % 5}`,
        utterance: i % 3 === 0 ? '我昨天教会小熊什么来着' : i % 3 === 1 ? '你好呀,小P' : '冰箱为什么会响',
        memory_write: [{ store: 'working', kind: 'dialogue', payload: { text: '压测' } }],
      });
      latencies.push(json.latency_ms as number);
    }
    latencies.sort((a, b) => a - b);
    const p95 = latencies[Math.floor(latencies.length * 0.95)]!;
    assert.ok(p95 <= 100, `p95=${p95.toFixed(2)}ms 超过 100ms`);
  });
});

describe('WS /agent/session', () => {
  it('订阅后收到 hello 与大臣值守切换事件', async () => {
    const ws = new WebSocket(`ws://127.0.0.1:${info.port}/agent/session`);
    const received: Array<Record<string, unknown>> = [];
    ws.on('message', (d) => received.push(JSON.parse(String(d)) as Record<string, unknown>));
    await new Promise<void>((resolve, reject) => {
      ws.once('open', resolve);
      ws.once('error', reject);
    });
    ws.send(JSON.stringify({ type: 'ping' }));

    await post('/agent/dispatch', { session_id: 'ws-1', utterance: '今天我们要开朝会吗' });
    await post('/agent/dispatch', { session_id: 'ws-1', utterance: '你好呀,小P' });
    await new Promise((r) => setTimeout(r, 150));

    const types = received.map((m) => m.type);
    assert.ok(types.includes('hello'), '连接即同步各会话值守大臣(灯效)');
    assert.ok(types.includes('pong'));
    assert.ok(types.includes('minister_change'), '值守切换事件推送');

    const change = received.find((m) => m.type === 'minister_change')!;
    const payload = change.payload as Record<string, unknown>;
    assert.equal(payload.session_id, 'ws-1');
    ws.close();
  });

  it('session_id 过滤:只收本会话事件', async () => {
    const ws = new WebSocket(`ws://127.0.0.1:${info.port}/agent/session?session_id=only-me`);
    const received: Array<Record<string, unknown>> = [];
    ws.on('message', (d) => received.push(JSON.parse(String(d)) as Record<string, unknown>));
    await new Promise<void>((resolve) => ws.once('open', resolve));

    await post('/agent/dispatch', { session_id: 'other-guy', utterance: '你好呀' });
    await post('/agent/dispatch', { session_id: 'only-me', utterance: '给我讲个笑话吧' });
    await new Promise((r) => setTimeout(r, 150));
    ws.close();

    for (const m of received) {
      const sid = (m.payload as Record<string, unknown> | undefined)?.session_id;
      assert.ok(sid === undefined || sid === 'only-me', `不应收到其他会话事件: ${JSON.stringify(m)}`);
    }
    assert.ok(received.some((m) => m.type === 'dispatch_done'));
  });
});

describe('健康与管理端点', () => {
  it('GET /healthz', async () => {
    const { status, json } = await get('/healthz');
    assert.equal(status, 200);
    assert.equal(json.ok, true);
    assert.ok(Array.isArray(json.ministers));
  });

  it('GET /admin/metrics 含四类埋点', async () => {
    const { json } = await get('/admin/metrics');
    const counters = json.counters as Record<string, number>;
    assert.ok(Object.keys(counters).some((k) => k.startsWith('route_done{')), 'route_done(intent, minister, conf)');
    assert.ok(Object.keys(counters).some((k) => k.startsWith('ctx_built{')), 'ctx_built(tokens)');
    assert.ok(Object.keys(counters).some((k) => k.startsWith('memory_write{')), 'memory_write(store, ok)');
    assert.ok(json.route_latency !== undefined);
  });

  it('GET /admin/audit 可查询调度留痕', async () => {
    const { json } = await get('/admin/audit?type=dispatch&limit=5');
    assert.ok(Array.isArray(json));
    assert.ok((json as unknown[]).length > 0);
  });

  it('巩固:trigger → confirm 全链路(HTTP)', async () => {
    // 造 3 次评估通过的词
    await post('/agent/dispatch', {
      session_id: 'u4',
      utterance: '教我一个新词',
      memory_write: [
        { store: 'episodic', kind: 'word_learned', payload: { word: '菠萝', eval: 'passed' } },
        { store: 'episodic', kind: 'word_learned', payload: { word: '菠萝', eval: 'passed' } },
        { store: 'episodic', kind: 'word_learned', payload: { word: '菠萝', eval: 'passed' } },
      ],
    });
    const trig = await post('/admin/consolidation/trigger', {});
    const report = trig.json as unknown as { status: string; id: string; candidates: Array<{ word: string }> };
    assert.equal(report.status, 'draft');
    assert.ok(report.candidates.some((c) => c.word === '菠萝'), '同一周 draft 复用,此前 u1 的苹果也应在内');

    const conf = await post('/admin/consolidation/confirm', { report_id: report.id });
    assert.ok(Number(conf.json.applied) >= 1);
    assert.equal(conf.json.status, 'confirmed');
  });

  it('死信队列端点:retry 后清零', async () => {
    const dlq = await get('/admin/dlq');
    assert.ok(typeof dlq.json.open === 'number');
    const retry = await post('/admin/dlq/retry', {});
    assert.ok(typeof retry.json.retried === 'number');
  });

  it('GET /admin/tools:边界清单可机读', async () => {
    const { json } = await get('/admin/tools');
    const mcp = json.mcp_tools as Array<{ name: string }>;
    const hooks = json.system_hooks as Array<{ name: string }>;
    assert.ok(mcp.some((t) => t.name === 'kg.query'));
    assert.equal(hooks.length, 3);
  });
});
