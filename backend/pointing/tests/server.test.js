// 服务端测试：静态服务、/api/see（模板 + LLM 失败兜底）、埋点报表聚合、/ws/crown 广播（FR-P08/10）。
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { once } from 'node:events';
import { tmpdir } from 'node:os';
import { createServer } from '../server/server.js';

// 每个用例用独立数据目录，避免污染真实埋点
async function start(env = {}) {
  const { mkdtempSync } = await import('node:fs');
  const dataDir = mkdtempSync(`${tmpdir()}/po-test-`);
  process.env.PO_DATA_DIR = dataDir;
  const { server, stop } = createServer({ port: 0, env });
  server.listen(0);
  await once(server, 'listening');
  const port = server.address().port;
  return { server, stop, base: `http://127.0.0.1:${port}`, wsBase: `ws://127.0.0.1:${port}` };
}

test('静态服务：/ 返回主页面，/js/app.js 可加载', async () => {
  const { stop, base } = await start();
  try {
    const html = await (await fetch(`${base}/`)).text();
    assert.ok(html.includes('万物模式'));
    const js = await fetch(`${base}/js/app.js`);
    assert.equal(js.status, 200);
    const admin = await (await fetch(`${base}/admin.html`)).text();
    assert.ok(admin.includes('家长报表'));
    assert.equal((await fetch(`${base}/%2e%2e%2fserver.js`)).status, 403); // 目录穿越防护
  } finally {
    stop();
  }
});

test('/api/see：模板回应非空；LLM 不可达 → template-fallback（FR-P05）', async () => {
  const { stop, base } = await start();
  try {
    const r1 = await (await fetch(`${base}/api/see`, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ image: null, level: 'kid', bbox_hint: { label: '冰箱', x: 1, y: 2, w: 3, h: 4 } }),
    })).json();
    assert.equal(r1.ok, true);
    assert.ok(r1.text.includes('冰箱'));
    assert.equal(r1.source, 'template');
  } finally {
    stop();
  }

  const { stop: s2stop, base: b2 } = await start({
    SEE_LLM_URL: 'http://127.0.0.1:9/unreachable', // 必然连接失败
  });
  try {
    const r2 = await (await fetch(`${b2}/api/see`, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ bbox_hint: { label: '杯子' } }),
    })).json();
    assert.equal(r2.ok, true);
    assert.ok(r2.text.length > 0);
    assert.equal(r2.source, 'template-fallback');
  } finally {
    s2stop();
  }
});

test('/admin/pointing-stats：POST 埋点 → GET 聚合（FR-P08/09）', async () => {
  const { stop, base } = await start();
  try {
    await fetch(`${base}/admin/pointing-stats`, { method: 'DELETE' }); // 清空，保证断言确定性
    const today = new Date().toISOString();
    const mk = (label, outcome, corrections, i) => ({
      ts: today,
      trigger: 'button',
      gestureHitFrames: i,
      gestureTotalFrames: 5,
      selectedLabel: label,
      selectedBy: 'ray',
      confirmStyle: 'light',
      confirmResult: outcome === 'confirmed' ? 'affirm' : 'exit:deny',
      confirmRounds: corrections + 1,
      corrections,
      outcome,
    });
    await fetch(`${base}/admin/pointing-stats`, {
      method: 'POST', headers: { 'content-type': 'application/json' },
      body: JSON.stringify(mk('冰箱', 'confirmed', 0, 4)),
    });
    await fetch(`${base}/admin/pointing-stats`, {
      method: 'POST', headers: { 'content-type': 'application/json' },
      body: JSON.stringify(mk('杯子', 'exit', 2, 0)),
    });

    const data = await (await fetch(`${base}/admin/pointing-stats`)).json();
    assert.equal(data.ok, true);
    assert.equal(data.total, 2);
    assert.equal(data.confirmed, 1);
    assert.equal(data.accuracy, 0.5);          // 确认通过 / 进入确认
    assert.equal(data.firstTryAccuracy, 1);    // 唯一成功一次即中
    assert.equal(data.avgCorrections, 1);
    assert.deepEqual(data.gestureHist, { '0': 1, '1-2': 0, '3+': 1 });
    assert.equal(data.today.pointed, 1);       // FR-P09 今日万物记录
    assert.equal(data.today.correct, 1);
    assert.equal(data.today.records[0].label, '冰箱');
    assert.equal(data.labels[0].label, '冰箱');
  } finally {
    stop();
  }
});

test('FR-P10：WS /ws/crown 客户端收到 /crown/press 广播的拍照指令', async () => {
  const { stop, base, wsBase } = await start();
  try {
    const ws = new WebSocket(`${wsBase}/ws/crown`);
    await once(ws, 'open');
    const got = new Promise((resolve) => { ws.onmessage = (e) => resolve(JSON.parse(e.data)); });
    const pressRes = await (await fetch(`${base}/crown/press`, { method: 'POST' })).json();
    assert.equal(pressRes.ok, true);
    assert.equal(pressRes.delivered, 1);
    const msg = await Promise.race([got, new Promise((_, rej) => setTimeout(() => rej(new Error('未收到广播')), 2000))]);
    assert.equal(msg.type, 'please_photo');
    ws.close();
  } finally {
    stop();
  }
});
