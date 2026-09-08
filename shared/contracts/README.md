# Shared Contracts（跨端契约）

`v1/` 下的 JSON Schema 2020-12 是**跨端唯一真源**。新增或修改跨端字段时，先改这里，
再改各端（`AGENTS.md` §38.12 / §39.1.5）。

## 内容

```text
v1/contract-version.json        契约版本
v1/device-event.schema.json     设备 → 服务端事件
v1/device-command.schema.json   服务端 → 设备命令
v1/device-settings.schema.json  设备设置
v1/dashboard-snapshot.schema.json  家长端首页
v1/weekly-report.schema.json    学习周报（claim 必须带 evidence）
v1/parent-constraints.schema.json  家长约束
v1/learning-event.schema.json   学习证据事件（raw / candidate / confirmed）
v1/fixtures/valid/*.json        必须被接受的样例
v1/fixtures/invalid/*.json      必须被拒绝的样例
learning_events.py              Python 侧 evidence 辅助（手写，见下）
```

## 测试

```bash
python -m pip install -r requirements-dev.txt
python -m pytest tests -q          # 12 用例：valid 必过 / invalid 必拒
python validate_contracts.py       # 同等校验的独立 CLI
```

## 各端消费方式（重要）

并非所有端都在运行时校验 schema，改字段时要按端确认：

| 端 | 方式 | 漂移风险 |
|---|---|---|
| `backend/device_gateway` | Ajv 运行时编译 `v1/*.schema.json` | 低：结构由 schema 强制 |
| `clients/hardware-rx5` | `jsonschema` 运行时校验（`SHE_CONTRACT_ROOT` 可覆盖根目录） | 低：同上 |
| `clients/ios` | `Domain/Models.swift` **手写 Codable**，仅用 `fixtures/valid/` 做解码测试 | **中**：字段改名只有被 fixture 覆盖时才会被发现 |
| `agents/director` | `src/learning-events.ts` **手写 TS 类型** | **中**：不校验 schema |
| 本目录 `learning_events.py` | **手写 dataclass/enum** | **中**：与 `learning-event.schema.json` 无自动一致性检查 |

改 `learning-event` 形状时，上述三处手写副本必须同步；目前没有 codegen 或跨端一致性测试
覆盖它们（已记入待办，见 `docs/IMPLEMENTATION_BACKLOG.md`）。

## 约定

- 新增字段优先向后兼容；破坏性变更走新版本目录（`v2/`），不原地改 `v1/`。
- 每个 schema 都必须同时有 valid 与 invalid fixture，否则测试无法证明约束生效。
- fixtures 里不得出现真实儿童数据、密钥或生产载荷（`AGENTS.md` §39.2.3）。
