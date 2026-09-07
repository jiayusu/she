from __future__ import annotations

from dataclasses import replace

import pytest

from she_device.contracts import DeviceCommand
from she_device.fallback import SAFE_LOCAL_FALLBACK
from she_device.runtime import DeviceRuntime


class FakeCamera:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.open_count = 0
        self.capture_count = 0
        self.close_count = 0

    def open(self) -> None:
        self.open_count += 1

    def capture(self, window_ms: int) -> dict[str, object]:
        self.capture_count += 1
        if self.fail:
            raise RuntimeError("camera unavailable")
        return {"label": "apple", "confidence": 0.92, "window_ms": window_ms}

    def close(self) -> None:
        self.close_count += 1


class FakeAudio:
    def __init__(self) -> None:
        self.spoken: list[str] = []

    def play_text(self, text: str, voice_id: str | None = None) -> None:
        self.spoken.append(text)


class FakeGPIO:
    def __init__(self) -> None:
        self.changes: list[tuple[str, str]] = []

    def set_led(self, color: str, pattern: str) -> None:
        self.changes.append((color, pattern))


class FakeTransport:
    def __init__(self) -> None:
        self.events: list[dict[str, object]] = []

    async def send_event(self, event: dict[str, object]) -> None:
        self.events.append(event)


@pytest.fixture
def capture_command() -> DeviceCommand:
    return DeviceCommand.from_dict(
        {
            "command_id": "22222222-2222-4222-8222-222222222222",
            "contract_version": "1.0",
            "device_id": "rx5-demo-001",
            "session_id": "session-demo-001",
            "sequence": 1,
            "issued_at": "2026-09-07T10:00:01Z",
            "expires_at": "2099-09-07T10:00:06Z",
            "type": "capture",
            "payload": {"window_ms": 2000},
        }
    )


def make_runtime(camera: FakeCamera):
    audio = FakeAudio()
    gpio = FakeGPIO()
    transport = FakeTransport()
    runtime = DeviceRuntime(
        device_id="rx5-demo-001",
        session_id="session-demo-001",
        camera=camera,
        audio=audio,
        gpio=gpio,
        transport=transport,
    )
    return runtime, audio, gpio, transport


@pytest.mark.asyncio
async def test_camera_opens_only_for_explicit_capture_and_always_closes(capture_command):
    camera = FakeCamera()
    runtime, _, _, transport = make_runtime(camera)
    assert camera.open_count == 0

    await runtime.handle_command(capture_command)

    assert (camera.open_count, camera.capture_count, camera.close_count) == (1, 1, 1)
    assert [event["type"] for event in transport.events] == ["pointing", "command_ack"]


@pytest.mark.asyncio
async def test_camera_closes_when_capture_raises(capture_command):
    camera = FakeCamera(fail=True)
    runtime, _, _, transport = make_runtime(camera)

    await runtime.handle_command(capture_command)

    assert camera.close_count == 1
    assert transport.events[-1]["payload"] == {
        "command_id": capture_command.command_id,
        "status": "failed",
        "error_code": "camera_unavailable",
    }


@pytest.mark.asyncio
async def test_repeated_command_is_idempotent(capture_command):
    camera = FakeCamera()
    runtime, _, _, transport = make_runtime(camera)

    await runtime.handle_command(capture_command)
    await runtime.handle_command(capture_command)

    assert camera.capture_count == 1
    acknowledgements = [event for event in transport.events if event["type"] == "command_ack"]
    assert len(acknowledgements) == 1


def test_disconnect_uses_fixed_local_fallback():
    runtime, audio, _, _ = make_runtime(FakeCamera())

    runtime.on_disconnect()

    assert audio.spoken == [SAFE_LOCAL_FALLBACK]


@pytest.mark.asyncio
async def test_sequence_must_increase(capture_command):
    runtime, _, _, transport = make_runtime(FakeCamera())
    await runtime.handle_command(capture_command)
    stale = replace(
        capture_command,
        command_id="33333333-3333-4333-8333-333333333333",
    )

    await runtime.handle_command(stale)

    assert transport.events[-1]["payload"]["error_code"] == "sequence_not_monotonic"


@pytest.mark.asyncio
async def test_injected_clock_and_ids_make_events_deterministic(capture_command):
    from datetime import datetime, timezone

    identifiers = iter(
        (
            "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
            "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
        )
    )
    transport = FakeTransport()
    runtime = DeviceRuntime(
        device_id="rx5-demo-001",
        session_id="session-demo-001",
        camera=FakeCamera(),
        audio=FakeAudio(),
        gpio=FakeGPIO(),
        transport=transport,
        clock=lambda: datetime(2026, 9, 7, 10, 0, tzinfo=timezone.utc),
        id_factory=lambda: next(identifiers),
    )

    await runtime.handle_command(capture_command)

    assert [event["event_id"] for event in transport.events] == [
        "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
        "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
    ]
    assert {event["occurred_at"] for event in transport.events} == {"2026-09-07T10:00:00Z"}
