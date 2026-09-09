import { randomUUID } from "node:crypto";

import type { WebSocket, WebSocketServer } from "ws";

import type { ContractValidators } from "./contracts.js";
import {
  CONTRACT_VERSION,
  type CommandDraft,
  type DeviceCommand,
  type DeviceEvent,
  type DeviceSession,
  type DeviceSessionSnapshot,
} from "./types.js";


const MAX_EVENT_IDS = 256;

function send(socket: WebSocket, payload: unknown): void {
  socket.send(JSON.stringify(payload));
}

function error(code: string, message: string): object {
  return { contract_version: CONTRACT_VERSION, error: { code, message } };
}

export class DeviceSessionRegistry {
  private readonly sessions = new Map<string, DeviceSession>();

  constructor(
    private readonly validators: ContractValidators,
    private readonly now: () => Date = () => new Date(),
    private readonly hooks: {
      onEvent?: (event: DeviceEvent, snapshot: DeviceSessionSnapshot) => void;
      onCommand?: (command: DeviceCommand) => void;
      onClose?: (deviceId: string) => void;
    } = {},
  ) {}

  attach(server: WebSocketServer): void {
    server.on("connection", (socket) => this.accept(socket));
  }

  snapshot(deviceId: string): DeviceSessionSnapshot | undefined {
    const session = this.sessions.get(deviceId);
    if (!session) return undefined;
    return {
      deviceId: session.deviceId,
      sessionId: session.sessionId,
      online: session.online,
      lastSequence: session.lastSequence,
      lastHeartbeatAt: session.lastHeartbeatAt,
      acceptedEvents: session.acceptedEvents,
      acceptedEventTypes: [...session.acceptedEventTypes],
      pendingCommands: session.pendingCommands.size,
    };
  }

  sendCommand(deviceId: string, draft: CommandDraft): DeviceCommand {
    const session = this.sessions.get(deviceId);
    if (!session?.online) throw new Error("device_offline");
    const issued = this.now();
    const command: DeviceCommand = {
      command_id: draft.commandId ?? randomUUID(),
      contract_version: CONTRACT_VERSION,
      device_id: deviceId,
      session_id: session.sessionId,
      sequence: session.nextCommandSequence++,
      issued_at: issued.toISOString(),
      expires_at: new Date(issued.getTime() + 5_000).toISOString(),
      type: draft.type,
      payload: draft.payload,
    };
    const result = this.validators.deviceCommand(command);
    if (!result.ok) throw new Error("invalid_device_command");
    session.pendingCommands.set(command.command_id, command);
    send(session.socket, command);
    this.hooks.onCommand?.(command);
    return command;
  }

  private accept(socket: WebSocket): void {
    let boundDeviceId: string | undefined;

    socket.on("message", (raw) => {
      let value: unknown;
      try {
        value = JSON.parse(raw.toString());
      } catch {
        send(socket, error("invalid_json", "Message must be valid JSON."));
        return;
      }

      if (!value || typeof value !== "object") {
        send(socket, error("invalid_device_event", "Message must be an object."));
        return;
      }
      const candidate = value as Record<string, unknown>;
      if (candidate.contract_version !== CONTRACT_VERSION) {
        send(socket, error("contract_version_unsupported", "Only contract version 1.0 is supported."));
        return;
      }
      const validation = this.validators.deviceEvent(candidate);
      if (!validation.ok) {
        send(socket, error("invalid_device_event", "Message does not match the v1 device event contract."));
        return;
      }

      const event = candidate as unknown as DeviceEvent;
      let session = this.sessions.get(event.device_id);
      if (!session) {
        if (event.type !== "hello") {
          send(socket, error("hello_required", "The first event must be hello."));
          return;
        }
        session = {
          deviceId: event.device_id,
          sessionId: event.session_id,
          socket,
          online: true,
          lastSequence: -1,
          nextCommandSequence: 0,
          lastHeartbeatAt: event.occurred_at,
          acceptedEvents: 0,
          acceptedEventTypes: [],
          seenEventIds: new Set(),
          eventOrder: [],
          pendingCommands: new Map(),
        };
        this.sessions.set(event.device_id, session);
        boundDeviceId = event.device_id;
      } else if (event.type === "hello" && !session.online && event.session_id !== session.sessionId) {
        // A process restart gets a new session id. Replace the offline record
        // while retaining the device identity and leaving the old socket inert.
        session = {
          deviceId: event.device_id,
          sessionId: event.session_id,
          socket,
          online: true,
          lastSequence: -1,
          nextCommandSequence: 0,
          lastHeartbeatAt: event.occurred_at,
          acceptedEvents: 0,
          acceptedEventTypes: [],
          seenEventIds: new Set(),
          eventOrder: [],
          pendingCommands: new Map(),
        };
        this.sessions.set(event.device_id, session);
        boundDeviceId = event.device_id;
      }

      if (session.socket !== socket) {
        send(socket, error("socket_mismatch", "Event must originate from the bound device connection."));
        return;
      }
      if (event.type === "command_ack") {
        const command = session.pendingCommands.get(String(event.payload.command_id));
        if (!command || this.now().getTime() >= Date.parse(command.expires_at)) {
          send(socket, error("unknown_or_expired_command", "Acknowledgement must match a live command."));
          return;
        }
      }
      if (session.seenEventIds.has(event.event_id)) {
        send(socket, { contract_version: CONTRACT_VERSION, status: "duplicate", event_id: event.event_id });
        return;
      }
      if (event.session_id !== session.sessionId) {
        send(socket, error("session_mismatch", "Event session does not match the active device session."));
        return;
      }
      if (event.sequence <= session.lastSequence) {
        send(socket, error("sequence_out_of_order", "Event sequence must increase monotonically."));
        return;
      }

      session.lastSequence = event.sequence;
      session.lastHeartbeatAt = event.occurred_at;
      session.acceptedEvents += 1;
      session.acceptedEventTypes.push(event.type);
      if (session.acceptedEventTypes.length > 32) session.acceptedEventTypes.shift();
      session.seenEventIds.add(event.event_id);
      session.eventOrder.push(event.event_id);
      if (session.eventOrder.length > MAX_EVENT_IDS) {
        const oldest = session.eventOrder.shift();
        if (oldest) session.seenEventIds.delete(oldest);
      }
      if (event.type === "command_ack") {
        session.pendingCommands.delete(String(event.payload.command_id));
      }
      this.hooks.onEvent?.(event, this.snapshot(event.device_id)!);
      send(socket, { contract_version: CONTRACT_VERSION, status: "accepted", event_id: event.event_id });
    });

    socket.on("close", () => {
      if (!boundDeviceId) return;
      const session = this.sessions.get(boundDeviceId);
      if (session?.socket === socket) {
        session.online = false;
        this.hooks.onClose?.(boundDeviceId);
      }
    });
  }
}
