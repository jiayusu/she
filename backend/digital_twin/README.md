# Digital Twin

The Digital Twin is the server-owned representation of every SHE device, including the simulator. It is deliberately downstream of `backend/device_gateway`: devices speak the validated v1 WebSocket contract, the gateway validates and deduplicates events, and the twin records the latest capability, telemetry, privacy, session, command, and acknowledgement state.

The parent app reads the twin over HTTP. It never treats local UI state as authoritative and it never connects directly to an RX5 board. `capability_errors` records explicit degraded providers reported by the runtime; an absent capability is never treated as hardware success.

## Portal flow

```text
RX5 runtime or simulator
  <-> ws://gateway/v1/device/session
Device Gateway (validation, idempotency, command correlation)
  -> DigitalTwinRegistry
  -> /v1/devices/{id}/twin and /timeline
Parent app / operations portal
```

Available gateway endpoints:

- `GET /v1/devices/{id}/twin`
- `GET /v1/devices/{id}/timeline?limit=100`
- `POST /v1/devices/{id}/commands` with `{ "type": "speak|led|capture|stop_capture|fallback", "payload": {} }`

Raw audio, images, child utterances, credentials, and tokens are not stored in the twin timeline. The twin is operational state, not a second learning or content database.
