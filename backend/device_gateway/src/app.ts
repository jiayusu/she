import { createServer, type IncomingMessage, type ServerResponse } from "node:http";
import type { AddressInfo } from "node:net";

import { WebSocketServer } from "ws";

import { ContractValidators, defaultContractRoot } from "./contracts.js";
import { DemoRepository } from "./demo-repository.js";
import { DeviceSessionRegistry } from "./device-sessions.js";
import { DigitalTwinRegistry } from "./digital-twin.js";
import { CONTRACT_VERSION, type JsonObject } from "./types.js";
import { LearningDelivery, service, ServiceError } from './learning.js';


export interface GatewayOptions {
  host?: string;
  port?: number;
  contractRoot?: string;
  learningReportUrl?: string;
  deviceToken?: string;
  memoryUrl?: string;
  directorUrl?: string;
  interactionUrl?: string;
  /** Browser origins allowed to call the parent HTTP API cross-origin. Empty/omitted disables CORS entirely. */
  allowedOrigins?: string[];
}

export interface GatewayHandle {
  url: string;
  wsUrl: string;
  port: number;
  sessions: DeviceSessionRegistry;
  twins: DigitalTwinRegistry;
  close(): Promise<void>;
}

function reply(response: ServerResponse, status: number, payload: unknown): void {
  const body = JSON.stringify(payload);
  response.writeHead(status, {
    "content-type": "application/json; charset=utf-8",
    "content-length": Buffer.byteLength(body),
  });
  response.end(body);
}

function fail(response: ServerResponse, status: number, code: string, message: string): void {
  reply(response, status, { contract_version: CONTRACT_VERSION, error: { code, message } });
}

async function readJson(request: IncomingMessage): Promise<JsonObject> {
  const chunks: Buffer[] = [];
  let size = 0;
  for await (const chunk of request) {
    const value = Buffer.from(chunk);
    size += value.length;
    if (size > 64 * 1024) throw new Error("payload_too_large");
    chunks.push(value);
  }
  const parsed = JSON.parse(Buffer.concat(chunks).toString("utf8") || "{}");
  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) throw new Error("invalid_json");
  return parsed as JsonObject;
}

