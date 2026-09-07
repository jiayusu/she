from __future__ import annotations

import asyncio
from collections import deque
from datetime import datetime, timezone
from random import Random
from typing import Any, Callable
from uuid import uuid4

from .contracts import CONTRACT_VERSION, ContractError, DeviceCommand, validate_event
from .fallback import SAFE_LOCAL_FALLBACK
from .ports import AudioPort, CameraPort, GPIOPort, SessionTransportPort, TransportPort


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class DeviceRuntime:
    def __init__(
        self,
        *,
        device_id: str,
        session_id: str,
        camera: CameraPort,
        audio: AudioPort,
        gpio: GPIOPort,
        transport: TransportPort,
        clock: Callable[[], datetime] = _utc_now,
        random_source: Random | None = None,
        id_factory: Callable[[], str] = lambda: str(uuid4()),
    ) -> None:
        self.device_id = device_id
        self.session_id = session_id
        self.camera = camera
        self.audio = audio
        self.gpio = gpio
        self.transport = transport
        self.clock = clock
        self.random = random_source or Random()
        self.id_factory = id_factory
        self._event_sequence = 0
        self._last_command_sequence = -1
        self._seen_commands: set[str] = set()
        self._seen_order: deque[str] = deque()

    def _event(self, event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        event = {
            "event_id": self.id_factory(),
            "contract_version": CONTRACT_VERSION,
            "device_id": self.device_id,
            "session_id": self.session_id,
            "sequence": self._event_sequence,
            "occurred_at": self.clock().astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
            "type": event_type,
            "payload": payload,
        }
        validate_event(event)
        self._event_sequence += 1
        return event

    async def hello(self, capabilities: list[str]) -> None:
        await self.transport.send_event(
            self._event("hello", {"runtime_version": "0.1.0", "capabilities": capabilities})
        )

    async def heartbeat(self) -> None:
        await self.transport.send_event(self._event("heartbeat", {}))

    async def wake(self, source: str = "simulator") -> None:
        await self.transport.send_event(self._event("wake", {"source": source}))

    async def _ack(self, command: DeviceCommand, status: str, error_code: str | None = None) -> None:
        await self.transport.send_event(
            self._event(
                "command_ack",
                {"command_id": command.command_id, "status": status, "error_code": error_code},
            )
        )

    def _remember(self, command_id: str) -> None:
        self._seen_commands.add(command_id)
        self._seen_order.append(command_id)
        while len(self._seen_order) > 256:
            expired = self._seen_order.popleft()
            self._seen_commands.discard(expired)

    async def handle_command(self, command: DeviceCommand) -> None:
        if command.command_id in self._seen_commands:
            return
        if command.sequence <= self._last_command_sequence:
            await self._ack(command, "failed", "sequence_not_monotonic")
            return

        self._last_command_sequence = command.sequence
        self._remember(command.command_id)
        try:
            if command.type == "capture":
                await self._capture(command)
            elif command.type == "stop_capture":
                self.camera.close()
            elif command.type in {"speak", "fallback"}:
                self.audio.play_text(str(command.payload["text"]), command.payload.get("voice_id"))
            elif command.type == "led":
                self.gpio.set_led(str(command.payload["color"]), str(command.payload["pattern"]))
            else:
                await self._ack(command, "failed", "command_unsupported")
                return
        except (OSError, RuntimeError):
            await self._ack(command, "failed", self._error_code(command.type))
            return
        await self._ack(command, "completed")

    async def _capture(self, command: DeviceCommand) -> None:
        opened = False
        try:
            self.camera.open()
            opened = True
            detected = self.camera.capture(int(command.payload["window_ms"]))
            await self.transport.send_event(
                self._event(
                    "pointing",
                    {
                        "label": str(detected.get("label", "unknown")),
                        "bbox": detected.get("bbox", [0.25, 0.25, 0.5, 0.5]),
                        "confidence": float(detected.get("confidence", 0.0)),
                        "confirmation_state": str(detected.get("confirmation_state", "unconfirmed")),
                    },
                )
            )
        finally:
            if opened:
                self.camera.close()

    @staticmethod
    def _error_code(command_type: str) -> str:
        return {
            "capture": "camera_unavailable",
            "speak": "audio_playback_unavailable",
            "fallback": "audio_playback_unavailable",
            "led": "gpio_unavailable",
            "stop_capture": "camera_unavailable",
        }.get(command_type, "device_error")

    def on_disconnect(self) -> None:
        self.audio.play_text(SAFE_LOCAL_FALLBACK)

    async def run(self, capabilities: list[str]) -> None:
        """Run a reconnecting device session when the transport supports sessions."""
        transport = self.transport
        if not isinstance(transport, SessionTransportPort):
            raise TypeError("transport_session_unsupported")
        attempt = 0
        while True:
            try:
                await transport.connect()
                await self.hello(capabilities)
                attempt = 0
                async for raw in transport.commands():
                    await self.handle_command(DeviceCommand.from_dict(raw))
            except (ConnectionError, OSError, ContractError):
                self.on_disconnect()
                attempt += 1
                base = min(30.0, 0.5 * (2 ** min(attempt, 6)))
                await asyncio.sleep(base + self.random.uniform(0.0, min(0.5, base / 4)))
            finally:
                await transport.close()
