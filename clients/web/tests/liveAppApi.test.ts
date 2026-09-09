import { fileURLToPath } from "node:url";
import { resolve } from "node:path";
import { readFileSync } from "node:fs";

import { afterAll, beforeAll, describe, test } from "vitest";
import assert from "node:assert/strict";

import { createGateway, type GatewayHandle } from "../../../backend/device_gateway/src/app.js";
import { LiveAppApi } from "@/api/appApi";
import { AppApiError } from "@/api/contracts";

const repoRoot = resolve(fileURLToPath(import.meta.url), "../../../..");

describe("LiveAppApi against the real Device Gateway", () => {
  let gateway: GatewayHandle;

  beforeAll(async () => {
    gateway = await createGateway({
      host: "127.0.0.1",
      port: 0,
      contractRoot: resolve(repoRoot, "shared/contracts/v1"),
      allowedOrigins: ["http://localhost:5173"],
    });
  });

  afterAll(async () => {
    await gateway.close();
  });

  test("saved family plan can be read back", async () => {
    const response = await fetch(`${gateway.url}/v1/parent-constraints`);
    assert.equal(response.status, 200);
    assert.equal((await response.json()).contract_version, "1.0");
  });

  test("dashboard, weekly report, and device settings decode from live responses", async () => {
    const api = new LiveAppApi({ baseUrl: gateway.url });
    const dashboard = await api.dashboard();
    assert.equal(dashboard.contract_version, "1.0");
    assert.equal(dashboard.pet.name, "小P");
    assert.ok(dashboard.device.device_id.length > 0);

    const report = await api.weeklyReport();
    assert.match(report.period_start, /^\d{4}-\d{2}-\d{2}$/);

    const settings = await api.deviceSettings(dashboard.device.device_id);
    assert.ok(settings.volume >= 0 && settings.volume <= 100);
  });

  test("device settings patch round-trips through the gateway", async () => {
    const api = new LiveAppApi({ baseUrl: gateway.url });
    const dashboard = await api.dashboard();
    const updated = await api.updateDeviceSettings(dashboard.device.device_id, {
      volume: 47,
      led_enabled: false,
    });
    assert.equal(updated.volume, 47);
    assert.equal(updated.led_enabled, false);
  });

  test("parent constraints and privacy demo operations round-trip", async () => {
    const api = new LiveAppApi({ baseUrl: gateway.url });
    const constraints = await api.updateParentConstraints({
      session_budget_seconds: 900,
      preferred_topics: ["animals", "food"],
      avoid_topics: [],
      next_day_context: "明天去海洋馆",
      teaching_pressure: "low",
    });
    assert.equal(constraints.session_budget_seconds, 900);
    assert.equal(constraints.mock, true);

    const exported = await api.requestPrivacyExport();
    assert.equal(exported.operation, "export");
    assert.equal(exported.store_mutated, false);
  });

  test("gateway error envelope maps to a server AppApiError", async () => {
    const api = new LiveAppApi({ baseUrl: gateway.url });
    try {
      await api.deviceSettings("rx5-missing-999");
      assert.fail("expected deviceSettings to fail");
    } catch (error) {
      assert.ok(error instanceof AppApiError);
      assert.equal(error.kind, "server");
      assert.equal(error.serverCode, "device_not_found");
    }
  });

  test("offline network failure maps to the offline error kind", async () => {
    const api = new LiveAppApi({ baseUrl: "http://127.0.0.1:1", timeoutMs: 250 });
    try {
      await api.dashboard();
      assert.fail("expected dashboard to fail");
    } catch (error) {
      assert.ok(error instanceof AppApiError);
      assert.equal(error.kind, "offline");
    }
  });

  test("quest state URL-encodes the explicitly supplied demo identity", async () => {
    const payload = readFileSync(
      resolve(repoRoot, "shared/contracts/v1/fixtures/valid/rpg-quest-summary.json"),
      "utf8",
    );
    let requestedUrl = "";
    const fetchImpl = (async (input: RequestInfo | URL) => {
      requestedUrl = String(input);
      return new Response(payload, {
        status: 200,
        headers: { "content-type": "application/json" },
      });
    }) as typeof fetch;
    const api = new LiveAppApi({ baseUrl: "https://gateway.example", fetchImpl });

    const summary = await api.questState("child/demo", "session?demo");

    assert.equal(
      requestedUrl,
      "https://gateway.example/v1/rpg/state?child_id=child%2Fdemo&session_id=session%3Fdemo",
    );
    assert.equal(summary.quest?.node_id, "find_red_cup");
  });
});
