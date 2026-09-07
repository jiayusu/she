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

  static async load(contractRoot: string): Promise<DemoRepository> {
    return new DemoRepository(
      await fixture(contractRoot, "dashboard-snapshot.json"),
      await fixture(contractRoot, "weekly-report.json"),
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
