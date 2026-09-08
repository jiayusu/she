from __future__ import annotations

import os
from pathlib import Path
from uuid import uuid4

from .adapters.rdk_x5 import ALSAAudio, RDKCamera, RDKGPIO, discover_capabilities
from .adapters.simulator import SimulatorAudio, SimulatorCamera, SimulatorGPIO
from .adapters.unavailable import UnavailableAudio, UnavailableCamera, UnavailableGPIO
from .gateway import gateway_from_environment
from .runtime import DeviceRuntime


def available_capability_names(report: dict[str, dict[str, object]]) -> list[str]:
    return sorted(name for name, value in report.items() if value.get("available") is True)


def create_runtime(*, mode: str | None = None) -> tuple[DeviceRuntime, list[str], dict[str, dict[str, object]]]:
    selected_mode = (mode or os.environ.get("SHE_HARDWARE_MODE", "rdk")).lower()
    device_id = os.environ.get("SHE_DEVICE_ID")
    if not device_id:
        raise RuntimeError("SHE_DEVICE_ID is required")
    session_id = os.environ.get("SHE_SESSION_ID", str(uuid4()))
    sequence_path = Path(os.environ.get("SHE_SEQUENCE_PATH", "/var/lib/she-device/event-sequence"))
    report = discover_capabilities()
    transport = gateway_from_environment()

    if selected_mode == "simulator":
        capabilities = ["simulator", "audio_playback", "short_capture"]
        report = {
            name: {"available": True, "provider": "simulator", "error_code": None}
            for name in ("camera", "inference", "gpio", "audio_capture", "audio_playback")
        }
        runtime = DeviceRuntime(
            device_id=device_id,
            session_id=session_id,
            camera=SimulatorCamera(),
            audio=SimulatorAudio(),
            gpio=SimulatorGPIO(),
            transport=transport,
            sequence_path=sequence_path,
        )
        return runtime, capabilities, report
    if selected_mode != "rdk":
        raise RuntimeError("SHE_HARDWARE_MODE must be rdk or simulator")

    pin_value = os.environ.get("SHE_GPIO_PIN")
    wav_value = os.environ.get("SHE_FALLBACK_WAV")
    camera = UnavailableCamera(str(report["camera"].get("error_code", "camera_unavailable")))
    if report["camera"]["available"] is True:
        try:
            camera = RDKCamera(camera_index=int(os.environ.get("SHE_CAMERA_INDEX", "0")))
        except (ImportError, OSError, RuntimeError) as exc:
            report["camera"] = {"available": False, "provider": "srcampy", "error_code": type(exc).__name__}
    audio = UnavailableAudio(str(report["audio_playback"].get("error_code", "audio_playback_unavailable")))
    if report["audio_playback"]["available"] is True and wav_value:
        audio = ALSAAudio(wav_path=Path(wav_value))
    elif report["audio_playback"]["available"] is True:
        report["audio_playback"] = {"available": False, "provider": "aplay", "error_code": "fallback_wav_missing"}
    gpio = UnavailableGPIO(str(report["gpio"].get("error_code", "gpio_unavailable")))
    if report["gpio"]["available"] is True and pin_value:
        try:
            gpio = RDKGPIO(pin=int(pin_value))
        except (ValueError, ImportError, OSError, RuntimeError) as exc:
            report["gpio"] = {"available": False, "provider": "Hobot.GPIO", "error_code": type(exc).__name__}
    elif report["gpio"]["available"] is True:
        report["gpio"] = {"available": False, "provider": "Hobot.GPIO", "error_code": "gpio_pin_unconfigured"}
    runtime = DeviceRuntime(
        device_id=device_id,
        session_id=session_id,
        camera=camera,
        audio=audio,
        gpio=gpio,
        transport=transport,
        sequence_path=sequence_path,
    )
    return runtime, available_capability_names(report), report
