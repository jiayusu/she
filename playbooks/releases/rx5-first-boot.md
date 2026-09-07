# RDK X5 first boot and hardware verification

Status: **simulator verified; physical RDK X5 unverified**

Target: RDK X5 running Ubuntu 22.04 / RDK OS 3.5 or later

Repository location on device: `/opt/she`

## Safety boundary

This procedure does not change pinmux, enable GPIO output, open a camera, record
audio, or enable the service during preflight. Do not create
`/etc/she-device.enabled` until every relevant capability has been checked on the
physical board. Raw frames and recordings must not be copied into the repository.

## 1. Prepare the board

1. Boot the vendor-supported Ubuntu 22.04 image from SD.
2. Connect through a trusted LAN and confirm SSH host identity out of band.
3. Copy the repository to `/opt/she` without `.env`, databases, logs, raw media,
   model artifacts, or local `.state` content.
4. Keep secrets only in `/etc/she-device.env`, owned by root with mode `0600`.

## 2. Read-only preflight

From the board:

```bash
bash /opt/she/clients/hardware-rx5/scripts/preflight.sh
```

Record the output in a new incident if any of the following are absent:

- `aarch64` architecture and Ubuntu 22.04;
- `srcampy` for camera access;
- `hbm_runtime` for BPU inference;
- `Hobot.GPIO` for GPIO;
- `arecord` and `aplay` for ALSA;
- camera and ALSA devices expected by the physical build.

Missing capability means unavailable; it must never be reported as working.

## 3. Verify the simulator on the board

```bash
python3 -m venv /opt/she/venv
/opt/she/venv/bin/python -m pip install -e '/opt/she/clients/hardware-rx5[dev]'
SHE_CONTRACT_ROOT=/opt/she/shared/contracts/v1 /opt/she/venv/bin/python -m pytest /opt/she/clients/hardware-rx5/tests -q
SHE_CONTRACT_ROOT=/opt/she/shared/contracts/v1 /opt/she/venv/bin/python -m she_device.cli simulate --once
```

Expected: all tests pass; the last redacted lifecycle line has type
`command_ack`. No utterance, audio, image, or token content appears.

## 4. Hardware verification gates

Verify one capability at a time with an adult operator present:

1. Confirm the camera device and vendor sample before opening `srcampy.Camera`.
2. Capture only a short disposable frame window; confirm the camera closes on
   both success and injected failure.
3. Verify ALSA playback with the approved local fallback WAV. Do not record a
   child during bring-up.
4. Confirm the exact GPIO pin and voltage against the board wiring before any
   output. This repository deliberately does not choose a pinmux.
5. Verify the Gateway WebSocket on a trusted LAN, then disconnect it and confirm
   the fixed local fallback: `小P在这里，我们稍后再试一次。`

For every failure, search `/opt/she/playbooks/incidents` and `/opt/she/skills`
first, then create an incident with sanitized evidence.

## 5. Service activation

The checked-in unit is guarded by `/etc/she-device.enabled` and remains disabled
by default. The current first-stage unit only performs capability discovery; it
does not claim a production hardware session. Do not enable it until a later,
device-verified change replaces `ExecStart` with the approved live runtime.

## Rollback

Remove `/etc/she-device.enabled`, stop and disable `she-device.service`, and keep
the repository and incident evidence for diagnosis. Do not delete system logs
until sanitized diagnostic evidence has been retained outside Git.
