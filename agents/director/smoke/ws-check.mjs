import WebSocket from 'ws';
const ws = new WebSocket('ws://127.0.0.1:8901/agent/session?session_id=child-001');
const got = [];
ws.on('message', (d) => got.push(JSON.parse(String(d))));
await new Promise((r) => ws.once('open', r));
ws.send(JSON.stringify({ type: 'ping' }));
const post = async (file) => {
  const { readFileSync } = await import('node:fs');
  await fetch('http://127.0.0.1:8901/agent/dispatch', {
    method: 'POST', headers: { 'content-type': 'application/json' },
    body: readFileSync(new URL(`../${file}`, import.meta.url)),
  });
};
await post('smoke/p2-object.json');  // 会触发 minister_change(老颞)
await new Promise((r) => setTimeout(r, 300));
console.log('WS 事件序列:', got.map((m) => m.type).join(' -> '));
const change = got.find((m) => m.type === 'minister_change');
console.log('minister_change payload:', JSON.stringify(change?.payload));
const hello = got.find((m) => m.type === 'hello');
console.log('hello(值守灯效):', JSON.stringify(hello?.sessions?.filter((s) => s.session_id === 'child-001')));
ws.close();
