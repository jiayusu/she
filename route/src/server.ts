// HTTP + WS 服务(接口契约见 PRD §6):
//   POST /agent/dispatch  { utterance, asr, emotion, session_id } → { minister, ctx_bundle, memory_write_ack }
//   WS   /agent/session   会话状态订阅(App 端"当前哪位大臣值守"灯效同步)
// 另含 /admin/* 运维端点与 /healthz。

import http from 'node:http';
import { WebSocketServer, WebSocket } from 'ws';
import type { App } from './app.ts';
import { DispatchError } from './app.ts';
import { MINISTER_LABEL, MINISTERS } from './types.ts';

const MAX_BODY = 1 << 20; // 1MB

export interface HttpServerInfo {
  server: http.Server;
  port: number;
  close(): Promise<void>;
}

function sendJson(res: http.ServerResponse, status: number, body: unknown): void {
  const buf = Buffer.from(JSON.stringify(body), 'utf8');
  res.writeHead(status, {
    'content-type': 'application/json; charset=utf-8',
    'content-length': buf.length,
  });
  res.end(buf);
}

function readBody(req: http.IncomingMessage): Promise<string> {
  return new Promise((resolve, reject) => {
    let size = 0;
    const chunks: Buffer[] = [];
    req.on('data', (c: Buffer) => {
      size += c.length;
      if (size > MAX_BODY) {
        reject(new DispatchError('请求体超过 1MB 限制'));
        req.destroy();
        return;
      }
      chunks.push(c);
    });
    req.on('end', () => resolve(Buffer.concat(chunks).toString('utf8')));
    req.on('error', reject);
  });
}

async function parseJsonBody(body: () => Promise<string>): Promise<unknown> {
  const raw = await body();
  try {
    return JSON.parse(raw || '{}');
  } catch {
    throw new DispatchError('请求体不是合法 JSON');
  }
}

type Handler = (ctx: {
  req: http.IncomingMessage;
  res: http.ServerResponse;
  params: Record<string, string>;
  query: URLSearchParams;
  body: () => Promise<string>;
}) => Promise<void> | void;

