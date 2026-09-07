#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from typing import Any

from websockets.asyncio.client import connect

from she_device.adapters.simulator import SimulatorAudio, SimulatorCamera, SimulatorGPIO
from she_device.contracts import ContractError, DeviceCommand
from she_device.redaction import redact_for_log
from she_device.runtime import DeviceRuntime


class WebSocketTransport:
    def __init__(self, socket: Any) -> None:
        self.socket = socket
        self.acknowledgements: list[dict[str, Any]] = []

    async def send_event(self, event: dict[str, Any]) -> None:
        await self.socket.send(json.dumps(event, separators=(",", ":")))
        if event["type"] == "command_ack":
            self.acknowledgements.append(event)
            print(json.dumps(redact_for_log(event), ensure_ascii=False, sort_keys=True), flush=True)


async def run_smoke(url: str, device_id: str) -> None:
    async with connect(url, open_timeout=3, close_timeout=1) as socket:
        transport = WebSocketTransport(socket)
        runtime = DeviceRuntime(
            device_id=device_id,
            session_id=f"{device_id}-smoke",
            camera=SimulatorCamera(),
            audio=SimulatorAudio(),
            gpio=SimulatorGPIO(),
            transport=transport,
        )
        await runtime.hello(["simulator", "audio_playback", "short_capture"])
        await runtime.wake("simulator")

        async def receive_two_commands() -> None:
            handled = 0
            while handled < 2:
                value = json.loads(await socket.recv())
                if not isinstance(value, dict) or "command_id" not in value:
                    continue
                command = DeviceCommand.from_dict(value)
                await runtime.handle_command(command)
                acknowledgement = transport.acknowledgements[-1]
                if acknowledgement["payload"]["status"] != "completed":
                    raise RuntimeError("command_failed")
                handled += 1

        await asyncio.wait_for(receive_two_commands(), timeout=8)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="gateway_smoke.py")
    parser.add_argument("--url", required=True)
    parser.add_argument("--device-id", required=True)
    args = parser.parse_args(argv)
    try:
        asyncio.run(run_smoke(args.url, args.device_id))
    except (OSError, ConnectionError, TimeoutError, asyncio.TimeoutError, ContractError, RuntimeError, ValueError):
        print('{"error_code":"gateway_smoke_failed"}', file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
