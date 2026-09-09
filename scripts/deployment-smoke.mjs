import assert from 'node:assert/strict';
const base = process.env.SHE_SMOKE_URL ?? 'http://127.0.0.1:8080';
async function get(path) {
  const response = await fetch(`${base}${path}`, { signal: AbortSignal.timeout(10000) });
  assert.equal(response.status, 200, `${path} status`);
  return response;
}
const html = await (await get('/')).text();
assert.match(html, /<div id="root"><\/div>/);
const asset = html.match(/src="([^"]+\.js)"/);
assert.ok(asset, 'built JavaScript asset');
assert.match((await get(asset[1])).headers.get('content-type'), /javascript/);
assert.equal((await (await get('/health')).json()).status, 'ok');
const dashboard = await (await get('/v1/dashboard')).json();
assert.equal(dashboard.contract_version, '1.0');
assert.equal(dashboard.mock, true);
assert.equal((await (await get('/v1/reports/weekly')).json()).contract_version, '1.0');
console.log('Deployment smoke passed: HTML, JavaScript, health, dashboard, weekly report.');
