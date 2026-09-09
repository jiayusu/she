# 契约与四端通信

> Agent 之间的结构化契约，以及 Hardware / App / Web 与后端的通信关系。
>
> 硬规则、组件归属与导航见仓库根 [`AGENTS.md`](../../AGENTS.md)。
> 本文各节沿用 AGENTS.md 原有编号，以保持既有交叉引用有效。

---

# 25. Agent 间契约

Agent 之间优先传结构化数据，不传自由长文本。

## CurriculumProposal

```json
{
  "primary_target": "",
  "review_targets": [],
  "i_plus_1_target": "",
  "language_level": 0,
  "priority": 0.0
}
```

## ScaffoldProposal

```json
{
  "scaffold_level": 0,
  "prompt_pattern": "",
  "fallback_pattern": "",
  "max_attempts": 0
}
```

## StoryProposal

```json
{
  "story_action": "",
  "world_role": "",
  "success_feedback": "",
  "state_patch": {}
}
```

`state_patch` 只为旧 learning response 兼容保留；RPG 主路径必须为空对象，世界变化只能出现在
`rpg-decision.world_events` 并由 Shared State 校验。

## TeachingAction

```json
{
  "action_id": "action-turn-001",
  "learning_goal": "",
  "target_expression": "",
  "language_level": 0,
  "scaffold_level": 0,
  "teaching_action": "",
  "correction_policy": "",
  "story_action": "",
  "prompt_id": "collect_milk_s2",
  "feedback_id": "collect_milk_s2",
  "node_id": "collect_milk",
  "phase": "presenting",
  "world_role": "饮品保管员",
  "success_condition": {},
  "memory_policy": ""
}
```

## AssessmentResult

```json
{
  "target_reached": false,
  "semantic_correctness": 0.0,
  "spontaneous": false,
  "prompt_level_used": 0,
  "pronunciation_intelligibility": null,
  "assessment_confidence": 0.0,
  "learning_evidence": []
}
```

`pronunciation_intelligibility=null` 表示尚无专用发音 evaluator 结果；不得用 ASR transcript
置信度代填。只有 evaluator 真实产出时才写入 `0..1`。

## RpgTurn

客户端/设备只能提交身份、输入种类与结构化感知引用：

```json
{
  "contract_version": "1.0",
  "child_id": "child-demo",
  "session_id": "session-demo",
  "turn_id": "turn-001",
  "previous_turn_id": null,
  "device_id": "rx5-demo",
  "input_kind": "object_observed",
  "utterance": "",
  "asr": null,
  "emotion": null,
  "detected_object": "fridge",
  "perception_event_id": "perception-001"
}
```

该对象 `additionalProperties=false`，不接受 world state、state patch、mastery 或客户端自报成功。
只有 `object_observed` 可以携带 `detected_object`；`speech`/`resume` 必须显式传 `null`。

## RpgDecision

Director 返回当前有限状态、Speech Act evidence 和本次 world events。JSON Schema 约束形状；
Memory 事务另外核对上一节点、连续 revision、canonical inventory、当前节点
`confirmed_object`、上一 `action_id`/scaffold、已完成 delivery、节点匹配的审核 prompt，以及
event-evidence 引用。同一合法回合最多产生两个事件（红杯奖励 `2→3`、任务完成 `3→4`）。
当前 v1 只允许 `milk_picnic.v1` 的 canonical 节点状态、角色、内容 ID、道具、criterion 和
event；新增种子必须先完成契约与内容审核，不能依靠任意字符串透传。

## RpgQuestSummary

Gateway 的 `GET /v1/rpg/state` 返回只读投影：节点、有效 phase、虚拟 inventory、内容引用和
delivery 状态。它不返回儿童原话、Speech Act evidence、request hash、完整学习响应或 profile，
也不存在对应的客户端写接口。

权威 schema：

```text
shared/contracts/v1/rpg-turn.schema.json
shared/contracts/v1/rpg-decision.schema.json
shared/contracts/v1/rpg-quest-summary.schema.json
```

---

# 34. 四端通信关系

完整数据流：

```text
                         ┌──────────────┐
                         │     App      │
                         │   家长控制面   │
                         └──────┬───────┘
                                │
                       配置 / 报告 / 隐私
                                │
                                ▼
┌──────────────┐       ┌──────────────────────┐       ┌──────────────┐
│ Hardware RX5 │◀─────▶│      Backend         │◀─────▶│     Web      │
│ 儿童实时终端   │ WS/API │ Agent + State + KG   │ API/WS │ 调试/运营后台 │
└──────┬───────┘       └──────────────────────┘       └──────────────┘
       │
       │ camera / mic / touch / speaker
       ▼
     儿童
```

## 34.1 Hardware ↔ Backend

使用：

```text
WebSocket
```

处理：

```text
实时 session
audio events
pointing events
TTS
灯效
设备控制
```

## 34.2 App ↔ Backend

使用：

```text
HTTPS API
```

处理：

```text
profile
report
settings
privacy
device management
parent constraints
```

## 34.3 Web ↔ Backend

使用：

```text
HTTPS + WebSocket
```

处理：

```text
debug trace
browser pointing
content review
KG review
system monitoring
manual testing
```
