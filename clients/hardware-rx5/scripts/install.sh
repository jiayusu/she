#!/usr/bin/env bash
set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
  printf 'run as root: sudo %s\n' "$0" >&2
  exit 2
fi

if ! id -u she-device >/dev/null 2>&1; then
  useradd --system --home-dir /var/lib/she-device --shell /usr/sbin/nologin she-device
fi
install -d -o she-device -g she-device /opt/she /var/lib/she-device
python3 -m venv /opt/she/venv
/opt/she/venv/bin/python -m pip install --upgrade pip
/opt/she/venv/bin/python -m pip install /opt/she/clients/hardware-rx5
install -m 0644 /opt/she/clients/hardware-rx5/deploy/she-device.service /etc/systemd/system/she-device.service
systemctl daemon-reload
printf 'Installed but not enabled. Run preflight.sh and configure /etc/she-device.env before enabling.\n'
