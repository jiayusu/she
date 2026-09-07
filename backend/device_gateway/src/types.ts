import type { WebSocket } from "ws";


export const CONTRACT_VERSION = "1.0" as const;

export type JsonObject = Record<string, unknown>;

export interface DeviceEvent {
  event_id: string;
  contract_version: typeof CONTRACT_VERSION;
  device_id: string;
  session_id: string;
  sequence: number;
  occurred_at: string;
  type: "hello" | "wake" | "touch" | "pointing" | "device_state" | "command_ack" | "heartbeat";
  payload: JsonObject;
}

export interface DeviceCommand {
  command_id: string;
  contract_version: typeof CONTRACT_VERSION;
  device_id: string;
  session_id: string;
  sequence: number;
  issued_at: string;
  expires_at: string;
  type: "speak" | "led" | "capture" | "stop_capture" | "fallback";
  payload: JsonObject;
}

export interface CommandDraft {
  type: DeviceCommand["type"];
  payload: JsonObject;
}

export interface DeviceSession {
  deviceId: string;
  sessionId: string;
  socket: WebSocket;
  online: boolean;
  lastSequence: number;
  nextCommandSequence: number;
  lastHeartbeatAt: string;
  acceptedEvents: number;
  seenEventIds: Set<string>;
  eventOrder: string[];
  pendingCommands: Map<string, DeviceCommand>;
}

export interface DeviceSessionSnapshot {
  deviceId: string;
  sessionId: string;
  online: boolean;
  lastSequence: number;
  lastHeartbeatAt: string;
  acceptedEvents: number;
  pendingCommands: number;
}
