import assert from "node:assert/strict";
import { once } from "node:events";
import { afterEach, beforeEach, describe, test } from "node:test";
import WebSocket from "ws";

import { createGateway, type GatewayHandle } from "../src/app.js";


const baseEvent = {
  event_id: "11111111-1111-4111-8111-111111111111",
  contract_version: "1.0",
  device_id: "rx5-demo-001",
  session_id: "session-demo-001",
  sequence: 0,
  occurred_at: "2026-09-07T10:00:00Z",
  type: "hello",
  payload: { runtime_version: "0.1.0", capabilities: ["simulator"] },
};

async function nextJson(socket: WebSocket): Promise<any> {
  const [data] = await once(socket, "message");
  return JSON.parse(data.toString());
}

describe("device WebSocket sessions", () => {
  let gateway: GatewayHandle;
  let socket: WebSocket;

  beforeEach(async () => {
    gateway = await createGateway({ host: "127.0.0.1", port: 0 });
    socket = new WebSocket(`${gateway.wsUrl}/v1/device/session`);
    await once(socket, "open");
  });

  afterEach(async () => {
    socket.close();
    await once(socket, "close").catch(() => undefined);
    await gateway.close();
  });

  test("hello marks a device online and duplicate events are idempotent", async () => {
    socket.send(JSON.stringify(baseEvent));
    assert.equal((await nextJson(socket)).status, "accepted");
    assert.equal(gateway.sessions.snapshot("rx5-demo-001")?.online, true);

    socket.send(JSON.stringify(baseEvent));
    assert.equal((await nextJson(socket)).status, "duplicate");
    assert.equal(gateway.sessions.snapshot("rx5-demo-001")?.acceptedEvents, 1);
  });

  test("lower sequence and unsupported contract versions are rejected", async () => {
    socket.send(JSON.stringify({ ...baseEvent, sequence: 4 }));
    assert.equal((await nextJson(socket)).status, "accepted");

    socket.send(JSON.stringify({ ...baseEvent, event_id: "33333333-3333-4333-8333-333333333333", sequence: 3 }));
    assert.equal((await nextJson(socket)).error.code, "sequence_out_of_order");

    socket.send(JSON.stringify({ ...baseEvent, event_id: "44444444-4444-4444-8444-444444444444", contract_version: "2.0", sequence: 5 }));
    assert.equal((await nextJson(socket)).error.code, "contract_version_unsupported");
  });

  test("command acknowledgements correlate with pending commands", async () => {
    socket.send(JSON.stringify(baseEvent));
    await nextJson(socket);

    const pending = gateway.sessions.sendCommand("rx5-demo-001", {
      type: "speak",
      payload: { text: "Milk! Yum!" },
    });
    const command = await nextJson(socket);
    assert.equal(command.command_id, pending.command_id);

    socket.send(JSON.stringify({
      ...baseEvent,
      event_id: "55555555-5555-4555-8555-555555555555",
      sequence: 1,
      type: "command_ack",
      payload: { command_id: command.command_id, status: "completed", error_code: null },
    }));
    assert.equal((await nextJson(socket)).status, "accepted");
    assert.equal(gateway.sessions.snapshot("rx5-demo-001")?.pendingCommands, 0);
  });
});
