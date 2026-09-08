# Shared State Layer

> 六类共享状态的结构、现有记忆系统的迁移映射，以及长期学习写入规则。
>
> 硬规则、组件归属与导航见仓库根 [`AGENTS.md`](../../AGENTS.md)。
> 本文各节沿用 AGENTS.md 原有编号，以保持既有交叉引用有效。

---

# 11. Shared State Layer

## 11.1 Session State

生命周期：单次会话 / 数分钟。

保存：

```text
session_id
current_scene
current_object
current_learning_goal
current_story_state
current_scaffold_level
recent_turns
stuck_streak
```

主要对应现有：

```text
工作记忆
engine context
ScriptState
```

---

## 11.2 Learner Profile

生命周期：数周至数月。

保存：

```text
mastery graph
candidate weaknesses
confirmed weaknesses
response behavior
pronunciation patterns
interests
emotion / resistance patterns
preferred scaffold
```

---

## 11.3 Knowledge Graph

保存：

- 通用儿童英语知识；
- YLE / CEFR 词汇；
- 概念关系；
- 万物模式事实；
- 课程关联。

物理实现：

```text
kb/data/kg.db
FAISS
RotatE
PPR
```

---

## 11.4 Story Memory

保存：

```text
StoryArc
角色
章节
现实物件剧情
第一次事件
高光事件
跨天续接
```

底层使用现有情景记忆 / StoryArc。

---

## 11.5 Learning History

每一次真实学习事件保存：

```json
{
  "ts": "",
  "scene": "",
  "learning_goal": "",
  "child_utterance": "",
  "assessment": {},
  "scaffold_level": 0,
  "language_level": 0,
  "target_reached": true,
  "emotion": {},
  "salience": 0.0
}
```

---

## 11.6 Teaching Skill Library

保存可复用教学流程：

```text
触发条件
适用学习问题
教学动作
脚手架策略
成功标准
回退动作
```

例如：

```text
skill: elicit_known_noun
trigger:
  child comprehends target but rarely outputs
procedure:
  L2 binary choice
  → L3 sentence starter
  → L5 model if still silent
success:
  target appears intelligibly
```

程序性记忆可作为该层底座，但不再代表一个“程序记忆 Agent”。

---

# 12. 现有记忆系统迁移映射

旧五记忆机制继续保留，但角色改变：

| 旧设计 | 新架构位置 |
|---|---|
| 工作记忆 | Session State |
| 情景记忆 | Story Memory + Learning History |
| 语义记忆 | Knowledge Graph |
| 显著性记忆 | Learner Profile / Story Memory 的 salience 标记 |
| 程序性记忆 | Teaching Skill Library / 定时任务 |

现有 `store` 服务继续作为共享存储基础设施。

主要接口：

```text
POST /memory/episodes
GET  /memory/recall?query=
POST /memory/consolidate
GET  /memory/procedural/due
POST /memory/snapshot
POST /memory/rollback/{v}

POST /memory/working/{sid}/push
GET  /memory/working/{sid}
POST /memory/session/{sid}/state
POST /memory/whitelist
GET  /memory/conflicts
POST /memory/conflicts/{id}/resolve
POST /memory/erase
```

### 红线

Agent 不允许直接操作 SQLite / FAISS 文件。

必须通过 store / KG 接口。

---

# 18. 长期学习写入规则

不得：

```text
一次错误
→ 直接永久记录“孩子不会 X”
```

必须区分：

```text
raw event
candidate evidence
confirmed learner state
```

建议状态：

```text
OBSERVED_ONCE
REPEATED
CONFIRMED
RESOLVED
```

只有满足至少以下条件之一才能进入 confirmed：

- 不同上下文重复出现；
- 多次高置信 Assessment；
- 主动输出 / 迁移证据明确；
- 人工家长/教师确认。

ASR 低置信、外部服务错误、题目歧义不得写成 confirmed weakness。
