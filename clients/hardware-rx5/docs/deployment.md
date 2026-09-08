# RDK X5 Deployment

This document is the hardware handoff for the mocked runtime. It does not claim that a physical board has been validated.

## Board prerequisites

- Ubuntu 22.04 aarch64 image and an operator-managed service account
- Python 3.10 or newer, `python3-venv`, `build-essential`, and ALSA utilities
- Network access to the Device Gateway WebSocket endpoint
- Vendor packages installed only when the corresponding capability is detected: `srcampy`, `hbm_runtime`, `Hobot.GPIO`
- Camera and microphone permissions granted to the service account

## Install

```bash
cd /opt/she/clients/hardware-rx5
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install .
./scripts/preflight.sh
```

Configure `SHE_GATEWAY_WS` and run the simulator first:

```bash
SHE_GATEWAY_WS=ws://gateway.example:8788/v1/device/session she-device simulate --once
```

## Enrollment and reconnect

Each physical unit receives a gateway-issued `device_id` and credential during
provisioning. Store both in the root-only environment file used by systemd;
never commit them or put them in telemetry. The first connection sends a
`hello` event with device, firmware, runtime, and capability information, then a
`device_state` event and one `capability_unavailable` event for each missing
provider. The latter is an explicit degraded state, not a successful hardware
probe.

The runtime reconnects with bounded exponential backoff (1, 2, 4, 8, 16, 30
seconds) and sends a fresh `hello` after every reconnect. Event sequence
numbers are monotonic per device. The gateway deduplicates `(device_id,
sequence)` so retries are idempotent. A command is complete only after a
matching `command_ack`; timeout leaves the twin `unknown`, never `succeeded`.

The runtime sends a heartbeat every 20 seconds while connected. A missing
heartbeat or a closed socket is treated as offline by the gateway and twin.

## Rollback

Deploy runtime packages and the systemd unit as one versioned release
directory. Keep the previous directory until first-boot health checks observe a
gateway handshake, audio capability, and clean shutdown. If a check fails,
restore the previous symlink and revoke the new enrollment token. Keep the
server-side twin timeline as the audit record.

Then install `deploy/she-device.service`, set the environment file to the gateway URL,
enrolled device identity, `SHE_HARDWARE_MODE=rdk`, `SHE_GPIO_PIN`, and
`SHE_FALLBACK_WAV`, create `/etc/she-device.enabled`, and run
`systemctl enable --now she-device`. The unit starts `she-device run`; it refuses
to claim unavailable capabilities: it connects in a degraded safe mode and
reports each missing capability to the twin. Physical activation still requires
the first-boot gates and operator-verified pin/audio configuration.

## Capability preflight

The runtime must probe imports, ALSA devices, `/dev/video*`, GPIO access, and accelerator availability. Missing capabilities become structured `capability_unavailable` events and activate safe fallback; do not hardcode GPIO pins or assume a camera exists.

## Rollback and removal

Stop and disable the service, remove the installed unit and virtual environment, and revoke the device enrollment at the gateway. Keep the server-side twin timeline for audit until the retention policy expires; it contains no raw media.
