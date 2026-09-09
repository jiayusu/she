import assert from "node:assert/strict";
import { afterEach, beforeEach, describe, test } from "node:test";

import { createGateway, type GatewayHandle } from "../src/app.js";


describe("parent control HTTP API", () => {
  let gateway: GatewayHandle;

  beforeEach(async () => {
    gateway = await createGateway({ host: "127.0.0.1", port: 0 });
  });

  afterEach(async () => {
    await gateway.close();
  });

  test("health and dashboard expose contract v1 demo state", async () => {
    const health = await fetch(`${gateway.url}/health`).then((response) => response.json());
    assert.deepEqual(health, { status: "ok", contract_version: "1.0" });

    const dashboard = await fetch(`${gateway.url}/v1/dashboard`).then((response) => response.json());
    assert.equal(dashboard.contract_version, "1.0");
    assert.equal(dashboard.mock, true);
    assert.deepEqual(Object.keys(dashboard.metrics).sort(), [
      "new_words",
      "spontaneous_speaking_count",
      "unprompted_output_count",
    ]);
  });

  test("device settings accept bounded updates and reject invalid volume", async () => {
    const valid = await fetch(`${gateway.url}/v1/devices/rx5-demo-001`, {
      method: "PATCH",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ volume: 72, led_enabled: false }),
    });
    assert.equal(valid.status, 200);
    const updated = await valid.json();
    assert.equal(updated.volume, 72);
    assert.equal(updated.led_enabled, false);

    const invalid = await fetch(`${gateway.url}/v1/devices/rx5-demo-001`, {
      method: "PATCH",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ volume: 101 }),
    });
    assert.equal(invalid.status, 400);
    assert.equal((await invalid.json()).error.code, "invalid_device_settings");
  });

  test("parent constraints update without permitting mastery fields", async () => {
    const response = await fetch(`${gateway.url}/v1/parent-constraints`, {
      method: "PUT",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        session_budget_seconds: 480,
        preferred_topics: ["dinosaurs"],
        avoid_topics: [],
        next_day_context: "",
        teaching_pressure: "low",
      }),
    });
    assert.equal(response.status, 200);
    assert.equal((await response.json()).session_budget_seconds, 480);

    const forbidden = await fetch(`${gateway.url}/v1/parent-constraints`, {
      method: "PUT",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ mastery: { apple: "TRANSFERRED" } }),
    });
    assert.equal(forbidden.status, 400);
  });

  test("privacy operations explicitly remain mock operations", async () => {
    for (const route of ["export", "erase"]) {
      const response = await fetch(`${gateway.url}/v1/privacy/${route}`, { method: "POST" });
      assert.equal(response.status, 202);
      const body = await response.json();
      assert.equal(body.mock, true);
      assert.equal(body.store_mutated, false);
      assert.equal(body.contract_version, "1.0");
    }
  });

  test("unknown routes and malformed JSON use structured errors", async () => {
    const missing = await fetch(`${gateway.url}/missing`);
    assert.equal(missing.status, 404);
    assert.equal((await missing.json()).error.code, "not_found");

    const malformed = await fetch(`${gateway.url}/v1/parent-constraints`, {
      method: "PUT",
      headers: { "content-type": "application/json" },
      body: "{",
    });
    assert.equal(malformed.status, 400);
    assert.equal((await malformed.json()).error.code, "invalid_json");
  });
});

describe("browser CORS allowlist", () => {
  let gateway: GatewayHandle;

  afterEach(async () => {
    await gateway.close();
  });

  test("allowed origin receives preflight and echoed CORS headers", async () => {
    gateway = await createGateway({
      host: "127.0.0.1",
      port: 0,
      allowedOrigins: ["http://localhost:5173"],
    });

    const preflight = await fetch(`${gateway.url}/v1/dashboard`, {
      method: "OPTIONS",
      headers: {
        origin: "http://localhost:5173",
        "access-control-request-method": "PATCH",
      },
    });
    assert.equal(preflight.status, 204);
    assert.equal(preflight.headers.get("access-control-allow-origin"), "http://localhost:5173");
    assert.match(preflight.headers.get("access-control-allow-methods") ?? "", /PATCH/);

    const dashboard = await fetch(`${gateway.url}/v1/dashboard`, {
      headers: { origin: "http://localhost:5173" },
    });
    assert.equal(dashboard.status, 200);
    assert.equal(dashboard.headers.get("access-control-allow-origin"), "http://localhost:5173");
  });

  test("disallowed origin gets no allow-origin header and CORS stays opt-in", async () => {
    gateway = await createGateway({
      host: "127.0.0.1",
      port: 0,
      allowedOrigins: ["http://localhost:5173"],
    });

    const stranger = await fetch(`${gateway.url}/v1/dashboard`, {
      headers: { origin: "http://evil.example" },
    });
    assert.equal(stranger.status, 200);
    assert.equal(stranger.headers.get("access-control-allow-origin"), null);
    assert.equal(stranger.headers.get("vary"), "Origin");

    const optIn = await createGateway({ host: "127.0.0.1", port: 0 });
    try {
      const legacy = await fetch(`${optIn.url}/v1/dashboard`, {
        headers: { origin: "http://localhost:5173" },
      });
      assert.equal(legacy.status, 200);
      assert.equal(legacy.headers.get("access-control-allow-origin"), null);
      assert.equal(legacy.headers.get("vary"), null);
    } finally {
      await optIn.close();
    }
  });
});
