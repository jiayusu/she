# 目标状态（ASPIRATIONAL）

> 本文件描述**目标**职责地图，不是磁盘现状。
>
> 硬规则、组件归属与导航见仓库根 [`AGENTS.md`](../../AGENTS.md)。
> 本文各节沿用 AGENTS.md 原有编号，以保持既有交叉引用有效。

---

# 24. 建议代码目录

目标架构建议：

```text
agents/
├── director/
│   ├── agent.py
│   ├── policy.py
│   └── schema.py
├── interaction/
│   ├── agent.py
│   ├── prompt.py
│   └── renderer.py
├── learner_model/
│   ├── agent.py
│   ├── mastery.py
│   └── evidence.py
├── curriculum/
│   ├── agent.py
│   ├── scheduler.py
│   └── kg_adapter.py
├── scaffold/
│   ├── agent.py
│   ├── levels.py
│   └── policy.py
├── story/
│   ├── agent.py
│   ├── state.py
│   └── world.py
├── assessment/
│   ├── agent.py
│   ├── rubric.py
│   └── confidence.py
└── parent/
    ├── agent.py
    └── report.py

shared/
├── contracts.py
├── session.py
├── learner_profile.py
├── learning_history.py
└── audit.py
```

现有：

```text
agents/interaction/
agents/director/
backend/knowledge_graph/
backend/memory_store/
backend/pointing/
backend/intel/
backend/digital_twin/
```

继续作为 deterministic service / infrastructure 使用。

---

# 37. 完整仓库级组件地图

```text
clients/
├── hardware-rx5/
│   ├── device runtime
│   ├── camera
│   ├── audio
│   ├── touch / wake
│   ├── led
│   └── websocket client
│
├── web/
│   ├── browser pointing
│   ├── debug console
│   ├── agent trace
│   ├── KG review
│   └── content review
│
└── app/
    ├── parent dashboard
    ├── learner report
    ├── device management
    ├── parent constraints
    └── privacy / erase

backend/
├── agents/
│   ├── director
│   ├── interaction
│   ├── learner_model
│   ├── curriculum
│   ├── scaffold
│   ├── story
│   ├── assessment
│   └── parent
│
├── engine/
├── kb/
├── store/
├── pointing/
├── intel/
├── safety/
├── asr/
├── vision/
└── device_gateway/
```

实际仓库当前目录不要求立即改成上述形式；这是目标职责地图。
