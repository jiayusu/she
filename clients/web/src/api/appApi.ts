import {
  AppApiError,
  decodeDashboardSnapshot,
  decodeDeviceSettings,
  decodeParentConstraints,
  decodePrivacyOperation,
  decodeWeeklyReport,
  encodeDeviceSettingsPatch,
  encodeParentConstraintsUpdate,
  type DashboardSnapshot,
  type DeviceSettings,
  type DeviceSettingsPatch,
  type ParentConstraints,
  type ParentConstraintsUpdate,
  type PrivacyOperation,
  type WeeklyReport,
} from "./contracts";

export interface AppApi {
  dashboard(): Promise<DashboardSnapshot>;
  weeklyReport(): Promise<WeeklyReport>;
  deviceSettings(deviceId: string): Promise<DeviceSettings>;
  updateDeviceSettings(deviceId: string, patch: DeviceSettingsPatch): Promise<DeviceSettings>;
  updateParentConstraints(update: ParentConstraintsUpdate): Promise<ParentConstraints>;
  requestPrivacyExport(): Promise<PrivacyOperation>;
  requestPrivacyErase(): Promise<PrivacyOperation>;
}

interface GatewayErrorEnvelope {
  error?: { code?: unknown };
}

/**
 * Browser client for the Device Gateway parent API. All decoding goes through
 * the strict contract decoders; raw response bodies are never logged.
 */
export class LiveAppApi implements AppApi {
  private readonly baseUrl: string;
  private readonly fetchImpl: typeof fetch;
  private readonly timeoutMs: number;

  constructor(options: { baseUrl?: string; fetchImpl?: typeof fetch; timeoutMs?: number } = {}) {
    this.baseUrl = options.baseUrl ?? "";
    this.fetchImpl = options.fetchImpl ?? globalThis.fetch.bind(globalThis);
    this.timeoutMs = options.timeoutMs ?? 8000;
  }

  dashboard(): Promise<DashboardSnapshot> {
    return this.request("v1/dashboard", decodeDashboardSnapshot);
  }

  weeklyReport(): Promise<WeeklyReport> {
    return this.request("v1/reports/weekly", decodeWeeklyReport);
  }

  deviceSettings(deviceId: string): Promise<DeviceSettings> {
    return this.request(`v1/devices/${encodeURIComponent(deviceId)}`, decodeDeviceSettings);
  }

  updateDeviceSettings(deviceId: string, patch: DeviceSettingsPatch): Promise<DeviceSettings> {
    return this.request(`v1/devices/${encodeURIComponent(deviceId)}`, decodeDeviceSettings, {
      method: "PATCH",
      body: encodeDeviceSettingsPatch(patch),
    });
  }

  updateParentConstraints(update: ParentConstraintsUpdate): Promise<ParentConstraints> {
    return this.request("v1/parent-constraints", decodeParentConstraints, {
      method: "PUT",
      body: encodeParentConstraintsUpdate(update),
    });
  }

  requestPrivacyExport(): Promise<PrivacyOperation> {
    return this.request("v1/privacy/export", decodePrivacyOperation, { method: "POST" });
  }

  requestPrivacyErase(): Promise<PrivacyOperation> {
    return this.request("v1/privacy/erase", decodePrivacyOperation, { method: "POST" });
  }

  private async request<T>(
    path: string,
    decode: (value: unknown) => T,
    init: { method?: string; body?: string } = {},
  ): Promise<T> {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), this.timeoutMs);
    let response: Response;
    try {
      response = await this.fetchImpl(`${this.baseUrl}/${path}`, {
        ...init,
        headers: {
          accept: "application/json",
          ...(init.body === undefined ? {} : { "content-type": "application/json" }),
        },
        signal: controller.signal,
      });
    } catch {
      throw new AppApiError("offline");
    } finally {
      clearTimeout(timeout);
    }

    if (!response.ok) {
      let serverCode: string | null = null;
      try {
        const envelope = (await response.json()) as GatewayErrorEnvelope;
        if (typeof envelope.error?.code === "string") serverCode = envelope.error.code;
      } catch {
        serverCode = null;
      }
      if (serverCode) throw new AppApiError("server", serverCode);
      throw new AppApiError("invalid_response");
    }

    try {
      return decode(await response.json());
    } catch (error) {
      if (error instanceof AppApiError) throw error;
      throw new AppApiError("invalid_response");
    }
  }
}
