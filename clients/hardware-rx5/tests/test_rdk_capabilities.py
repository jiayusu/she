from __future__ import annotations

from she_device.adapters.rdk_x5 import ALSAAudio, discover_capabilities


def test_missing_vendor_modules_and_alsa_are_structured_unavailable():
    def missing_import(name: str):
        raise ModuleNotFoundError(name)

    report = discover_capabilities(import_module=missing_import, which=lambda _: None)

    assert report == {
        "camera": {"available": False, "provider": "srcampy", "error_code": "module_missing"},
        "inference": {"available": False, "provider": "hbm_runtime", "error_code": "module_missing"},
        "gpio": {"available": False, "provider": "Hobot.GPIO", "error_code": "module_missing"},
        "audio_capture": {"available": False, "provider": "arecord", "error_code": "binary_missing"},
        "audio_playback": {"available": False, "provider": "aplay", "error_code": "binary_missing"},
    }


def test_alsa_playback_uses_an_argument_array_without_shell(tmp_path, monkeypatch):
    calls = []
    wav = tmp_path / "fallback.wav"
    wav.write_bytes(b"RIFF")

    def fake_run(arguments, **kwargs):
        calls.append((arguments, kwargs))

    monkeypatch.setattr("she_device.adapters.rdk_x5.subprocess.run", fake_run)

    ALSAAudio(wav_path=wav).play_text("not passed to subprocess")

    assert calls == [(["aplay", "--quiet", str(wav)], {"check": True, "timeout": 15})]


def test_available_vendor_modules_and_alsa_are_reported_without_initializing_hardware():
    imported: list[str] = []

    def fake_import(name: str):
        imported.append(name)
        return object()

    report = discover_capabilities(import_module=fake_import, which=lambda name: f"/usr/bin/{name}")

    assert all(item["available"] for item in report.values())
    assert imported == ["srcampy", "hbm_runtime", "Hobot.GPIO"]
