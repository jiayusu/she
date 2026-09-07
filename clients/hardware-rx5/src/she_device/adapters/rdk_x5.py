from __future__ import annotations

import importlib
import shutil
import subprocess
from pathlib import Path
from typing import Any, Callable


def discover_capabilities(
    *,
    import_module: Callable[[str], Any] = importlib.import_module,
    which: Callable[[str], str | None] = shutil.which,
) -> dict[str, dict[str, object]]:
    report: dict[str, dict[str, object]] = {}
    for capability, provider in (
        ("camera", "srcampy"),
        ("inference", "hbm_runtime"),
        ("gpio", "Hobot.GPIO"),
    ):
        try:
            import_module(provider)
            report[capability] = {"available": True, "provider": provider, "error_code": None}
        except (ImportError, OSError):
            report[capability] = {
                "available": False,
                "provider": provider,
                "error_code": "module_missing",
            }
    for capability, provider in (("audio_capture", "arecord"), ("audio_playback", "aplay")):
        available = which(provider) is not None
        report[capability] = {
            "available": available,
            "provider": provider,
            "error_code": None if available else "binary_missing",
        }
    return report


class RDKCamera:
    def __init__(self, *, camera_index: int = 0) -> None:
        module = importlib.import_module("srcampy")
        self._camera = module.Camera()
        self._camera_index = camera_index

    def open(self) -> None:
        self._camera.open_cam(self._camera_index, -1, 30, 640, 480)

    def capture(self, window_ms: int) -> dict[str, object]:
        frame = self._camera.get_img(2, 640, 480)
        if frame is None:
            raise RuntimeError("camera_frame_unavailable")
        return {
            "label": "unverified",
            "bbox": [0.25, 0.25, 0.5, 0.5],
            "confidence": 0.0,
            "confirmation_state": "unconfirmed",
        }

    def close(self) -> None:
        self._camera.close_cam()


class ALSAAudio:
    def __init__(self, *, wav_path: Path) -> None:
        self.wav_path = wav_path

    def play_text(self, text: str, voice_id: str | None = None) -> None:
        if not self.wav_path.is_file():
            raise RuntimeError("fallback_wav_missing")
        subprocess.run(["aplay", "--quiet", str(self.wav_path)], check=True, timeout=15)


class RDKGPIO:
    def __init__(self, *, pin: int) -> None:
        self._gpio = importlib.import_module("Hobot.GPIO")
        self._pin = pin

    def set_led(self, color: str, pattern: str) -> None:
        self._gpio.output(self._pin, self._gpio.LOW if pattern == "off" else self._gpio.HIGH)
