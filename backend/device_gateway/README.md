# Device Gateway

**唯一的硬件 / 软件传输边界。** 所有设备控制都经过本组件（`AGENTS.md` §38.5）：对家长端提供
HTTP API，对设备（RX5 或模拟器）提供 WebSocket 会话，并在服务端维护权威 Digital Twin。

本组件同时**拥有 Digital Twin 实现**（`src/digital-twin.ts`）。`backend/digital_twin/` 只有文档，
没有代码——找 twin 逻辑请看这里。

- 架构定位：`AGENTS.md` §29 与 [`docs/architecture/08-contracts.md`](../../docs/architecture/08-contracts.md) §34
- Twin 与门户部署说明：[`../digital_twin/README.md`](../digital_twin/README.md) ·
  [`../digital_twin/deployment.md`](../digital_twin/deployment.md)

## 运行

```bash
npm ci
npm start           # 默认 127.0.0.1:8788，PORT 可覆盖
```

家长端 HTTP：

```text
GET  /v1/dashboard              GET  /v1/reports/weekly
GET/PUT /v1/parent-constraints
POST /v1/privacy/export         POST /v1/privacy/erase
```

设备与 Twin：

```text
WS   /v1/device/session         设备会话（enrollment 后才建 twin）
GET  /v1/devices/{id}           GET /v1/devices/{id}/twin
GET  /v1/devices/{id}/timeline  POST /v1/devices/{id}/commands
```

环境变量：`PORT`(8788)、`SHE_DEVICE_TOKEN`（设备鉴权；未配置时拒绝未鉴权的 WS upgrade）、
`SHE_LEARNING_REPORT_URL`（未配置则用 `DemoRepository` 演示数据）。

> **安全边界**：WebSocket upgrade 在进入会话注册表之前完成鉴权。生产部署必须置于 TLS 终止之后
> 并限制 WS origin/网络，详见 `../digital_twin/deployment.md`。

## 测试

```bash
npm test            # 10 用例，含与 Python RX5 模拟器的端到端流程
npm run typecheck   # tsc --noEmit
```

`test/device-e2e.test.ts` 会 spawn `clients/hardware-rx5` 的模拟器，因此需要先安装该组件：
`python -m pip install -e './clients/hardware-rx5[dev]'`（缺失时该用例失败，其余 9 个仍通过）。

## 涉及契约

**本组件在运行时直接校验 schema**，不手写副本：`src/contracts.ts` 用 Ajv 编译
`shared/contracts/v1/*.schema.json`（`device-event`、`device-command`、`dashboard-snapshot`、
`weekly-report`、`parent-constraints`、`device-settings`）。改契约先改
`shared/contracts/`（`AGENTS.md` §38.12）。

幂等与去重：事件按 `sequence` 去重，命令按 `command_id` 幂等；`HTTP 202` 不等于送达，
Twin 记录 pending / acknowledged / timed-out。
