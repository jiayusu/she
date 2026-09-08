import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { resolve } from "node:path";

import { assert, describe, test } from "vitest";

import {
  AppApiError,
  decodeDashboardSnapshot,
  decodeDeviceSettings,
  decodeParentConstraints,
  decodePrivacyOperation,
  decodeWeeklyReport,
} from "@/api/contracts";

const fixturesRoot = resolve(fileURLToPath(import.meta.url), "../../../../shared/contracts/v1/fixtures");

function fixture(path: string): unknown {
  return JSON.parse(readFileSync(resolve(fixturesRoot, path), "utf8")) as unknown;
}

describe("contract decoding against canonical fixtures", () => {
  test("dashboard decodes canonical snake_case payload", () => {
    const dashboard = decodeDashboardSnapshot(fixture("valid/dashboard-snapshot.json"));
    assert.equal(dashboard.contract_version, "1.0");
    assert.equal(dashboard.metrics.spontaneous_speaking_count, 6);
    assert.equal(dashboard.metrics.unprompted_output_count, 3);
    assert.deepEqual(dashboard.metrics.new_words, ["milk", "open"]);
    assert.equal(dashboard.device.battery_percent, 82);
    assert.equal(dashboard.pet.name, "小P");
    assert.equal(dashboard.mock, true);
  });

  test("weekly report decodes evidence and mastery updates", () => {
    const report = decodeWeeklyReport(fixture("valid/weekly-report.json"));
    assert.equal(report.evidence[0]?.kind, "spontaneous");
    assert.equal(report.mastery_updates[0]?.from, "PROMPTED_OUTPUT");
    assert.equal(report.mastery_updates[0]?.to, "SPONTANEOUS_OUTPUT");
    assert.deepEqual(report.transferred_words, ["apple"]);
    assert.equal(report.mock, true);
  });

  test("device settings and parent constraints decode demo state", () => {
    const device = decodeDeviceSettings(fixture("valid/device-settings.json"));
    assert.equal(device.volume, 58);
    assert.equal(device.led_enabled, true);
    assert.equal(device.raw_audio_upload_enabled, false);

    const constraints = decodeParentConstraints(fixture("valid/parent-constraints.json"));
    assert.equal(constraints.teaching_pressure, "low");
    assert.equal(constraints.session_budget_seconds, 600);
  });

  test("future contract version is rejected as incompatible", () => {
    const payload = { ...(fixture("valid/dashboard-snapshot.json") as Record<string, unknown>) };
    payload.contract_version = "2.0";
    assert.throws(() => decodeDashboardSnapshot(payload), AppApiError);
    try {
      decodeDashboardSnapshot(payload);
    } catch (error) {
      assert.equal((error as AppApiError).kind, "incompatible_contract");
    }
  });

  test("shape drift is rejected as invalid_response", () => {
    assert.throws(
      () => decodeDashboardSnapshot({ contract_version: "1.0", greeting: 42 }),
      AppApiError,
    );
    assert.throws(
      () => decodeWeeklyReport({
        contract_version: "1.0",
        evidence: [{ kind: "hallucinated" }],
      }),
      AppApiError,
    );
    assert.throws(() => decodePrivacyOperation({ contract_version: "1.0", mock: "yes" }), AppApiError);
  });
});
