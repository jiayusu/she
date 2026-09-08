# 03 五大臣 Agent 调度 · 实现说明

PRD 见 [README.md](README.md)。设计与决策见 [docs/design.md](docs/design.md)。

## 快速开始

```bash
npm install
npm test          # 66 用例:8 条 FR 验收 + 非功能 + HTTP/WS e2e
npm start         # 启动服务(默认 127.0.0.1:8787)
npm run typecheck # tsc --noEmit
```

```bash
# 冒烟:孩子问记忆 → 路由阿海,带剧情上下文
curl -s http://127.0.0.1:8787/agent/dispatch \
  -H 'content-type: application/json' \
  -d '{"session_id":"child-001","utterance":"我昨天教会小熊什么来着","emotion":0.1,"asr":{"conf":0.95}}'
```

## 验收对照

| PRD 验收 | 实现 | 测试 |
| --- | --- | --- |
| FR-G01 六类意图 ≥90%,低置信反问澄清 | `src/intent.ts`(词法+情绪+softmax) | `test/intent.test.ts`(48 句盲测 100%,澄清分支) |
| FR-G02 映射配置化,运营改无需发版 | `config/minister-map.json` + 热加载 + 备选链 | `test/mapping.test.ts` |
| FR-G03 注入包四要素,预算 500/1500,延迟 ≤50ms | `src/context.ts` | `test/context.test.ts`(预算+裁剪+p95) |
| FR-G04 写入成功率 ≥99.9%,重试 1 次,死信当日清零 | `src/memory-write.ts` | `test/memory-write.test.ts`(确定性故障注入 1000 连写) |
| FR-G05 显著性 ≥阈值入白名单,只增不删 | `src/salience.ts` + `NeverForgetWhitelist` | `test/salience.test.ts` |
| FR-G06 周 batch,diff 报告,人工确认生效 | `src/consolidation.ts` | `test/consolidation.test.ts` |
| FR-G07 三 agent 可观测、可手动触发 | `src/metacognition.ts` | `test/metacognition.test.ts` |
| FR-G08 边界清单文档化,安全钩子不可绕过 | `src/hooks.ts` + `docs/tool-boundary.md` | `test/hooks.test.ts`(403/注入/强制过滤) |
| 路由+注入 ≤100ms | dispatch 管线全内存 | `test/e2e.test.ts`(HTTP p95) |
| 崩溃恢复重建 ≤2s | 快照 50ms 防抖 + `recover()` | `test/session.test.ts`(实测 ~5ms) |
| 调度决策全留审计 | `src/audit.ts`(JSONL 按天) | `test/session.test.ts` |
| §6 接口 + §8 埋点 | `src/server.ts` / `src/metrics.ts` | `test/e2e.test.ts` |

接口手册:[docs/api.md](docs/api.md) · 注入规范:[docs/context-injection.md](docs/context-injection.md) ·
工具边界:[docs/tool-boundary.md](docs/tool-boundary.md)

## 运行时数据目录

`data/`(gitignore):`snapshots/` 会话快照、`stores/` 五库 JSONL、`kg.json` 语义层、
`whitelist.json` 永不遗忘、`dlq.jsonl` 死信、`audit/` 审计、`reports/` 复盘报告。
