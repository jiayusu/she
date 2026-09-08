import { assert, describe, test } from "vitest";

import {
  AppApiError,
  type DashboardSnapshot,
  type DeviceSettings,
  type ParentConstraints,
  type WeeklyReport,
} from "@/api/contracts";
import { AppModel } from "@/state/appModel";

function dashboardFixture(): DashboardSnapshot {
  return {
    contract_version: "1.0",
    generated_at: "2026-09-07T10:00:00Z",
    greeting: "早上好，苏妈妈",
    pet: { name: "小P", mood: "delighted", accessibility_label: "小P很开心" },
    highlight: { text: "“milk” 今天第一次主动出现", evidence_id: "evidence-milk-001" },
    task: { title: "把 “I want…” 说得更自然", subtitle: "冰箱星球的小任务", progress: 0.64, action_label: "查看今日探险" },
    metrics: { spontaneous_speaking_count: 6, unprompted_output_count: 3, new_words: ["milk", "open"] },
    device: { device_id: "rx5-demo-001", name: "小P 设备", online: false, battery_percent: 82 },
    mock: true,
  };
}

function reportFixture(): WeeklyReport {
  return {
    contract_version: "1.0",
    period_start: "2026-09-01",
    period_end: "2026-09-07",
    spontaneous_speaking_count: 32,
    prompted_speaking_count: 17,
    new_spontaneous_words: ["milk"],
    transferred_words: ["apple"],
    current_focus: "主动表达食物需求",
    scaffold_trend: "L3 → L2",
    evidence: [],
    mastery_updates: [],
    mock: true,
  };
}

function deviceFixture(volume = 58): DeviceSettings {
  return {
    contract_version: "1.0",
    device_id: "rx5-demo-001",
    name: "小P 设备",
    online: false,
    battery_percent: 82,
    volume,
    led_enabled: true,
    camera_enabled: true,
    raw_audio_upload_enabled: false,
    firmware_version: "demo-0.1.0",
    last_seen_at: "2026-09-07T10:00:00Z",
    mock: true,
  };
}

function constraintsFixture(): ParentConstraints {
  return {
    contract_version: "1.0",
    session_budget_seconds: 600,
    preferred_topics: ["animals", "food"],
    avoid_topics: [],
    next_day_context: "明天去动物园",
    teaching_pressure: "low",
    updated_at: "2026-09-07T10:00:00Z",
    mock: true,
  };
}

class MockApi {
  failure: AppApiError | null = null;
  patchFailure: AppApiError | null = null;
  dashboardPayload = dashboardFixture();
  device = deviceFixture();

  async dashboard() {
    if (this.failure) throw this.failure;
    return this.dashboardPayload;
  }

  async weeklyReport() {
    if (this.failure) throw this.failure;
    return reportFixture();
  }

  async deviceSettings() {
    if (this.failure) throw this.failure;
    return this.device;
  }

  async updateDeviceSettings(_deviceId: string, patch: { volume?: number; led_enabled?: boolean }) {
    if (this.patchFailure) throw this.patchFailure;
    return {
      ...this.device,
      ...(patch.volume === undefined ? {} : { volume: patch.volume }),
      ...(patch.led_enabled === undefined ? {} : { led_enabled: patch.led_enabled }),
    };
  }

  async updateParentConstraints(update: {
    session_budget_seconds: number;
    next_day_context: string;
  }) {
    if (this.failure) throw this.failure;
    return {
      ...constraintsFixture(),
      session_budget_seconds: update.session_budget_seconds,
      next_day_context: update.next_day_context,
    };
  }

  async requestPrivacyExport() {
    return {
      contract_version: "1.0",
      operation: "export",
      status: "accepted_demo_only",
      mock: true,
      store_mutated: false,
    };
  }

  async requestPrivacyErase() {
    return {
      contract_version: "1.0",
      operation: "erase",
      status: "accepted_demo_only",
      mock: true,
      store_mutated: false,
    };
  }
}

describe("AppModel behavior parity with the iOS view-model", () => {
  test("load moves from loading to ready with dashboard evidence", async () => {
    const model = new AppModel(new MockApi() as never);
    assert.equal(model.getState().phase, "idle");

    const load = model.load();
    assert.equal(model.getState().phase, "loading");
    await load;

    const state = model.getState();
    assert.equal(state.phase, "ready");
    assert.equal(state.dashboard?.pet.name, "小P");
    assert.equal(state.dashboard?.mock, true);
    assert.equal(state.deviceSettings?.device_id, "rx5-demo-001");
  });

  test("first-load failure lands in the calm offline state", async () => {
    const api = new MockApi();
    api.failure = new AppApiError("offline");
    const model = new AppModel(api as never);

    await model.load();

    const state = model.getState();
    assert.equal(state.phase, "offline");
    assert.equal(state.dashboard, null);
  });

  test("failed refresh keeps evidence and reports a refresh error", async () => {
    const api = new MockApi();
    const model = new AppModel(api as never);
    await model.load();
    const before = model.getState().dashboard;
    api.failure = new AppApiError("offline");

    await model.load();

    const state = model.getState();
    assert.equal(state.phase, "ready");
    assert.equal(state.dashboard, before);
    assert.equal(state.refreshError?.kind, "offline");
    assert.equal(state.transientError, null);
  });

  test("failed settings patch rolls back the optimistic change", async () => {
    const api = new MockApi();
    const model = new AppModel(api as never);
    await model.load();
    const original = model.getState().deviceSettings;
    api.patchFailure = new AppApiError("offline");

    await model.updateDeviceSettings({ volume: 12 });

    const state = model.getState();
    assert.deepEqual(state.deviceSettings, original);
    assert.equal(state.transientError?.kind, "offline");
  });

  test("parent constraints round-trip reports what was saved", async () => {
    const model = new AppModel(new MockApi() as never);
    const saved = await model.updateParentConstraints({
      session_budget_seconds: 900,
      preferred_topics: ["animals", "food"],
      avoid_topics: [],
      next_day_context: "明天去海洋馆",
      teaching_pressure: "low",
    });

    assert.equal(saved?.session_budget_seconds, 900);
    assert.equal(saved?.next_day_context, "明天去海洋馆");
    assert.equal(model.getState().parentConstraints, saved);
  });
});
