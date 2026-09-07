#!/usr/bin/env bash
set -u

printf 'os='; . /etc/os-release 2>/dev/null && printf '%s %s\n' "${NAME:-unknown}" "${VERSION_ID:-unknown}" || printf 'unknown\n'
printf 'architecture=%s\n' "$(uname -m)"
printf 'rdk_packages='; dpkg-query -W -f='${binary:Package} ${Version}\n' 2>/dev/null | grep -E 'hobot|hbm|d-robotics' || printf 'unavailable\n'
printf 'camera_devices='; find /dev -maxdepth 1 -type c -name 'video*' -print 2>/dev/null || true
printf 'alsa_capture='; command -v arecord >/dev/null 2>&1 && arecord -l 2>/dev/null || printf 'unavailable\n'
printf 'alsa_playback='; command -v aplay >/dev/null 2>&1 && aplay -l 2>/dev/null || printf 'unavailable\n'
python3 - <<'PY'
import importlib
for name in ("srcampy", "hbm_runtime", "Hobot.GPIO"):
    try:
        importlib.import_module(name)
        print(f"module:{name}=available")
    except Exception as exc:
        print(f"module:{name}=unavailable:{type(exc).__name__}")
PY
printf 'network='; ip route get 1.1.1.1 2>/dev/null | head -n 1 || printf 'unavailable\n'