function isObject(value: unknown): value is JsonObject {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function readRpgStateQuery(searchParams: URLSearchParams): {
  child_id: string;
  session_id: string;
  turn_id?: string;
} {
  const allowed = new Set(["child_id", "session_id", "turn_id"]);
  if ([...searchParams.keys()].some((key) => !allowed.has(key))) {
    throw new ServiceError("invalid_rpg_state_query", 400);
  }
  const readIdentity = (key: "child_id" | "session_id" | "turn_id", required: boolean) => {
    const values = searchParams.getAll(key);
    if ((required && values.length !== 1) || (!required && values.length > 1)) {
      throw new ServiceError("invalid_rpg_state_query", 400);
    }
    const value = values[0];
    if (value === undefined && !required) return undefined;
    if (typeof value !== "string" || !/^[A-Za-z0-9_-]{1,80}$/.test(value)) {
      throw new ServiceError("invalid_rpg_state_query", 400);
    }
    return value;
  };
  const child_id = readIdentity("child_id", true)!;
  const session_id = readIdentity("session_id", true)!;
  const turn_id = readIdentity("turn_id", false);
  return turn_id === undefined ? { child_id, session_id } : { child_id, session_id, turn_id };
}

function rpgQuestSummary(state: unknown, requestedTurnId?: string): JsonObject {
  if (!isObject(state) || !Number.isInteger(state.revision) || (state.revision as number) < 0) {
    throw new ServiceError("invalid_rpg_state", 502);
  }
  const selected = requestedTurnId === undefined ? state.latest : state.replay;
  if (requestedTurnId !== undefined && !isObject(selected)) {
    throw new ServiceError("rpg_turn_not_found", 404);
  }
  if (!isObject(selected)) {
    return {
      contract_version: CONTRACT_VERSION,
      learning_revision: state.revision,
      turn_id: null,
      delivery_status: null,
      quest: null,
    };
  }
  const response = selected.response;
  const delivery = selected.delivery;
  if (!isObject(response) || !isObject(delivery) || typeof selected.turn_id !== "string") {
    throw new ServiceError("invalid_rpg_state", 502);
  }
  if (!isObject(response.rpg)) {
    return {
      contract_version: CONTRACT_VERSION,
      learning_revision: state.revision,
      turn_id: selected.turn_id,
      delivery_status: typeof delivery.status === "string" ? delivery.status : null,
      quest: null,
    };
  }
  const action = response.teaching_action;
  if (!isObject(action)) throw new ServiceError("invalid_rpg_state", 502);
  let effectivePhase = response.rpg.phase;
  if (effectivePhase === "presenting" && delivery.status === "completed") {
    effectivePhase = "awaiting_speech";
  } else if (effectivePhase === "presenting"
    && (delivery.status === "failed" || delivery.status === "expired")) {
    effectivePhase = "delivery_failed";
  }
  return {
    contract_version: CONTRACT_VERSION,
    learning_revision: state.revision,
    turn_id: selected.turn_id,
    delivery_status: typeof delivery.status === "string" ? delivery.status : null,
    quest: {
      seed_id: response.rpg.seed_id,
      seed_version: response.rpg.seed_version,
      node_id: response.rpg.node_id,
      phase: effectivePhase,
      world_revision: response.rpg.world_revision,
      inventory: response.rpg.inventory,
      completed_nodes: response.rpg.completed_nodes,
      world_role: response.rpg.world_role,
      action_kind: action.teaching_action,
      target_expression: action.target_expression,
      prompt_id: typeof action.prompt_id === "string" ? action.prompt_id : null,
      feedback_id: response.rpg.feedback_id,
      next_quest_id: response.rpg.next_quest_id,
    },
  };
}

const CORS_METHODS = "GET, PATCH, PUT, POST, OPTIONS";
const CORS_HEADERS = "content-type, authorization";

/**
 * CORS stays opt-in: without an explicit allowlist the gateway behaves exactly as
 * before (no CORS headers, browsers blocked). Allowed browser origins get their
 * own Origin echoed back; every other response carries `Vary: Origin` so caches
 * never mix allowlisted and non-allowlisted variants.
 */
function corsHeadersFor(origin: string | undefined, allowedOrigins: Set<string>): Record<string, string> {
  if (allowedOrigins.size === 0) return {};
  if (origin && allowedOrigins.has(origin)) {
    return {
      "access-control-allow-origin": origin,
      "access-control-allow-methods": CORS_METHODS,
      "access-control-allow-headers": CORS_HEADERS,
      "access-control-max-age": "600",
    };
  }
  return { vary: "Origin" };
}

export async function createGateway(options: GatewayOptions = {}): Promise<GatewayHandle> {
  const host = options.host ?? "127.0.0.1";
  const deviceToken = options.deviceToken ?? process.env.SHE_DEVICE_TOKEN;
  const contractRoot = options.contractRoot ?? defaultContractRoot();
  const validators = await ContractValidators.load(contractRoot);
  const repository = await DemoRepository.load(contractRoot, options.learningReportUrl ?? process.env.SHE_LEARNING_REPORT_URL);
  const twins = new DigitalTwinRegistry();
  let learning: LearningDelivery | undefined;
  const sessions = new DeviceSessionRegistry(validators, undefined, {
    onEvent: (event, snapshot) => { twins.onEvent(event, snapshot); void learning?.acknowledge(event); },
    onCommand: (command) => twins.onCommand(command),
    onClose: (deviceId) => twins.onClosed(deviceId),
  });
  const memoryUrl = options.memoryUrl ?? process.env.SHE_MEMORY_URL;
  const directorUrl = options.directorUrl ?? process.env.SHE_DIRECTOR_URL;
  const interactionUrl = options.interactionUrl ?? process.env.SHE_INTERACTION_URL;
  if(memoryUrl && interactionUrl) learning = new LearningDelivery(memoryUrl,interactionUrl,sessions);
  const webSockets = new WebSocketServer({ noServer: true });
  sessions.attach(webSockets);
  const allowedOrigins = new Set(options.allowedOrigins ?? []);

  const server = createServer(async (request, response) => {
    const url = new URL(request.url ?? "/", `http://${request.headers.host ?? "localhost"}`);
    const deviceMatch = url.pathname.match(/^\/v1\/devices\/([^/]+)$/);
    const corsHeaders = corsHeadersFor(request.headers.origin, allowedOrigins);
    for (const [name, value] of Object.entries(corsHeaders)) response.setHeader(name, value);

    try {
      if (request.method === "OPTIONS") {
        response.writeHead(204, { "content-length": 0 });
        response.end();
        return;
      }
      if (request.method === "GET" && url.pathname === "/health") {
        reply(response, 200, { status: "ok", contract_version: CONTRACT_VERSION });
      } else if (request.method === "POST" && url.pathname === "/v1/rpg/direct") {
        if (!directorUrl) {
          fail(response, 503, "rpg_director_unavailable", "The RPG Director is not configured.");
          return;
        }
        const value = await readJson(request);
        if (!validators.rpgTurn(value).ok) {
          fail(response, 400, "invalid_rpg_turn", "RPG turn does not match contract v1.");
          return;
        }
        const result = await service(`${directorUrl}/agent/direct`, value);
        if (!isObject(result) || !validators.rpgDecision(result.rpg).ok) {
          fail(response, 502, "invalid_rpg_decision", "Director returned an invalid RPG decision.");
          return;
        }
        reply(response, 200, result);
      } else if (request.method === "GET" && url.pathname === "/v1/rpg/state") {
        if (!memoryUrl) {
          fail(response, 503, "rpg_memory_unavailable", "The RPG state service is not configured.");
          return;
        }
        const query = readRpgStateQuery(url.searchParams);
        const memoryQuery = new URLSearchParams({
          child_id: query.child_id,
          session_id: query.session_id,
        });
        if (query.turn_id !== undefined) memoryQuery.set("turn_id", query.turn_id);
        const state = await service(`${memoryUrl}/memory/learning/state?${memoryQuery}`);
        if (isObject(state) && isObject((query.turn_id === undefined ? state.latest : state.replay))) {
          const selected = query.turn_id === undefined ? state.latest : state.replay;
          if (isObject(selected) && isObject(selected.response) && selected.response.rpg !== undefined
            && !validators.rpgDecision(selected.response.rpg).ok) {
            fail(response, 502, "invalid_rpg_state", "Stored RPG state does not match contract v1.");
            return;
          }
        }
        const summary = rpgQuestSummary(state, query.turn_id);
        if (!validators.rpgQuestSummary(summary).ok) {
          fail(response, 502, "invalid_rpg_summary", "RPG quest projection does not match contract v1.");
          return;
        }
        reply(response, 200, summary);
      } else if (request.method === 'POST' && url.pathname === '/v1/learning/direct' && directorUrl) {
        reply(response,200,await service(`${directorUrl}/agent/direct`,await readJson(request)));
      } else if (request.method === 'POST' && url.pathname === '/v1/learning/execute' && learning) {
        reply(response,202,await learning.deliver(await readJson(request)));
      } else if (request.method === 'GET' && url.pathname === '/v1/learning/state' && memoryUrl) {
        reply(response,200,await service(`${memoryUrl}/memory/learning/state?${url.searchParams}`));
      } else if (request.method === "GET" && url.pathname === "/v1/dashboard") {
        reply(response, 200, repository.dashboard());
      } else if (request.method === "GET" && url.pathname === "/v1/reports/weekly") {
        reply(response, 200, repository.weeklyReport());
      } else if (request.method === "GET" && url.pathname.match(/^\/v1\/devices\/[^/]+\/twin$/)) {
        const deviceId = decodeURIComponent(url.pathname.split("/")[3] ?? "");
        const twin = twins.get(deviceId);
        if (twin) reply(response, 200, twin);
        else if (repository.device(deviceId)) reply(response, 200, {
          device_id: deviceId, online: false, session_id: null, capabilities: [], capability_errors: {},
          runtime: { firmware_version: null, runtime_version: null },
          telemetry: { battery_percent: null, temperature_c: null, network: null },
          privacy: { camera_enabled: true, raw_audio_upload_enabled: false },
          last_event: null, last_command: null, updated_at: new Date(0).toISOString(),
        });
        else fail(response, 404, "device_not_found", "Device does not exist.");
      } else if (request.method === "GET" && url.pathname.match(/^\/v1\/devices\/[^/]+\/timeline$/)) {
        const deviceId = decodeURIComponent(url.pathname.split("/")[3] ?? "");
        if (!repository.device(deviceId) && !twins.get(deviceId)) fail(response, 404, "device_not_found", "Device does not exist.");
        else reply(response, 200, { device_id: deviceId, items: twins.timeline(deviceId, Number(url.searchParams.get("limit") ?? "100")) });
      } else if (request.method === "POST" && url.pathname.match(/^\/v1\/devices\/[^/]+\/commands$/)) {
        const deviceId = decodeURIComponent(url.pathname.split("/")[3] ?? "");
        const value = await readJson(request);
        const type = value.type;
        const payload = value.payload;
        if (typeof type !== "string" || !payload || typeof payload !== "object" || Array.isArray(payload)) {
          fail(response, 400, "invalid_command", "Command requires a type and object payload.");
          return;
        }
        try {
          const command = sessions.sendCommand(deviceId, { type: type as never, payload: payload as JsonObject });
          reply(response, 202, command);
        } catch (caught) {
          const reason = caught instanceof Error ? caught.message : "command_failed";
          fail(response, reason === "device_offline" ? 409 : 400, reason, "Command could not be issued.");
        }
      } else if (request.method === "GET" && deviceMatch) {
        const device = repository.device(decodeURIComponent(deviceMatch[1] ?? ""));
        if (device) reply(response, 200, device);
        else fail(response, 404, "device_not_found", "Device does not exist.");
      } else if (request.method === "PATCH" && deviceMatch) {
        const deviceId = decodeURIComponent(deviceMatch[1] ?? "");
        if (!repository.device(deviceId)) {
          fail(response, 404, "device_not_found", "Device does not exist.");
          return;
        }
        const patch = await readJson(request);
        const allowed = new Set(["volume", "led_enabled", "camera_enabled", "raw_audio_upload_enabled"]);
        if (Object.keys(patch).some((key) => !allowed.has(key))) {
          fail(response, 400, "invalid_device_settings", "Only parent-controlled settings may be changed.");
          return;
        }
        const candidate = repository.candidateDevice(patch);
        if (!validators.deviceSettings(candidate).ok) {
          fail(response, 400, "invalid_device_settings", "Device settings are outside the allowed range.");
          return;
        }
        reply(response, 200, repository.saveDevice(candidate));
      } else if (request.method === "GET" && url.pathname === "/v1/parent-constraints") {
        reply(response, 200, repository.constraints());
      } else if (request.method === "PUT" && url.pathname === "/v1/parent-constraints") {
        const value = await readJson(request);
        const candidate = repository.candidateConstraints(value, new Date().toISOString());
        if (!validators.parentConstraints(candidate).ok) {
          fail(response, 400, "invalid_parent_constraints", "Parent constraints do not match contract v1.");
          return;
        }
        reply(response, 200, repository.saveConstraints(candidate));
      } else if (request.method === "POST" && ["/v1/privacy/export", "/v1/privacy/erase"].includes(url.pathname)) {
        reply(response, 202, {
          contract_version: CONTRACT_VERSION,
          operation: url.pathname.endsWith("erase") ? "erase" : "export",
          status: "accepted_demo_only",
          mock: true,
          store_mutated: false,
        });
      } else {
        fail(response, 404, "not_found", "Route not found.");
      }
    } catch (caught) {
      if(caught instanceof ServiceError) {
        fail(response,caught.status,caught.message,'Learning operation could not complete. Retry using the same turn ID.');
        return;
      }
      const code = caught instanceof Error && caught.message === "payload_too_large" ? "payload_too_large" : "invalid_json";
      fail(response, code === "payload_too_large" ? 413 : 400, code, "Request body could not be accepted.");
    }
  });

  server.on("upgrade", (request, socket, head) => {
    const url = new URL(request.url ?? "/", `http://${request.headers.host ?? "localhost"}`);
    if (url.pathname !== "/v1/device/session") {
      socket.destroy();
      return;
    }
    if (deviceToken) {
      const authorization = request.headers.authorization;
      if (authorization !== `Bearer ${deviceToken}`) {
        socket.write("HTTP/1.1 401 Unauthorized\r\nConnection: close\r\n\r\n");
        socket.destroy();
        return;
      }
    }
    webSockets.handleUpgrade(request, socket, head, (webSocket) => webSockets.emit("connection", webSocket, request));
  });

  await new Promise<void>((resolve, reject) => {
    server.once("error", reject);
    server.listen(options.port ?? 8788, host, resolve);
  });
  const address = server.address() as AddressInfo;

  return {
    url: `http://${host}:${address.port}`,
    wsUrl: `ws://${host}:${address.port}`,
    port: address.port,
    sessions,
    twins,
    close: async () => {
      for (const client of webSockets.clients) client.terminate();
      webSockets.close();
      await new Promise<void>((resolve, reject) => server.close((error) => error ? reject(error) : resolve()));
    },
  };
}
