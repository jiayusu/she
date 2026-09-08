# Learning Director（学习导演）

学习优先的总调度器：接收 Interaction Agent 的一轮输入，产出 `curriculum`、`scaffold`、
`story` 与唯一 `teaching_action`。不直接对儿童说话，不直接写 Learner Profile / KG / SQLite。

- 架构定位：`AGENTS.md` §29 与 [`docs/architecture/02-agents.md`](../../docs/architecture/02-agents.md) §4
- 设计与决策：[`docs/design.md`](docs/design.md)
- 接口手册：[`docs/api.md`](docs/api.md) ·
  注入规范：[`docs/context-injection.md`](docs/context-injection.md) ·
  工具边界：[`docs/tool-boundary.md`](docs/tool-boundary.md)

## 学习循环

[第一阶段实现与限制](docs/learning-loop.md)：评估上一轮目标、有限追问、低置信确认、暂停恢复与六阶段 trace。
新入口只返回 candidate/no_write，不再将原话写入旧 JSONL fallback；Shared State 写回尚未接入。

## 运行

```bash
npm ci
npm start           # 默认 127.0.0.1:8790，PORT 可覆盖
```

端点：`POST /agent/direct`（新客户端用这个）、`POST /agent/dispatch`（迁移期兼容）、
`WS /agent/session`、`GET /healthz`、`/admin/*`。

```bash
# 冒烟：孩子问记忆 → 带剧情上下文作答
curl -s http://127.0.0.1:8790/agent/direct \
  -H 'content-type: application/json' \
  -d '{"session_id":"child-001","utterance":"我昨天教会小熊什么来着","emotion":0.1,"asr":{"conf":0.95}}'
```

## 测试

```bash
npm test            # 76 用例：FR 验收 + 非功能 + HTTP/WS e2e
npm run typecheck   # tsc --noEmit
```

## 涉及契约

`shared/contracts/v1/learning-event.schema.json`（学习证据事件）。
`src/learning-events.ts` 目前手写该形状，未在运行时校验 schema——改字段时先改
`shared/contracts/`，再改本组件（`AGENTS.md` §38.12）。

## 验收对照

| PRD 验收 | 实现 | 测试 |
| --- | --- | --- |
| FR-G01 六类意图 ≥90%，低置信反问澄清 | `src/intent.ts`（词法+情绪+softmax） | `test/intent.test.ts`（48 句盲测 100%，澄清分支） |
| FR-G02 映射配置化，运营改无需发版 | `config/minister-map.json` + 热加载 + 备选链 | `test/mapping.test.ts` |
| FR-G03 注入包四要素，预算 500/1500，延迟 ≤50ms | `src/context.ts` | `test/context.test.ts`（预算+裁剪+p95） |
| FR-G04 写入成功率 ≥99.9%，重试 1 次，死信当日清零 | `src/memory-write.ts` | `test/memory-write.test.ts`（确定性故障注入 1000 连写） |
| FR-G05 显著性 ≥阈值入白名单，只增不删 | `src/salience.ts` + `NeverForgetWhitelist` | `test/salience.test.ts` |
| FR-G06 周 batch，diff 报告，人工确认生效 | `src/consolidation.ts` | `test/consolidation.test.ts` |
| FR-G07 三 agent 可观测、可手动触发 | `src/metacognition.ts` | `test/metacognition.test.ts` |
| FR-G08 边界清单文档化，安全钩子不可绕过 | `src/hooks.ts` + `docs/tool-boundary.md` | `test/hooks.test.ts`（403/注入/强制过滤） |
| 路由+注入 ≤100ms | dispatch 管线全内存 | `test/e2e.test.ts`（HTTP p95） |
| 崩溃恢复重建 ≤2s | 快照 50ms 防抖 + `recover()` | `test/session.test.ts`（实测 ~5ms） |
| 调度决策全留审计 | `src/audit.ts`（JSONL 按天） | `test/session.test.ts` |

## 运行时数据目录

`data/`（已 gitignore）：`snapshots/` 会话快照、`stores/` 五库 JSONL、`kg.json` 语义层、
`whitelist.json` 永不遗忘、`dlq.jsonl` 死信、`audit/` 审计、`reports/` 复盘报告。

## 历史

`package.json` 的包名仍是 `five-ministers-dispatch`，源码里保留 minister 相关类型：
本组件由旧 `route/` 目录演进而来。旧「五大臣 = 五后台 Agent」PRD 已归档在
[`docs/archive/prd/director-prd-v1.md`](../../docs/archive/prd/director-prd-v1.md)，
**不要据此恢复旧架构**（`AGENTS.md` §28.3）。
