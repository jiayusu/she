# API 手册

Base URL:`http://127.0.0.1:8787`(端口 `PORT` 环境变量,默认 8787)。

## 对外接口(PRD §6)

### POST /agent/direct

Learning-first decision endpoint. It is the preferred integration surface for new clients and
never returns a minister or changes long-term learner state. The director combines the current
utterance, optional detected object, learner snapshot, recent attempts and emotion signal into
one `teaching_action` with separate `language_level` and `scaffold_level` fields.

```json
{
  "session_id": "demo",
  "utterance": "milk",
  "detected_object": "milk",
  "recent_attempts": []
}
```

The response contains `curriculum`, `scaffold`, `story`, `teaching_action` and an explicit
`safety` object. Flattened aliases (`scaffold_level`, `story_action`, `success_condition`) and a
sanitized `ctx_bundle` are included for thin clients. `memory_policy` is conservative (`candidate`) and must be promoted by an
assessment/shared-state service before any confirmed learner write.

### POST /agent/dispatch

```jsonc
// 请求
{
  "session_id": "child-001",
  "utterance": "我昨天教会小熊什么来着",
  "asr": { "conf": 0.95 },                  // ASR(02) 元数据;number 视为 conf
  "emotion": { "valence": -0.2, "arousal": 0.8, "label": "sad" }, // 声学情绪分;number 视为 valence
  "script_state": { "plot": "朝会", "act": 3 },  // 剧情引擎(01)推送,merge 语义
  "assistant_reply": "……",                  // 可选:大臣回复,记入对话轮并过输出钩子
  "memory_write": [                          // 剧情引擎产生的记忆写入
    { "id": "mw1", "store": "episodic", "kind": "milestone", "payload": { "text": "第一次复述故事" } },
    { "kind": "word_learned", "payload": { "word": "苹果", "eval": "passed" } } // store 可由 minister 推导
  ]
}
```

```jsonc
// 响应 200
{
  "route_id": "rt_…",
  "intent": "memory",
  "confidence": 0.96,
  "need_clarify": false,
  "clarify_question": null,
  "minister": "ahai",
  "minister_label": "阿海",
  "fallback_used": false,
  "route_reason": "意图 memory 主大臣",
  "ctx_bundle": { /* 见 docs/context-injection.md */ },
  "memory_write_ack": [
    { "id": "mw1", "store": "episodic", "ok": true, "attempts": 1, "salience": 1.0, "whitelisted": true }
  ],
  "latency_ms": 1.8,
  "safety": { "input_filtered": false, "injection_suspected": false, "output_filtered": false }
}
```

错误:400 缺字段/非法 JSON;所有校验错误消息人话可读。

### WS /agent/session

连接 `ws://127.0.0.1:8787/agent/session?session_id=child-001`(可选过滤会话)。

- 服务端即推 `hello`(全部会话的值守大臣,灯效同步)。
- 订阅事件:`minister_change` / `dispatch_done` / `dlq_alert` / `whitelist_added` /
  `job_done` / `consolidation_confirmed` / `map_reloaded`,统一帧
  `{ type, payload, ts }`。
- 客户端发 `{"type":"ping"}` → 回 `pong`。

### GET /agent/session/:id

会话当前状态(值守大臣、剧本状态、最近 10 轮、今日已学词、情绪)。

### GET /healthz

`{ ok, uptime_ms, sessions, dlq_open, whitelist, ministers[] }`

## 管理端点(/admin)

| 方法与路径 | 用途 |
| --- | --- |
| GET /admin/map · POST /admin/map/reload | 映射表查看 / 热加载(FR-G02,改 `config/minister-map.json` 后无需发版) |
| POST /admin/lexicon/reload | 词典热加载 |
| GET /admin/ministers | 五大臣值守/降级状态 |
| POST /admin/ministers/:id/degrade `{on}` | 标记大臣降级(验证备选链) |
| POST /admin/consolidation/trigger | 生成巩固 diff 报告(FR-G06) |
| GET /admin/consolidation/reports[/:id] | 报告查询 |
| POST /admin/consolidation/confirm `{report_id}` | 人工一键确认,词进老颞语义层 |
| GET /admin/jobs · POST /admin/jobs/:name/trigger | 元认知任务状态 / 手动触发(review / prune / consolidate,FR-G07) |
| GET /admin/dlq · POST /admin/dlq/retry · POST /admin/dlq/sweep | 死信队列查看 / 重推 / 当日清零巡检(FR-G04) |
| GET /admin/whitelist · POST /admin/whitelist `{ref_id,reason}` | 永不遗忘白名单(只增,FR-G05) |
| GET /admin/tools · POST /admin/tools/invoke `{name,args}` | 工具边界机读清单 / 以 LLM 身份调用工具(FR-G08,钩子名返回 403) |
| GET /admin/kg/pending-review · POST /admin/kg/pending-review/:id/resolve `{accept}` | KG 冲突待审处理(04 冲突接口) |
| GET /admin/audit?date=&type=&limit= | 审计日志查询 |
| GET /admin/metrics | 埋点快照 + 延迟分位 |
| POST /admin/sessions/:id/rebuild | 从快照重建单个会话 |

## 埋点(§8)

`route_done(intent, minister, conf)` / `ctx_built(tokens)` /
`memory_write(store, ok)` / `consolidate_batch(count)`,
另含 `route_latency_ms` / `ctx_build_ms` 分位数。快照:`GET /admin/metrics`。
