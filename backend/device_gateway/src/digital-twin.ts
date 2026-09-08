import type { CommandDraft, DeviceCommand, DeviceEvent, DeviceSessionSnapshot, JsonObject } from "./types.js";

export interface DigitalTwinState {
  device_id: string;
  online: boolean;
  session_id: string | null;
  capabilities: string[];
  capability_errors: Record<string, string>;
  runtime: { firmware_version: string | null; runtime_version: string | null };
  telemetry: { battery_percent: number | null; temperature_c: number | null; network: string | null };
  privacy: { camera_enabled: boolean; raw_audio_upload_enabled: boolean };
  last_event: { event_id: string; type: DeviceEvent["type"]; occurred_at: string } | null;
  last_command: { command_id: string; type: DeviceCommand["type"]; issued_at: string; acknowledged: boolean } | null;
  updated_at: string;
}

export interface TwinTimelineEntry {
  at: string;
  kind: "event" | "command" | "session";
  type: string;
  id?: string;
  payload?: JsonObject;
}

function numberOrNull(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function stringOrNull(value: unknown): string | null {
  return typeof value === "string" && value.length > 0 ? value : null;
}

export class DigitalTwinRegistry {
  private readonly twins = new Map<string, DigitalTwinState>();
  private readonly timelines = new Map<string, TwinTimelineEntry[]>();

  onEvent(event: DeviceEvent, session: DeviceSessionSnapshot): void {
    const payload = event.payload ?? {};
    const current = this.twins.get(event.device_id) ?? {
      device_id: event.device_id,
      online: true,
      session_id: event.session_id,
      capabilities: [],
      capability_errors: {},
      runtime: { firmware_version: null, runtime_version: null },
      telemetry: { battery_percent: null, temperature_c: null, network: null },
      privacy: { camera_enabled: true, raw_audio_upload_enabled: false },
      last_event: null,
      last_command: null,
      updated_at: event.occurred_at,
    };
    current.online = session.online;
    current.session_id = event.session_id;
    current.last_event = { event_id: event.event_id, type: event.type, occurred_at: event.occurred_at };
    current.updated_at = event.occurred_at;
    if (event.type === "hello") {
      if (Array.isArray(payload.capabilities)) {
        current.capabilities = payload.capabilities.filter((value): value is string => typeof value === "string");
      }
      current.runtime.firmware_version = stringOrNull(payload.firmware_version) ?? current.runtime.firmware_version;
      current.runtime.runtime_version = stringOrNull(payload.runtime_version) ?? current.runtime.runtime_version;
    }
    if (event.type === "device_state" || event.type === "heartbeat") {
      current.telemetry.battery_percent = numberOrNull(payload.battery_percent) ?? current.telemetry.battery_percent;
      current.telemetry.temperature_c = numberOrNull(payload.temperature_c) ?? current.telemetry.temperature_c;
      current.telemetry.network = stringOrNull(payload.network) ?? current.telemetry.network;
      if (typeof payload.camera_enabled === "boolean") current.privacy.camera_enabled = payload.camera_enabled;
      if (typeof payload.raw_audio_upload_enabled === "boolean") current.privacy.raw_audio_upload_enabled = payload.raw_audio_upload_enabled;
    }
    if (event.type === "capability_unavailable") {
      const capability = stringOrNull(payload.capability);
      const errorCode = stringOrNull(payload.error_code);
      if (capability && errorCode) current.capability_errors[capability] = errorCode;
    }
    if (event.type === "command_ack" && current.last_command && current.last_command.command_id === payload.command_id) {
      current.last_command.acknowledged = true;
    }
    this.twins.set(event.device_id, current);
    this.append(event.device_id, { at: event.occurred_at, kind: "event", type: event.type, id: event.event_id, payload });
  }

  onCommand(command: DeviceCommand): void {
    const twin = this.ensure(command.device_id, command.session_id, command.issued_at);
    twin.last_command = { command_id: command.command_id, type: command.type, issued_at: command.issued_at, acknowledged: false };
    twin.updated_at = command.issued_at;
    this.append(command.device_id, { at: command.issued_at, kind: "command", type: command.type, id: command.command_id, payload: command.payload });
  }

  onClosed(deviceId: string, at = new Date().toISOString()): void {
    const twin = this.twins.get(deviceId);
    if (!twin) return;
    twin.online = false;
    twin.updated_at = at;
    this.append(deviceId, { at, kind: "session", type: "offline" });
  }

  get(deviceId: string): DigitalTwinState | undefined {
    const twin = this.twins.get(deviceId);
    return twin ? structuredClone(twin) : undefined;
  }

  timeline(deviceId: string, limit = 100): TwinTimelineEntry[] {
    return structuredClone((this.timelines.get(deviceId) ?? []).slice(-Math.max(1, Math.min(limit, 500))));
  }

  private ensure(deviceId: string, sessionId: string, at: string): DigitalTwinState {
    const existing = this.twins.get(deviceId);
    if (existing) return existing;
    const twin: DigitalTwinState = {
      device_id: deviceId,
      online: true,
      session_id: sessionId,
      capabilities: [],
      capability_errors: {},
      runtime: { firmware_version: null, runtime_version: null },
      telemetry: { battery_percent: null, temperature_c: null, network: null },
      privacy: { camera_enabled: true, raw_audio_upload_enabled: false },
      last_event: null,
      last_command: null,
      updated_at: at,
    };
    this.twins.set(deviceId, twin);
    return twin;
  }

  private append(deviceId: string, entry: TwinTimelineEntry): void {
    const timeline = this.timelines.get(deviceId) ?? [];
    timeline.push(entry);
    if (timeline.length > 500) timeline.splice(0, timeline.length - 500);
    this.timelines.set(deviceId, timeline);
  }
}
