# RDK X5 Device Runtime（硬件端运行时）

儿童真正使用的实时交互终端：唤醒、采音、采图、触摸/按键、播放 TTS、灯效、断网兜底。
硬件端只做**确定性、低延迟、隐私敏感**的工作，**不承担长期教学决策**（`AGENTS.md` §38.1）。

对外只连 `backend/device_gateway` 的 WebSocket，不直连其他后台（§38.5）。

- 架构定位：`AGENTS.md` §29 与 [`docs/architecture/05-hardware-rx5.md`](../../docs/architecture/05-hardware-rx5.md) §31
- 上板部署：[`docs/deployment.md`](docs/deployment.md) ·
  首次开机核验：[`../../playbooks/releases/rx5-first-boot.md`](../../playbooks/releases/rx5-first-boot.md)

## ⚠ 真机状态

**尚无任何真实 RDK X5 通过验证。** 模拟器、契约、摄像头生命周期与降级逻辑已自动化覆盖；
板上的 Ubuntu 22.04、`srcampy`、`hbm_runtime`、`Hobot.GPIO`、ALSA、摄像头与针脚仍须在
设备可 SSH 后逐项核验。**不得把「模块缺失」当作成功**（`AGENTS.md` §39.2.4）。

## 运行

```bash
python -m pip install -e '.[dev]'      # 包名 she-device，装出 she-device 命令

she-device simulate --once             # 确定性模拟器跑一轮（无硬件、无网络）
she-device capabilities                # 只探测依赖，不碰硬件
she-device run --hardware-mode simulator   # 连 gateway 跑运行时（或 --hardware-mode rdk）
```

也可用 `python -m she_device.cli simulate --once`（`scripts/verify.ps1` 即如此调用）。

环境变量（见 `.env.example`）：`SHE_GATEWAY_WS`、`SHE_DEVICE_ID`、`SHE_DEVICE_TOKEN`、
`SHE_HARDWARE_MODE`、`SHE_CAMERA_INDEX`、`SHE_GPIO_PIN`、`SHE_FALLBACK_WAV`、
`SHE_FIRMWARE_VERSION`、`SHE_RUNTIME_VERSION`、`SHE_CONTRACT_ROOT`（覆盖契约根目录）。

```bash
SHE_GATEWAY_WS=ws://127.0.0.1:8788/v1/device/session she-device run --hardware-mode simulator
```

## 测试

```bash
python -m pytest tests -q     # 11 用例（pytest-asyncio，asyncio_mode=auto）
```

## 涉及契约

**运行时直接校验 schema**，不手写副本：`src/she_device/contracts.py` 用
`jsonschema.Draft202012Validator` 校验 `shared/contracts/v1/device-event` 与
`device-command`。根目录按 `SHE_CONTRACT_ROOT` → 仓库内相对路径 → `/opt/she/...` 依次解析。
改契约先改 `shared/contracts/`（`AGENTS.md` §38.12）。

## 结构

```text
src/she_device/
├── cli.py          命令行入口
├── runtime.py      主循环：事件序列、心跳、重连
├── gateway.py      WebSocket 传输（有界重连）
├── ports.py        硬件端口抽象
├── factory.py      按能力探测选择 adapter
├── adapters/       rdk_x5 / simulator / unavailable
├── contracts.py    schema 校验
├── fallback.py     断网与降级
└── redaction.py    日志脱敏
deploy/she-device.service   systemd 单元
scripts/{install,preflight}.sh
```

## 隐私红线

原始儿童音频、画面、话语、token、凭据不得进入 Git 或默认日志（`AGENTS.md` §39.2.3）。
摄像头只由显式事件触发，采集窗口结束必须关闭（§38.6）。能力缺失要显式上报
`capability_errors`，**不能静默当作正常**。
