# RX5 Deployment Runbook

1. Verify `clients/hardware-rx5/scripts/preflight.sh` on the board.
2. Verify the gateway health endpoint and WebSocket enrollment.
3. Start the simulator with `gateway_smoke.py` before enabling hardware capture.
4. Confirm `GET /v1/devices/{id}/twin` reports capabilities and fresh heartbeat data.
5. Issue one bounded LED/speak command and confirm its correlated `command_ack`.
6. Enable camera/audio only after privacy settings and capability probes pass.

Physical RDK X5 validation is pending SSH access. A passing simulator run is not hardware evidence.