export function createServer(app: App): HttpServerInfo {
  const wss = new WebSocketServer({ noServer: true });

  // WS:会话状态订阅(大臣值守灯效)
  app.bus.on('minister_change', (e) => broadcast(wss, 'minister_change', e));
  app.bus.on('dispatch_done', (e) => broadcast(wss, 'dispatch_done', e));
  app.bus.on('dlq_alert', (e) => broadcast(wss, 'dlq_alert', e));
  app.bus.on('whitelist_added', (e) => broadcast(wss, 'whitelist_added', e));
  app.bus.on('job_done', (e) => broadcast(wss, 'job_done', e));
  app.bus.on('consolidation_confirmed', (e) => broadcast(wss, 'consolidation_confirmed', e));
  app.bus.on('map_reloaded', (e) => broadcast(wss, 'map_reloaded', e));

  const routes: Array<[string, RegExp, Handler]> = [
    ['GET', /^\/healthz$/, async ({ res }) => {
      sendJson(res, 200, { ok: true, ...app.stats(), ministers: app.listMinisters() });
    }],

    // ---- 对外接口(PRD §6) ----
    ['POST', /^\/agent\/dispatch$/, async ({ res, body }) => {
      const parsed = (await parseJsonBody(body)) as never;
      const resp = await app.dispatch(parsed);
      sendJson(res, 200, resp);
    }],
    ['GET', /^\/agent\/session\/(?<id>.+)$/, async ({ res, params }) => {
      const state = app.sessions.list().find((s) => s.session_id === params.id);
      if (!state) {
        sendJson(res, 404, { error: '会话不存在(可尝试 POST /admin/sessions/:id/rebuild)' });
        return;
      }
      sendJson(res, 200, {
        session_id: state.session_id,
        minister_on_duty: state.minister_on_duty,
        minister_label: MINISTER_LABEL[state.minister_on_duty],
        script_state: state.script_state,
        recent_turns: state.turns.slice(-10),
        today_words: state.today_words,
        emotion: state.emotion,
        created_at: state.created_at,
        updated_at: state.updated_at,
      });
    }],

    // ---- FR-G02 映射表运维 ----
    ['GET', /^\/admin\/map$/, async ({ res }) => sendJson(res, 200, app.mapTable.config)],
    ['POST', /^\/admin\/map\/reload$/, async ({ res }) => sendJson(res, 200, await app.reloadMap())],

    ['POST', /^\/admin\/lexicon\/reload$/, async ({ res }) => {
      app.reloadLexicon();
      sendJson(res, 200, { ok: true });
    }],

    // ---- 大臣值守/降级 ----
    ['GET', /^\/admin\/ministers$/, async ({ res }) => sendJson(res, 200, app.listMinisters())],
    ['POST', /^\/admin\/ministers\/(?<id>\w+)\/degrade$/, async ({ res, params, body }) => {
      if (!MINISTERS.includes(params.id as never)) {
        sendJson(res, 404, { error: '未知大臣' });
        return;
      }
      const b = await parseJsonBody(body) as never as { on?: boolean };
      app.setDegraded(params.id as never, b.on !== false);
      sendJson(res, 200, app.listMinisters());
    }],

    // ---- FR-G06 巩固 ----
    ['POST', /^\/admin\/consolidation\/trigger$/, async ({ res }) => {
      const report = app.consolidation.runDraft();
      sendJson(res, 200, report);
    }],
    ['GET', /^\/admin\/consolidation\/reports$/, async ({ res }) => sendJson(res, 200, app.consolidation.listReports())],
    ['GET', /^\/admin\/consolidation\/reports\/(?<id>[\w-]+)$/, async ({ res, params }) => {
      const r = app.consolidation.getReport(params.id);
      if (!r) {
        sendJson(res, 404, { error: '报告不存在' });
        return;
      }
      sendJson(res, 200, r);
    }],
    ['POST', /^\/admin\/consolidation\/confirm$/, async ({ res, body }) => {
      const b = await parseJsonBody(body) as never as { report_id?: string };
      if (!b.report_id) {
        sendJson(res, 400, { error: '缺少 report_id' });
        return;
      }
      const r = app.consolidation.confirm(b.report_id);
      if (!r.report) {
        sendJson(res, 404, { error: '报告不存在或已确认' });
        return;
      }
      sendJson(res, 200, { applied: r.applied, status: r.report.status });
    }],

    // ---- FR-G07 元认知任务 ----
    ['GET', /^\/admin\/jobs$/, async ({ res }) => sendJson(res, 200, app.jobs.status())],
    ['POST', /^\/admin\/jobs\/(?<name>\w+)\/trigger$/, async ({ res, params }) => {
      try {
        const result = await app.jobs.triggerNow(params.name);
        sendJson(res, 200, result);
      } catch (e) {
        sendJson(res, 404, { error: (e as Error).message });
      }
    }],

    // ---- FR-G04 死信队列 ----
    ['GET', /^\/admin\/dlq$/, async ({ res }) =>
      sendJson(res, 200, { open: app.writeScheduler.openDlqCount(), items: app.writeScheduler.listDlq() })],
    ['POST', /^\/admin\/dlq\/retry$/, async ({ res }) => sendJson(res, 200, await app.writeScheduler.retryDlq())],
    ['POST', /^\/admin\/dlq\/sweep$/, async ({ res }) => sendJson(res, 200, await app.writeScheduler.sweepDlq())],

    // ---- FR-G05 白名单(只增) ----
    ['GET', /^\/admin\/whitelist$/, async ({ res }) => sendJson(res, 200, app.whitelist.list())],
    ['POST', /^\/admin\/whitelist$/, async ({ res, body }) => {
      const b = await parseJsonBody(body) as never as { ref_id?: string; reason?: string };
      if (!b.ref_id) {
        sendJson(res, 400, { error: '缺少 ref_id' });
        return;
      }
      const r = app.whitelist.add({ ref_id: b.ref_id, reason: b.reason ?? '人工加入', score: 1, source: 'manual' });
      app.audit.append({ ts: Date.now(), type: 'whitelist_add', detail: { ref_id: b.ref_id, source: 'manual', added: r.added } });
      sendJson(res, 200, r);
    }],

    // ---- FR-G08 工具边界 ----
    ['GET', /^\/admin\/tools$/, async ({ res }) =>
      sendJson(res, 200, { mcp_tools: app.tools.listMcpTools(), system_hooks: app.tools.listSystemHooks() })],
    ['POST', /^\/admin\/tools\/invoke$/, async ({ res, body }) => {
      const b = await parseJsonBody(body) as never as { name?: string; args?: Record<string, unknown> };
      try {
        const result = await app.tools.llmInvoke(b.name ?? '', b.args ?? {});
        sendJson(res, 200, { ok: true, result });
      } catch (e) {
        sendJson(res, (e as Error).name === 'ToolBoundaryError' ? 403 : 404, { error: (e as Error).message });
      }
    }],
    ['GET', /^\/admin\/kg\/pending-review$/, async ({ res }) => sendJson(res, 200, app.kg.listPendingReview())],
    ['POST', /^\/admin\/kg\/pending-review\/(?<id>[\w-]+)\/resolve$/, async ({ res, params, body }) => {
      const b = await parseJsonBody(body) as never as { accept?: boolean };
      const ok = app.kg.resolvePendingReview(params.id, b.accept === true);
      sendJson(res, ok ? 200 : 404, { ok });
    }],

    // ---- 审计 / 指标 / 会话恢复 ----
    ['GET', /^\/admin\/audit$/, async ({ res, query }) => {
      const date = query.get('date') ?? undefined;
      const type = (query.get('type') ?? undefined) as never;
      const limit = query.get('limit') ? Number(query.get('limit')) : undefined;
      sendJson(res, 200, app.audit.query({ date, type, limit }));
    }],
    ['GET', /^\/admin\/metrics$/, async ({ res }) =>
      sendJson(res, 200, { ...app.metrics.snapshot(), route_latency: app.metrics.summary('route_latency_ms'), ctx_latency: app.metrics.summary('ctx_build_ms') })],
    ['POST', /^\/admin\/sessions\/(?<id>.+)\/rebuild$/, async ({ res, params }) => sendJson(res, 200, app.rebuildSession(params.id))],
  ];

  const server = http.createServer(async (req, res) => {
    const url = new URL(req.url ?? '/', 'http://localhost');
    const path = url.pathname;
    for (const [method, re, handler] of routes) {
      if (req.method !== method) continue;
      const m = re.exec(path);
      if (!m) continue;
      try {
        await handler({
          req,
          res,
          params: m.groups ?? {},
          query: url.searchParams,
          body: () => readBody(req),
        });
      } catch (e) {
        if (e instanceof DispatchError) sendJson(res, e.status ?? 400, { error: e.message });
        else sendJson(res, 500, { error: (e as Error).message });
      }
      return;
    }
    sendJson(res, 404, { error: `no route: ${req.method} ${path}` });
  });

  server.on('upgrade', (req, socket, head) => {
    const url = new URL(req.url ?? '/', 'http://localhost');
    if (url.pathname !== '/agent/session') {
      socket.destroy();
      return;
    }
    wss.handleUpgrade(req, socket, head, (ws) => {
      wss.emit('connection', ws, req, url);
    });
  });

  wss.on('connection', (ws: WebSocket, _req: http.IncomingMessage, url: URL) => {
    const filterSession = url.searchParams.get('session_id');
    ws.send(JSON.stringify({
      type: 'hello',
      sessions: app.sessions.list().map((s) => ({
        session_id: s.session_id,
        minister_on_duty: s.minister_on_duty,
      })),
    }));
    (ws as WebSocket & { __filter?: string | null }).__filter = filterSession;
    ws.on('message', (data) => {
      // 客户端可发送 {"type":"ping"} 保活
      try {
        const msg = JSON.parse(String(data)) as { type?: string };
        if (msg.type === 'ping') ws.send(JSON.stringify({ type: 'pong', ts: Date.now() }));
      } catch {
        // 忽略非 JSON 帧
      }
    });
  });

  function broadcast(w: WebSocketServer, type: string, payload: unknown): void {
    const data = JSON.stringify({ type, payload, ts: Date.now() });
    for (const client of w.clients) {
      if (client.readyState !== WebSocket.OPEN) continue;
      const filter = (client as WebSocket & { __filter?: string | null }).__filter;
      const sid = (payload as { session_id?: string }).session_id;
      if (filter && sid && filter !== sid) continue;
      client.send(data);
    }
  }

  return {
    server,
    port: 0,
    close: () =>
      new Promise<void>((resolve) => {
        for (const c of wss.clients) c.close();
        server.close(() => resolve());
      }),
  };
}

export async function listen(app: App, port: number): Promise<HttpServerInfo> {
  const info = createServer(app);
  await new Promise<void>((resolve) => info.server.listen(port, () => resolve()));
  const addr = info.server.address();
  info.port = typeof addr === 'object' && addr ? addr.port : port;
  return info;
}
