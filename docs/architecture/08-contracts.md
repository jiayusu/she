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

## TeachingAction

```json
{
  "learning_goal": "",
  "target_expression": "",
  "language_level": 0,
  "scaffold_level": 0,
  "teaching_action": "",
  "correction_policy": "",
  "story_action": "",
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
  "pronunciation_intelligibility": 0.0,
  "assessment_confidence": 0.0,
  "learning_evidence": []
}
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
