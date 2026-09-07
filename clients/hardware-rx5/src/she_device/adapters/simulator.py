from __future__ import annotations

from typing import Any


class SimulatorCamera:
    def __init__(self) -> None:
        self.is_open = False

    def open(self) -> None:
        self.is_open = True

    def capture(self, window_ms: int) -> dict[str, object]:
        if not self.is_open:
            raise RuntimeError("camera_not_open")
        return {
            "label": "apple",
            "bbox": [0.25, 0.25, 0.5, 0.5],
            "confidence": 0.92,
            "confirmation_state": "confirmed",
        }

    def close(self) -> None:
        self.is_open = False


class SimulatorAudio:
    def __init__(self) -> None:
        self.history: list[str] = []

    def play_text(self, text: str, voice_id: str | None = None) -> None:
        self.history.append(text)


class SimulatorGPIO:
    def __init__(self) -> None:
        self.history: list[tuple[str, str]] = []

    def set_led(self, color: str, pattern: str) -> None:
        self.history.append((color, pattern))


class MemoryTransport:
    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []

    async def send_event(self, event: dict[str, Any]) -> None:
        self.events.append(event)
