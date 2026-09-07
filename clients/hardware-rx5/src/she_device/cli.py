from __future__ import annotations

import argparse
import asyncio
import json
from datetime import datetime, timezone
from random import Random

from .adapters.rdk_x5 import discover_capabilities
from .adapters.simulator import MemoryTransport, SimulatorAudio, SimulatorCamera, SimulatorGPIO
from .contracts import DeviceCommand
from .redaction import redact_for_log
from .runtime import DeviceRuntime


def _fixed_clock() -> datetime:
    return datetime(2026, 9, 7, 10, 0, 0, tzinfo=timezone.utc)


async def _simulate_once() -> None:
    identifiers = iter(
        (
            "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
            "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
            "cccccccc-cccc-4ccc-8ccc-cccccccccccc",
        )
    )
    transport = MemoryTransport()
    runtime = DeviceRuntime(
        device_id="rx5-demo-001",
        session_id="session-demo-001",
        camera=SimulatorCamera(),
        audio=SimulatorAudio(),
        gpio=SimulatorGPIO(),
        transport=transport,
        clock=_fixed_clock,
        random_source=Random(7),
        id_factory=lambda: next(identifiers),
    )
    await runtime.hello(["simulator", "audio_playback", "short_capture"])
    await runtime.handle_command(
        DeviceCommand.from_dict(
            {
                "command_id": "22222222-2222-4222-8222-222222222222",
                "contract_version": "1.0",
                "device_id": "rx5-demo-001",
                "session_id": "session-demo-001",
                "sequence": 1,
                "issued_at": "2026-09-07T10:00:01Z",
                "expires_at": "2026-09-07T10:00:06Z",
                "type": "capture",
                "payload": {"window_ms": 2000},
            }
        )
    )
    for event in transport.events:
        print(json.dumps(redact_for_log(event), ensure_ascii=False, sort_keys=True))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="she-device")
    subparsers = parser.add_subparsers(dest="mode", required=True)
    simulate = subparsers.add_parser("simulate", help="run the deterministic hardware simulator")
    simulate.add_argument("--once", action="store_true", required=True)
    subparsers.add_parser("capabilities", help="inspect RDK X5 dependencies without touching hardware")
    args = parser.parse_args(argv)
    if args.mode == "simulate":
        asyncio.run(_simulate_once())
        return 0
    print(json.dumps(discover_capabilities(), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
