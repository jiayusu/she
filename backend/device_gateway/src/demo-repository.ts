import { readFile } from "node:fs/promises";
import path from "node:path";

import { CONTRACT_VERSION, type JsonObject } from "./types.js";


function clone<T>(value: T): T {
  return structuredClone(value);
}

async function fixture(contractRoot: string, name: string): Promise<JsonObject> {
  const content = await readFile(path.join(contractRoot, "fixtures", "valid", name), "utf8");
  return JSON.parse(content) as JsonObject;
}

export class DemoRepository {
  private constructor(
    private readonly dashboardValue: JsonObject,
    private readonly weeklyReportValue: JsonObject,
    private deviceValue: JsonObject,
    private constraintsValue: JsonObject,
  ) {}

  static async load(contractRoot: string, learningReportUrl?: string): Promise<DemoRepository> {
    const report = await loadLearningReport(contractRoot, learningReportUrl);
    return new DemoRepository(
      await fixture(contractRoot, "dashboard-snapshot.json"),
      report,
      await fixture(contractRoot, "device-settings.json"),
      await fixture(contractRoot, "parent-constraints.json"),
    );
  }

  dashboard(): JsonObject {
    return clone(this.dashboardValue);
  }

  weeklyReport(): JsonObject {
    return clone(this.weeklyReportValue);
  }

  device(deviceId: string): JsonObject | undefined {
    return this.deviceValue.device_id === deviceId ? clone(this.deviceValue) : undefined;
  }

  candidateDevice(patch: JsonObject): JsonObject {
    return { ...this.deviceValue, ...patch, contract_version: CONTRACT_VERSION, mock: true };
  }

  saveDevice(value: JsonObject): JsonObject {
    this.deviceValue = clone(value);
    return clone(this.deviceValue);
  }

  candidateConstraints(value: JsonObject, now: string): JsonObject {
    return {
      ...value,
      contract_version: CONTRACT_VERSION,
      updated_at: now,
      mock: true,
    };
  }

  saveConstraints(value: JsonObject): JsonObject {
    this.constraintsValue = clone(value);
    return clone(this.constraintsValue);
  }

  constraints(): JsonObject {
    return clone(this.constraintsValue);
  }
}

async function loadLearningReport(contractRoot: string, url?: string): Promise<JsonObject> {
  const fallback = await fixture(contractRoot, "weekly-report.json");
  if (!url) return fallback;
  try {
    const response = await fetch(url, { headers: { accept: "application/json" } });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const value = await response.json() as JsonObject;
    if (value.contract_version !== CONTRACT_VERSION || !Array.isArray(value.evidence)) throw new Error("incompatible learning report");
    return value;
  } catch (error) {
    console.warn(`[gateway] learning report service unavailable; using labelled fallback: ${(error as Error).message}`);
    return fallback;
  }
}
