// 零依赖 Node 服务：
//   静态托管 web/（index / admin / js / css / models）
//   POST /api/see                 视觉模块接口（FR-P04 确认通过后调用）
//   GET|POST|DELETE /admin/pointing-stats   FR-P08 埋点回流 + 报表聚合
//   POST /crown/press             模拟蛇首按下 → 向 /ws/crown 广播"请拍照"（FR-P10）
//   WS   /ws/crown                浏览器监听拍照指令
import http from 'node:http';
import fs from 'node:fs';
import fsp from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { WsConnection, acceptKey } from './ws.js';
import { generateReply } from './see.js';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const WEB_ROOT = path.resolve(__dirname, '../web');

const MIME = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.mjs': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.svg': 'image/svg+xml',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.ico': 'image/x-icon',
  '.onnx': 'application/octet-stream',
  '.task': 'application/octet-stream',
  '.map': 'application/json',
};

export function createServer({ port = 8787, env = process.env } = {}) {
  const wsClients = new Set();
  const DATA_DIR = env.PO_DATA_DIR || process.env.PO_DATA_DIR || path.resolve(__dirname, '../data');
  const STATS_FILE = path.join(DATA_DIR, 'pointing-stats.jsonl');

  const server = http.createServer(async (req, res) => {
    try {
      await route(req, res);
    } catch (err) {
      sendJson(res, 500, { ok: false, error: String(err && err.message || err) });
    }
  });

  async function route(req, res) {
    const u = new URL(req.url, 'http://localhost');
    const p = u.pathname;

    if (p === '/healthz') return sendJson(res, 200, { ok: true, ts: Date.now() });

    if (p === '/api/see' && req.method === 'POST') {
      const body = await readJson(req, 12 * 1024 * 1024);
      const hint = body.bbox_hint || {};
      const t0 = Date.now();
      const reply = await generateReply({ label: hint.label, level: body.level }, env);
      // 注意：请求里的 image 仅裁切区域，存根不落盘（隐私：不落盘不上传原图）
      return sendJson(res, 200, {
        ok: true,
        text: reply.text,
        source: reply.source,
        bbox_hint: hint,
        latencyMs: Date.now() - t0,
      });
    }

    if (p === '/admin/pointing-stats') {
      if (req.method === 'POST') {
        const rec = await readJson(req, 256 * 1024);
        await appendStats(sanitizeSession(rec));
        return sendJson(res, 200, { ok: true });
      }
      if (req.method === 'DELETE') {
        await fsp.mkdir(DATA_DIR, { recursive: true });
        await fsp.writeFile(STATS_FILE, '', 'utf8');
        return sendJson(res, 200, { ok: true });
      }
      if (req.method === 'GET') {
        const sessions = await readStats();
        return sendJson(res, 200, { ok: true, ...aggregate(sessions) });
      }
    }

    if (p === '/crown/press' && req.method === 'POST') {
      const msg = JSON.stringify({ type: 'please_photo', ts: Date.now() });
      let delivered = 0;
      for (const c of wsClients) {
        try { c.send(msg); delivered++; } catch { /* 坏连接由 close 回调清理 */ }
      }
      return sendJson(res, 200, { ok: true, delivered });
    }

    if (req.method === 'GET' || req.method === 'HEAD') return serveStatic(req, p, res);
    return sendJson(res, 404, { ok: false, error: 'not found' });
  }

  // FR-P10：/ws/crown 升级
  server.on('upgrade', (req, socket) => {
    const u = new URL(req.url, 'http://localhost');
    if (u.pathname !== '/ws/crown' || !req.headers['sec-websocket-key']) {
      socket.destroy();
      return;
    }
    socket.write(
      'HTTP/1.1 101 Switching Protocols\r\n' +
      'Upgrade: websocket\r\n' +
      'Connection: Upgrade\r\n' +
      `Sec-WebSocket-Accept: ${acceptKey(req.headers['sec-websocket-key'])}\r\n\r\n`
    );
    const conn = new WsConnection(socket);
    wsClients.add(conn);
    conn.on('close', () => wsClients.delete(conn));
  });

  // ---- 埋点存储与聚合（FR-P08 / FR-P09）----
  function sanitizeSession(rec) {
    // 只保留必要字段；绝不落盘图像
    const num = (v) => (Number.isFinite(Number(v)) ? Number(v) : undefined);
    return {
      ts: typeof rec.ts === 'string' ? rec.ts : new Date().toISOString(),
      trigger: rec.trigger,
      gestureHitFrames: num(rec.gestureHitFrames),
      gestureTotalFrames: num(rec.gestureTotalFrames),
      gestureRelaxed: !!rec.gestureRelaxed,
      selectedBy: rec.selectedBy,
      selectedLabel: rec.selectedLabel,
      selectedBox: Array.isArray(rec.selectedBox) ? rec.selectedBox : undefined,
      confirmStyle: rec.confirmStyle,
      confirmResult: rec.confirmResult,
      confirmRounds: num(rec.confirmRounds),
      corrections: num(rec.corrections),
      autoPassed: !!rec.autoPassed,
      outcome: rec.outcome,
      triggerToCaptureMs: num(rec.triggerToCaptureMs),
      windowDurationMs: num(rec.windowDurationMs),
      seeLatencyMs: num(rec.seeLatencyMs),
      apiSource: rec.apiSource,
      ua: typeof rec.ua === 'string' ? rec.ua.slice(0, 200) : undefined,
    };
  }

  async function appendStats(rec) {
    await fsp.mkdir(DATA_DIR, { recursive: true });
    await fsp.appendFile(STATS_FILE, JSON.stringify(rec) + '\n', 'utf8');
  }

  async function readStats() {
    let raw;
    try {
      raw = await fsp.readFile(STATS_FILE, 'utf8');
    } catch {
      return [];
    }
    const out = [];
    for (const line of raw.split('\n')) {
      const s = line.trim();
      if (!s) continue;
      try { out.push(JSON.parse(s)); } catch { /* 跳过坏行 */ }
    }
    return out;
  }

  function aggregate(sessions) {
    const byDay = new Map();
    const byLabel = new Map();
    const gestureHist = { '0': 0, '1-2': 0, '3+': 0 };
    let total = sessions.length;
    let confirmed = 0;
    let confirmedFirstTry = 0;
    let correctionsSum = 0;
    let roundsSum = 0;
    let confirmSessions = 0;
    let triggerSlow = 0;

    const todayKey = new Date().toISOString().slice(0, 10);
    const todayRecords = [];

    for (const s of sessions) {
      const day = String(s.ts || '').slice(0, 10) || 'unknown';
      const d = byDay.get(day) || { date: day, sessions: 0, confirmed: 0, corrections: 0 };
      d.sessions++;
      const ok = s.outcome === 'confirmed';
      if (ok) d.confirmed++;
      d.corrections += s.corrections || 0;
      byDay.set(day, d);

      if (s.selectedLabel) {
        const l = byLabel.get(s.selectedLabel) || { label: s.selectedLabel, count: 0, confirmed: 0 };
        l.count++;
        if (ok) l.confirmed++;
        byLabel.set(s.selectedLabel, l);
      }
      const hits = s.gestureHitFrames ?? 0;
      gestureHist[hits >= 3 ? '3+' : hits >= 1 ? '1-2' : '0']++;

      if (s.outcome === 'confirmed' || s.outcome === 'exit') {
        confirmSessions++;
        if (ok) {
          confirmed++;
          if ((s.corrections || 0) === 0) confirmedFirstTry++;
        }
        correctionsSum += s.corrections || 0;
        roundsSum += s.confirmRounds || 0;
      }
      if (s.triggerToCaptureMs > 1000) triggerSlow++;

      if (day === todayKey && ok) {
        todayRecords.push({
          time: String(s.ts).slice(11, 19),
          label: s.selectedLabel,
          corrections: s.corrections || 0,
          rounds: s.confirmRounds || 0,
        });
      }
    }

    const days = [...byDay.values()].sort((a, b) => a.date.localeCompare(b.date));
    return {
      total,
      confirmSessions,
      confirmed,
      // 北极星代理：确认通过（孩子说"对"）/ 进入确认的会话
      accuracy: confirmSessions ? +(confirmed / confirmSessions).toFixed(4) : null,
      firstTryAccuracy: confirmed ? +(confirmedFirstTry / confirmed).toFixed(4) : null,
      avgCorrections: confirmSessions ? +(correctionsSum / confirmSessions).toFixed(2) : null,
      avgRounds: confirmSessions ? +(roundsSum / confirmSessions).toFixed(2) : null,
      triggerSlowCount: triggerSlow,
      gestureHist,
      days,
      labels: [...byLabel.values()].sort((a, b) => b.count - a.count),
      // FR-P09 今日万物记录（家长端）
      today: {
        date: todayKey,
        pointed: todayRecords.length,
        correct: todayRecords.filter((r) => r.corrections === 0).length,
        records: todayRecords,
      },
      recent: sessions.slice(-20),
    };
  }

  // ---- 静态文件 ----
  async function serveStatic(req, p, res) {
    let rel = decodeURIComponent(p);
    if (rel === '/' || rel === '/index.html') rel = '/index.html';
    if (rel === '/admin' || rel === '/admin/') rel = '/admin.html';
    const file = path.normalize(path.join(WEB_ROOT, rel));
    if (!file.startsWith(WEB_ROOT)) return sendJson(res, 403, { ok: false, error: 'forbidden' });
    let stat;
    try {
      stat = await fsp.stat(file);
      if (stat.isDirectory()) return sendJson(res, 403, { ok: false, error: 'forbidden' });
    } catch {
      return sendJson(res, 404, { ok: false, error: 'not found' });
    }
    const ext = path.extname(file).toLowerCase();
    res.writeHead(200, {
      'content-type': MIME[ext] || 'application/octet-stream',
      'content-length': stat.size,
      'cache-control': ext === '.onnx' || ext === '.task' ? 'public, max-age=86400' : 'no-cache',
    });
    if (req.method === 'HEAD') return res.end();
    fs.createReadStream(file).pipe(res);
  }

  return {
    server,
    wsCount: () => wsClients.size,
    STATS_FILE,
    // 立即断开 keep-alive 连接，保证测试/进程可退出
    stop: () => { server.close(); server.closeAllConnections?.(); },
  };
}

function readJson(req, limit) {
  return new Promise((resolve, reject) => {
    const chunks = [];
    let size = 0;
    req.on('data', (c) => {
      size += c.length;
      if (size > limit) {
        reject(new Error('payload too large'));
        req.destroy();
        return;
      }
      chunks.push(c);
    });
    req.on('end', () => {
      try {
        const text = Buffer.concat(chunks).toString('utf8');
        resolve(text ? JSON.parse(text) : {});
      } catch (e) {
        reject(new Error('invalid json'));
      }
    });
    req.on('error', reject);
  });
}

function sendJson(res, code, obj) {
  const body = JSON.stringify(obj);
  res.writeHead(code, { 'content-type': 'application/json; charset=utf-8', 'content-length': Buffer.byteLength(body) });
  res.end(body);
}

// 直接运行：node server/server.js
if (process.argv[1] && fileURLToPath(import.meta.url) === path.resolve(process.argv[1])) {
  const port = Number(process.env.PORT || 8787);
  const { server } = createServer({ port });
  server.listen(port);
  server.on('listening', () => {
    console.log(`[pointing-module] http://localhost:${port}  （主页面 / ，家长报表 /admin.html）`);
  });
}
