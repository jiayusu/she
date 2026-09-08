from __future__ import annotations


class UnavailableCamera:
    def __init__(self, error_code: str = "camera_unavailable") -> None:
        self.error_code = error_code

    def open(self) -> None:
        raise RuntimeError(self.error_code)

    def capture(self, window_ms: int) -> dict[str, object]:
        raise RuntimeError(self.error_code)

    def close(self) -> None:
        return


class UnavailableAudio:
    def __init__(self, error_code: str = "audio_playback_unavailable") -> None:
        self.error_code = error_code

    def play_text(self, text: str, voice_id: str | None = None) -> None:
        raise RuntimeError(self.error_code)


class UnavailableGPIO:
    def __init__(self, error_code: str = "gpio_unavailable") -> None:
        self.error_code = error_code

    def set_led(self, color: str, pattern: str) -> None:
        raise RuntimeError(self.error_code)
