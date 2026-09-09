import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { createServer, type IncomingMessage } from "node:http";
import type { AddressInfo } from "node:net";
import path from "node:path";
import { afterEach, beforeEach, describe, test } from "node:test";

import { createGateway, type GatewayHandle } from "../src/app.js";


const contractRoot = path.resolve(import.meta.dirname, "../../../shared/contracts/v1");

type JsonRecord = Record<string, unknown>;
type StubResult = { status?: number; body: unknown };
type StubHandler = (
  request: IncomingMessage,
  body: unknown,
) => StubResult | Promise<StubResult>;

interface JsonStub {
  url: string;
  requests: Array<{ method: string; path: string; body: unknown }>;
  close(): Promise<void>;
}

async function fixture(directory: "valid" | "invalid", name: string): Promise<JsonRecord> {
  return JSON.parse(
    await readFile(path.join(contractRoot, "fixtures", directory, name), "utf8"),
  ) as JsonRecord;
}

async function jsonStub(handler: StubHandler): Promise<JsonStub> {
  const requests: JsonStub["requests"] = [];
  const server = createServer(async (request, response) => {
    const chunks: Buffer[] = [];
    for await (const chunk of request) chunks.push(Buffer.from(chunk));
    const raw = Buffer.concat(chunks).toString("utf8");
    const body = raw.length === 0 ? undefined : JSON.parse(raw) as unknown;
    requests.push({
      method: request.method ?? "GET",
      path: request.url ?? "/",
      body,
    });

    const result = await handler(request, body);
    const encoded = JSON.stringify(result.body);
    response.writeHead(result.status ?? 200, {
      "content-type": "application/json; charset=utf-8",
      "content-length": Buffer.byteLength(encoded),
    });
    response.end(encoded);
  });

  await new Promise<void>((resolve, reject) => {
    server.once("error", reject);
    server.listen(0, "127.0.0.1", resolve);
  });
  const address = server.address() as AddressInfo;
  return {
    url: `http://127.0.0.1:${address.port}`,
    requests,
    close: async () => {
      await new Promise<void>((resolve, reject) => {
        server.close((error) => error ? reject(error) : resolve());
      });
    },
  };
}

function storedRpgState(decision: JsonRecord, deliveryStatus: "completed" | "failed"): JsonRecord {
  return {
    revision: 4,
    latest: {
      turn_id: "rpg-turn-001",
      device_id: "rx5-demo-001",
      request: {
        utterance: "child-private-utterance",
        raw_asr_trace: "must-not-cross-the-gateway",
      },
      response: {
        rpg: decision,
        teaching_action: {
          action_id: "action-001",
          teaching_action: "ask",
          target_expression: "I want milk.",
          prompt_id: "collect_milk_s2",
        },
        internal_evidence: "must-not-cross-the-gateway",
      },
      delivery: { status: deliveryStatus },
    },
  };
}

describe("embodied RPG HTTP boundary", () => {
  let gateway: GatewayHandle;
  let director: JsonStub;
  let memory: JsonStub;
  let validDecision: JsonRecord;
  let directorResult: unknown;
  let memoryResult: unknown;

  beforeEach(async () => {
    validDecision = await fixture("valid", "rpg-decision.json");
    directorResult = { rpg: validDecision };
    memoryResult = storedRpgState(validDecision, "completed");
    director = await jsonStub(() => ({ body: directorResult }));
    memory = await jsonStub(() => ({ body: memoryResult }));
    gateway = await createGateway({
      host: "127.0.0.1",
      port: 0,
      directorUrl: director.url,
      memoryUrl: memory.url,
    });
  });

  afterEach(async () => {
    await gateway.close();
    await director.close();
    await memory.close();
  });

  test("direct rejects stale speech context and client-owned world state before forwarding", async () => {
    const invalidTurns = [
      await fixture("invalid", "rpg-turn-speech-stale-object.json"),
      await fixture("invalid", "rpg-turn-world-state.json"),
    ];

    for (const turn of invalidTurns) {
      const response = await fetch(`${gateway.url}/v1/rpg/direct`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(turn),
      });
      assert.equal(response.status, 400);
      assert.equal((await response.json()).error.code, "invalid_rpg_turn");
    }

    assert.equal(director.requests.length, 0);
  });

  test("direct fails closed when Director returns an invalid RPG decision", async () => {
    const validTurn = await fixture("valid", "rpg-turn.json");
    directorResult = {
      rpg: {
        ...validDecision,
        confirmed_object: null,
      },
    };

    const response = await fetch(`${gateway.url}/v1/rpg/direct`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(validTurn),
    });

    assert.equal(response.status, 502);
    assert.equal((await response.json()).error.code, "invalid_rpg_decision");
    assert.equal(director.requests.length, 1);
    assert.equal(director.requests[0]?.path, "/agent/direct");
  });

  test("state exposes only the child-safe quest summary and projects delivery phase", async () => {
    const completed = await fetch(
      `${gateway.url}/v1/rpg/state?child_id=child-demo&session_id=session-demo`,
    );
    assert.equal(completed.status, 200);
    const completedSummary = await completed.json();
    assert.equal(completedSummary.delivery_status, "completed");
    assert.equal(completedSummary.quest.phase, "awaiting_speech");
    assert.equal(completedSummary.quest.confirmed_object, "fridge");
    assert.equal("utterance" in completedSummary.quest, false);
    assert.equal("speech_act_evidence" in completedSummary.quest, false);
    assert.doesNotMatch(
      JSON.stringify(completedSummary),
      /child-private-utterance|raw_asr_trace|internal_evidence|source_turn_id/,
    );

    memoryResult = storedRpgState(validDecision, "failed");
    const failed = await fetch(
      `${gateway.url}/v1/rpg/state?child_id=child-demo&session_id=session-demo`,
    );
    assert.equal(failed.status, 200);
    const failedSummary = await failed.json();
    assert.equal(failedSummary.delivery_status, "failed");
    assert.equal(failedSummary.quest.phase, "delivery_failed");
    assert.equal(failedSummary.quest.confirmed_object, "fridge");
  });

  test("state rejects unknown, malformed, and duplicate identity query parameters", async () => {
    const invalidQueries = [
      "child_id=child-demo",
      "child_id=child-demo&session_id=session-demo&debug=true",
      "child_id=child-a&child_id=child-b&session_id=session-demo",
      "child_id=child-demo&session_id=session-demo&turn_id=turn-a&turn_id=turn-b",
      "child_id=child%20demo&session_id=session-demo",
    ];

    for (const query of invalidQueries) {
      const response = await fetch(`${gateway.url}/v1/rpg/state?${query}`);
      assert.equal(response.status, 400);
      assert.equal((await response.json()).error.code, "invalid_rpg_state_query");
    }

    assert.equal(memory.requests.length, 0);
  });
});
