from __future__ import annotations

import asyncio
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
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
        sequence_path: Path | None = None,
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
        self._sequence_path = sequence_path
        self._event_sequence = self._load_event_sequence()
        self._event_lock = asyncio.Lock()
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
        self._persist_event_sequence()
        return event

    def _load_event_sequence(self) -> int:
        if self._sequence_path is None or not self._sequence_path.is_file():
            return 0
        try:
            value = int(self._sequence_path.read_text(encoding="utf-8").strip())
            return max(0, value)
        except (OSError, ValueError):
            return 0

    def _persist_event_sequence(self) -> None:
        if self._sequence_path is None:
            return
        try:
            self._sequence_path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self._sequence_path.with_suffix(self._sequence_path.suffix + ".tmp")
            temporary.write_text(str(self._event_sequence), encoding="utf-8")
            temporary.replace(self._sequence_path)
        except OSError:
            # Event delivery remains authoritative; inability to persist a
            # cursor is surfaced by the next gateway sequence check.
            return

    async def hello(self, capabilities: list[str], *, firmware_version: str | None = None, runtime_version: str = "0.1.0") -> None:
        payload: dict[str, Any] = {"runtime_version": runtime_version, "capabilities": capabilities}
        if firmware_version:
            payload["firmware_version"] = firmware_version
        await self._send_event("hello", payload)

    async def _send_event(self, event_type: str, payload: dict[str, Any]) -> None:
        async with self._event_lock:
            await self.transport.send_event(self._event(event_type, payload))

    async def heartbeat(self) -> None:
        await self._send_event("heartbeat", {})

    async def publish_capabilities(self, report: dict[str, dict[str, object]]) -> None:
        available = sorted(name for name, value in report.items() if value.get("available") is True)
        await self._send_event(
            "device_state",
            {"online": True, "battery_percent": None, "capabilities": available},
        )
        for capability, value in sorted(report.items()):
            if value.get("available") is True:
                continue
            await self._send_event(
                "capability_unavailable",
                {
                    "capability": capability,
                    "provider": str(value.get("provider", "unknown")),
                    "error_code": str(value.get("error_code", "unavailable")),
                },
            )

    async def wake(self, source: str = "simulator") -> None:
        await self._send_event("wake", {"source": source})

    async def _ack(self, command: DeviceCommand, status: str, error_code: str | None = None) -> None:
        await self._send_event(
            "command_ack",
            {"command_id": command.command_id, "status": status, "error_code": error_code},
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
        if command.device_id != self.device_id or command.session_id != self.session_id:
            await self._ack(command, "failed", "command_target_mismatch")
            return
        if command.sequence <= self._last_command_sequence:
            await self._ack(command, "failed", "sequence_not_monotonic")
            return

        self._last_command_sequence = command.sequence
        self._remember(command.command_id)

        try:
            expires_at = datetime.fromisoformat(command.expires_at.replace("Z", "+00:00"))
        except ValueError:
            await self._ack(command, "failed", "command_expiry_invalid")
            return
        if expires_at <= self.clock().astimezone(timezone.utc):
            await self._ack(command, "failed", "command_expired")
            return

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
            await self._send_event(
                "pointing",
                {
                    "label": str(detected.get("label", "unknown")),
                    "bbox": detected.get("bbox", [0.25, 0.25, 0.5, 0.5]),
                    "confidence": float(detected.get("confidence", 0.0)),
                    "confirmation_state": str(detected.get("confirmation_state", "unconfirmed")),
                },
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
        try:
            self.audio.play_text(SAFE_LOCAL_FALLBACK)
        except (OSError, RuntimeError):
            # A disconnected gateway must never crash the reconnect loop. The
            # local fallback is best effort when the audio device is unavailable.
            return

    async def _heartbeat_loop(self) -> None:
        while True:
            await asyncio.sleep(20.0)
            await self.heartbeat()

    async def run(
        self,
        capabilities: list[str],
        *,
        capability_report: dict[str, dict[str, object]] | None = None,
        firmware_version: str = "unknown",
        runtime_version: str = "0.1.0",
    ) -> None:
        """Run a reconnecting device session when the transport supports sessions."""
        transport = self.transport
        if not isinstance(transport, SessionTransportPort):
            raise TypeError("transport_session_unsupported")
        attempt = 0
        while True:
            try:
                await transport.connect()
                # Command sequence numbers are scoped to the gateway session;
                # event sequence numbers intentionally remain device-scoped.
                self._last_command_sequence = -1
                await self.hello(capabilities, firmware_version=firmware_version, runtime_version=runtime_version)
                if capability_report is not None:
                    await self.publish_capabilities(capability_report)
                attempt = 0
                heartbeat_task = asyncio.create_task(self._heartbeat_loop())
                try:
                    async for raw in transport.commands():
                        await self.handle_command(DeviceCommand.from_dict(raw))
                finally:
                    heartbeat_task.cancel()
                    await asyncio.gather(heartbeat_task, return_exceptions=True)
            except (ConnectionError, OSError, TimeoutError, ContractError):
                self.on_disconnect()
                attempt += 1
                base = min(30.0, 0.5 * (2 ** min(attempt, 6)))
                await asyncio.sleep(base + self.random.uniform(0.0, min(0.5, base / 4)))
            finally:
                await transport.close()
