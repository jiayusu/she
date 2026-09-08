# Digital Twin and Hardware Portal Deployment

The gateway is the only portal between hardware and software. Start it from `backend/device_gateway` with Node 20+:

Paths below are relative to the repository root; run from there.

```powershell
Push-Location -LiteralPath './backend/device_gateway'
npm ci
npm run typecheck
npm start
Pop-Location
```

The mock device uses `clients/hardware-rx5` and points `SHE_GATEWAY_WS` at `ws://<gateway-host>:8788/v1/device/session`. The simulator is the supported development path while physical SSH access is pending.

Production requirements:

- bind the gateway behind TLS termination and restrict the WebSocket origin/network;
- persist gateway logs as redacted operational metadata only;
- set `SHE_DEVICE_TOKEN` on the gateway and the matching root-only
  `SHE_DEVICE_TOKEN` on enrolled devices (or replace this single-token gate with
  the production enrollment service); unauthenticated WebSocket upgrades are
  rejected before the session registry sees a hello;
- monitor twin freshness (`updated_at`), offline transitions, command acknowledgements, and capability failures;
- treat an offline or stale twin as unknown hardware state, never as proof that a sensor is safe.

Enrollment is owned by the gateway. The twin is created only after an
authenticated `hello` event. Reconnects retain the same `device_id`, sequence
deduplication makes event retries safe, and commands are idempotent by
`command_id`. The twin records pending, acknowledged, or timed-out commands;
an HTTP 202 is not proof of delivery.

For rollback, drain commands, stop the runtime, revoke its credential, and
restore the prior release. Never delete the twin timeline during rollback.

No RDK X5 board has been validated in this workspace. Physical rollout remains blocked on operator-approved SSH access and capability checks.
