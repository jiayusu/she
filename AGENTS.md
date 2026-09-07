# AGENTS.md

> 项目级 Agent 架构与后台组件协作约定
> 适用范围：儿童英语启蒙穿戴设备后台、LLM 剧情引擎、知识图谱、记忆、指向识别、数据情报及后续 Agent 实现。

---

## 0. 项目目标

本项目服务 **4–8 岁英语启蒙阶段儿童**，核心目标不是“回答英语问题”，而是：

> **在家庭真实场景中，通过现实物件、剧情和最小必要提示，让孩子从“能听懂 / 能跟读”逐步走到“主动开口”。**

产品交互原则：

1. **开口是核心行为目标**：孩子的英语表达应推动剧情或现实物件反馈。
2. **儿童前台只面对一个稳定角色**：多 Agent 全部隐藏在后台。
3. **不把后台系统组织方式暴露给儿童**：儿童不需要知道课程、评估、记忆、路由等模块存在。
4. **先保证愿意说，再优化说得准**：优先 Recast（吸收式纠错），避免打断式纠错。
5. **教学难度遵循 i+1**：结合 CEFR / YLE、知识图谱、复习状态和儿童当前输出能力。
6. **所有长期学习判断必须可追踪、可回滚**。
7. **儿童实时对话不直接访问开放互联网**；外部内容必须经过结构化、审核，再进入 KG。

---

# 1. 总体架构

系统不是单一“AI 后台”，而是四层产品系统：

```text
┌──────────────────────────────────────────────┐
│                 ① 硬件端                     │
│ 地瓜 RX5 + 摄像头 + 麦克风/扬声器 + 触摸/按键   │
│ 唤醒、采音、拍照/短帧、播放、灯效、设备状态       │
└─────────────────────┬────────────────────────┘
                      │ 实时事件 / 音频 / 图像 / 控制
                      ▼
┌──────────────────────────────────────────────┐
│                 ② Web 端                     │
│ 开发调试 / 浏览器版指向识别 / 演示 / 运营后台      │
│ 摄像头调试、会话可视化、Agent trace、KG/内容审核   │
└─────────────────────┬────────────────────────┘
                      │ HTTPS / WebSocket
                      ▼
┌──────────────────────────────────────────────┐
│                 ③ 服务端                     │
│                                              │
│  感知 → Agent 教学层 → Shared State → 基础服务   │
│                                              │
│  ASR / Vision / Emotion                      │
│            ↓                                 │
│  Interaction Agent                           │
│            ↓                                 │
│  Learning Director                           │
│       ┌────┼────┬────┬────┐                  │
│       ↓    ↓    ↓    ↓    ↓                  │
│   Learner Curriculum Scaffold Story Assessment│
│            ↓                                 │
│  engine / kb / store / safety / intel        │
└─────────────────────┬────────────────────────┘
                      │ 用户数据 / 报告 / 配置
                      ▼
┌──────────────────────────────────────────────┐
│                 ④ App 端                     │
│ 家长端                                        │
│ 设备管理、学习报告、目标设置、隐私与数据管理       │
└──────────────────────────────────────────────┘
```

其中儿童实时交互链路仍采用：

> **前台单一角色 + 后台多 Agent + 共享状态层 + 确定性后台组件**

```text
儿童
 │
 │ 语音 / 触摸 / 指物
 ▼
硬件端 RX5
 │
 ▼
感知层
 │
 ▼
┌────────────────────────────┐
│ Interaction Agent          │
│ 前台唯一角色：王冠精灵 / 小P │
└─────────────┬──────────────┘
              ▼
┌────────────────────────────┐
│ Learning Director          │
│ 学习导演 / 总调度器          │
└─────────────┬──────────────┘
              │
     ┌────────┼───────────────┐
     ▼        ▼               ▼
Learner     Curriculum      Scaffold
Model       Agent           Agent
Agent
     │        │               │
     └────────┼───────┬───────┘
              ▼       ▼
          Story     Assessment
          World     Agent
          Agent
              │       │
              └───┬───┘
                  ▼
           Interaction Agent
                  │
                  ▼
             TTS / 灯效 / 动作
                  │
                  ▼
                儿童
                  ↺
```

后台 Agent 不直接拥有数据库，不绕过安全规则。

所有长期状态统一写入 **Shared State Layer**：

```text
Shared State Layer
├── Session State
├── Learner Profile
├── Knowledge Graph
├── Story Memory
├── Learning History
└── Teaching Skill Library
```

现有“工作记忆 / 情景记忆 / 语义记忆 / 显著性记忆 / 程序性记忆”继续作为存储机制存在，但 **不再映射成五个对话 Agent**。

---

# 2. Agent 清单

实时主链路共 7 个 Agent。

| Agent | 核心问题 | 是否直接对儿童说话 |
|---|---|---|
| Interaction Agent | “这一句话具体怎么说？” | 是 |
| Learning Director | “这一轮系统到底应该做什么？” | 否 |
| Learner Model Agent | “这个孩子现在会什么、卡在哪里？” | 否 |
| Curriculum Agent | “现在最值得练什么？” | 否 |
| Scaffold Agent | “需要多少帮助才能让孩子成功开口？” | 否 |
| Story World Agent | “为什么孩子现在愿意说这句话？” | 否 |
| Assessment Agent | “这次表现意味着什么？” | 否 |

可选异步 Agent：

| Agent | 作用 |
|---|---|
| Parent Agent | 给家长生成学习摘要，接收家长输入，不参与儿童实时对话 |

---

# 3. Interaction Agent

## 3.1 做什么

Interaction Agent 是 **唯一面向儿童的语言出口**。

职责：

- 把后台教学决策转换成儿童能理解的自然语言。
- 保持固定角色人格、音色和关系感。
- 执行 Recast，不直接指出错误。
- 控制句长、词汇难度和中文脚手架。
- 表达 Story World Agent 指定的剧情反馈。
- 当 LLM 不可用时走模板兜底，保证绝不空响应。

## 3.2 不做什么

不得自行决定：

- 今天学什么；
- 孩子处于什么能力阶段；
- 一个错误是否需要长期记录；
- 是否更新 KG；
- 是否修改长期 Learner Profile；
- 是否改变教学策略；
- 是否访问开放互联网。

## 3.3 输入

```json
{
  "teaching_action": {},
  "story_action": {},
  "scaffold_level": 0,
  "child_utterance": "",
  "asr_result": {},
  "assess_result": {},
  "session_context": {},
  "approved_facts": []
}
```

## 3.4 输出

```json
{
  "text": "",
  "emotion_tag": "",
  "voice_id": "",
  "interaction_type": "",
  "expected_child_action": ""
}
```

## 3.5 对应现有后台

主要复用：

```text
engine/src/she_engine/
├── engine.py
├── recast.py
├── levels.py
├── schema.py
├── templates.py
├── llm.py
├── safety.py
└── events.py
```

现有剧情引擎已提供：

- Recast；
- L0–L5 分级句式；
- JSON Schema；
- 模板兜底；
- LLM Provider；
- 安全挂钩；
- latency / cost 埋点。

### 迁移要求

现有 `minister` / “五大臣人格路由”属于旧架构。

保留：

- 人格资产版本化；
- voice_id；
- light_color；
- 提示词版本；
- 模板库；
- rollback。

删除其“按意图切换不同后台 Agent”的架构含义。

新的前台应默认表现为 **一个稳定儿童角色**。

---

# 4. Learning Director

## 4.1 做什么

Learning Director 是实时主链路的 **总调度器**。

它不负责写最终儿童话术，而负责产生一次结构化教学决策。

每轮回答：

> **“根据当前孩子、当前场景和当前课程状态，下一步应该做什么？”**

职责：

- 汇总 Learner Model、Curriculum、Scaffold、Story、Assessment 的结果。
- 选择当前唯一 primary learning goal。
- 控制当前轮是否：
  - 提问；
  - 重邀；
  - 提示；
  - Recast；
  - 剧情推进；
  - 自由探索；
  - 暂停教学目标。
- 决定这一轮成功条件。
- 控制多 Agent 冲突：最终一轮只能有一个教学动作。
- 对低置信结果选择保守动作，不强行更新长期学习状态。

## 4.2 输入

```json
{
  "session_state": {},
  "learner_state": {},
  "curriculum_proposal": {},
  "scaffold_proposal": {},
  "story_proposal": {},
  "assessment": {},
  "detected_object": null,
  "emotion_signal": null
}
```

## 4.3 输出

```json
{
  "learning_goal": "",
  "target_expression": "",
  "teaching_action": "",
  "scaffold_level": 0,
  "correction_policy": "recast|ignore|explicit_later",
  "story_action": "",
  "success_condition": {},
  "memory_policy": "no_write|candidate|confirmed",
  "next_state": ""
}
```

## 4.4 核心规则

1. 每轮最多一个 primary goal。
2. 儿童连续卡壳时优先降低输出要求，不提高内容难度。
3. 情绪安全优先于课程推进。
4. 不确定是偶然失误还是能力缺口时：
   - `memory_policy = candidate`
   - 不直接写成 confirmed weakness。
5. 已有剧情状态必须连续，不允许因后台 Agent 切换导致“串台”。

## 4.5 对应现有后台

旧 `03 五大臣 Agent 调度` 中以下能力迁移到 Learning Director / Shared State：

- 意图识别；
- 上下文拼装；
- 记忆写入调度；
- 工具边界；
- 审计日志；
- 巩固任务触发。

旧接口：

```text
POST /agent/dispatch
```

后续应升级为学习决策接口，而不是返回 `minister`。

建议目标接口：

```text
POST /agent/direct
```

输入：

```json
{
  "session_id": "",
  "utterance": "",
  "asr": {},
  "emotion": {},
  "object_context": {}
}
```

输出：

```json
{
  "learning_goal": "",
  "teaching_action": "",
  "scaffold_level": 0,
  "story_action": "",
  "success_condition": {},
  "ctx_bundle": {}
}
```

---

# 5. Learner Model Agent

## 5.1 做什么

Learner Model Agent 维护 **儿童当前真实能力状态**。

它不回答“学过没有”，而回答：

> **“这个词 / 句型现在处在哪一个掌握阶段？”**

维护内容：

- 词汇掌握状态；
- 句型掌握状态；
- 听懂能力；
- 跟读能力；
- 提示后输出；
- 主动输出；
- 跨场景迁移；
- 发音可理解度；
- 响应延迟；
- 所需 scaffold 等级；
- 高频错误模式；
- 开口意愿；
- 兴趣主题；
- 紧张 / 抗拒信号。

## 5.2 能力状态机

词汇和表达不得只使用 `known / unknown`。

建议：

```text
UNSEEN
  ↓
HEARD
  ↓
COMPREHENDED
  ↓
IMITATED
  ↓
PROMPTED_OUTPUT
  ↓
SPONTANEOUS_OUTPUT
  ↓
TRANSFERRED
```

状态只能基于 Assessment evidence 更新。

单次错误不能直接将已掌握状态降级。

## 5.3 输入

```json
{
  "assessment_event": {},
  "recent_learning_history": [],
  "current_profile": {},
  "relevant_memories": []
}
```

## 5.4 输出

```json
{
  "mastery_updates": [],
  "candidate_weaknesses": [],
  "confirmed_weaknesses": [],
  "interest_updates": [],
  "recommended_scaffold": 0,
  "confidence": 0.0
}
```

## 5.5 存储

写入：

- Learner Profile；
- Learning History；
- 情景记忆；
- 显著性记录。

不得直接修改 KG 的通用教育知识。

---

# 6. Curriculum Agent

## 6.1 做什么

Curriculum Agent 决定：

> **“现在最值得练什么？”**

它把长期学习目标映射到当前现实场景。

职责：

- 根据 Learner Profile 选择 primary target。
- 从 KG 获取相关词 / 句型 / 概念。
- 实现 i+1。
- 安排间隔重复。
- 做螺旋上升。
- 做交错学习。
- 优先强化“听懂 → 跟读 → 提示输出 → 主动输出 → 迁移”的薄弱环节。
- 利用当前物体和场景选择自然学习内容。

## 6.2 输入

```json
{
  "learner_profile": {},
  "current_scene": "",
  "detected_object": null,
  "recent_targets": [],
  "review_due": [],
  "story_state": {}
}
```

## 6.3 输出

```json
{
  "primary_target": "",
  "review_targets": [],
  "i_plus_1_target": "",
  "difficulty_level": "L0-L5",
  "reason": "",
  "priority": 0.0
}
```

## 6.4 使用 KG

KG 是课程约束和事实来源，不是自由聊天记忆。

主要调用：

```text
GET  /kg/facts/{word}
POST /kg/retrieve
GET  /kg/packs/{level}
```

现有 KG 提供：

- Cambridge YLE / CEFR-J 词表；
- ConceptNet 清洗知识边；
- `facts()`；
- `next_words()`；
- FAISS + PPR 检索；
- L0–L5 内容包；
- 热更新；
- snapshot / rollback。

## 6.5 KG 写入原则

Curriculum Agent **不能直接写 KG**。

新增通用知识必须走：

```text
候选知识
→ 规则校验
→ 冲突检测
→ 审核
→ /kg/edges:batch
```

孩子个人经历不得直接变成公共 KG 事实。

---

# 7. Scaffold Agent

## 7.1 做什么

Scaffold Agent 负责：

> **“为了让这个孩子这一轮成功开口，需要给多少帮助？”**

它是“开口难”问题的核心教学 Agent。

## 7.2 Scaffold Levels

```text
L0 自由输出
"What do you want?"

L1 情景暗示
"The fridge is waiting..."

L2 二选一
"Milk or water?"

L3 句首提示
"I want..."

L4 填空
"I want ___."

L5 完整示范
"Say: I want milk."

L6 只输入，不要求输出
"Milk! Yummy!"
```

注：这里的 Scaffold Level 与剧情引擎的语言难度 L0–L5 是两个概念，代码中必须使用不同字段名：

```text
language_level
scaffold_level
```

不得混用。

## 7.3 动态规则

```text
连续成功
→ scaffold_level 降低

连续失败
→ scaffold_level 提高

出现明显抗拒 / 紧张
→ 降低任务要求或进入 L6

自由输出成功
→ 记录 spontaneous evidence
```

## 7.4 输入

```json
{
  "learning_goal": "",
  "learner_state": {},
  "recent_attempts": [],
  "emotion_signal": null
}
```

## 7.5 输出

```json
{
  "scaffold_level": 0,
  "prompt_pattern": "",
  "fallback_pattern": "",
  "max_attempts": 0
}
```

## 7.6 与现有引擎关系

现有：

```text
stuck.py
levels.py
engine.handle_silence()
```

可复用底层机制。

但原有“连续 2 次卡壳 → 降语言 L”应拆分：

```text
语言难度 language_level
≠
开口脚手架 scaffold_level
```

优先提高 `scaffold_level`，而不是立即降低语言课程等级。

---

# 8. Story World Agent

## 8.1 做什么

Story World Agent 把教学目标转换成：

> **“孩子为什么愿意现在说这句话？”**

它负责动机，不负责课程判断。

职责：

- 维护现实物件拟人化设定；
- 生成小规模剧情事件；
- 保持 StoryArc 连贯；
- 把目标语言变成“推动世界的动作”；
- 给开口即时产生世界反馈；
- 从 Story Memory 恢复跨天剧情。

示例：

```text
教学目标：open

Story World：
冰箱精灵被锁住，只有听到英文咒语才开门。

孩子："Open!"

结果：
剧情推进，冰箱回应。
```

## 8.2 输入

```json
{
  "learning_goal": "",
  "target_expression": "",
  "detected_object": null,
  "story_memory": {},
  "child_interests": []
}
```

## 8.3 输出

```json
{
  "story_action": "",
  "world_role": "",
  "child_motivation": "",
  "success_feedback": "",
  "story_state_patch": {}
}
```

## 8.4 与现有剧情引擎关系

复用：

- `state_machine.py`
- StoryArc 持久化
- 模板兜底
- engine response generation

不再采用：

```text
朝会 → 某大臣
探险 → 某大臣
睡前 → 某大臣
```

来决定不同后台 Agent。

剧情状态只描述：

```text
scene
chapter
objective
world_state
```

---

# 9. Assessment Agent

## 9.1 做什么

Assessment Agent 是 **隐藏式学习评估器**。

它判断的是：

> **“这一次表现提供了什么学习证据？”**

评估维度：

- 是否完成目标语义；
- 是否出现目标词 / 句型；
- 主动输出还是提示后输出；
- 使用了几级 scaffold；
- 响应延迟；
- 发音是否影响理解；
- 是否是重复错误；
- 是否存在情绪压力；
- ASR / evaluator 是否可能不可靠。

## 9.2 不做什么

不得直接面向儿童输出：

- “你错了”；
- 分数；
- 长篇语法说明；
- 强制重读。

这些信息先进入后台。

## 9.3 输入

```json
{
  "child_utterance": "",
  "asr_result": {},
  "pronunciation_result": {},
  "learning_goal": "",
  "success_condition": {},
  "scaffold_level": 0,
  "response_latency_ms": 0,
  "emotion_signal": null
}
```

## 9.4 输出

```json
{
  "target_reached": true,
  "semantic_correctness": 0.0,
  "spontaneous": false,
  "prompt_level_used": 0,
  "pronunciation_intelligibility": 0.0,
  "error_type": null,
  "assessment_confidence": 0.0,
  "learning_evidence": []
}
```

## 9.5 评估写入规则

```text
高置信 + 多次重复
→ confirmed learner update

单次低置信错误
→ candidate evidence

ASR / evaluator 可疑
→ no long-term update
```

Recast 所需 corrected / target_form 应来自评估组件，不由 Interaction Agent 自己发明。

---

# 10. Parent Agent（异步）

Parent Agent 不进入儿童实时对话。

## 做什么

- 每日 / 每周学习摘要；
- 汇总主动开口次数；
- 汇总无提示输出；
- 汇总新增主动词汇；
- 汇总当前主要学习障碍；
- 给出下一阶段建议；
- 接收家长输入并转成后台约束。

输入示例：

```text
今天只有 10 分钟
最近在学动物
明天要去动物园
孩子今天情绪不好
```

输出转换成：

```json
{
  "session_budget": 600,
  "preferred_topics": ["animals"],
  "next_day_context": "zoo",
  "teaching_pressure": "low"
}
```

不得让家长的单次主观判断直接覆盖 Learner Profile 的客观学习证据。

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

# 13. 指向识别模块

路径来源：当前 Pointing 浏览器模块。

## 做什么

识别：

> **孩子当前指的是哪个现实物体。**

流程：

```text
触发
→ 5 帧采集
→ MediaPipe 手势识别
→ YOLO 物体检测
→ 射线选物
→ 置信度判断
→ 必要时确认
→ detected_object
```

关键规则：

- ≥3 帧命中：轻确认；
- 1–2 帧：重确认；
- 0 帧：中心框兜底；
- 最多 2 轮确认；
- 指向窗口结束必须关闭摄像头；
- 原图默认不落盘。

输出进入：

```text
Learning Director
Curriculum Agent
Story World Agent
```

它不是 Agent，不负责生成课程。

---

# 14. KG 后台

目录：

```text
kb/
```

## 做什么

KG 是：

> **儿童可用、可审查、可回滚的通用英语知识和课程约束层。**

负责：

- YLE / CEFR-J 词表；
- ConceptNet 知识关系；
- 清洗；
- 嵌入；
- 检索；
- 万物事实；
- 热更新；
- 冲突检测；
- snapshot / rollback。

关键接口：

```text
POST /kg/edges:batch
POST /kg/snapshot
POST /kg/rollback/{v}
GET  /kg/packs/{level}
POST /kg/runtime-consolidate
GET  /kg/conflicts
POST /kg/retrieve
GET  /kg/facts/{word}
```

### KG 不负责

- 保存某一个孩子的私人学习画像；
- 保存聊天全文；
- 决定孩子今天练什么；
- 决定脚手架等级；
- 自由从互联网补知识。

---

# 15. 数据情报后台

目录：当前 `intel` 模块。

## 做什么

数据情报只服务：

- 内容运营；
- 家长痛点研究；
- 万物模式知识池；
- 舆情监控。

流程：

```text
外部内容
→ 抓取
→ 排序/去重
→ LLM 结构化
→ 敏感内容过滤
→ 人工审核
→ KG
```

### 架构红线

```text
外部搜索
≠
儿童实时 Agent Tool
```

任何外部互联网内容进入儿童产品前必须：

```text
结构化
→ 人工审核
→ KG 热更新
→ 可回滚
```

不得：

```text
儿童问一句
→ Agent 即时搜索知乎/互联网
→ 直接回答儿童
```

---

# 16. 单轮实时执行流程

标准单轮顺序：

```text
1. 儿童输入
   ├── 语音
   ├── 触摸
   └── 指物

2. 感知层
   ├── ASR
   ├── 发音/语言评估
   ├── 情绪信号
   └── 指向识别

3. Session State 更新

4. Learner Model Agent
   → 当前能力状态

5. Curriculum Agent
   → primary target / review / i+1

6. Scaffold Agent
   → scaffold_level

7. Story World Agent
   → story_action

8. Learning Director
   → 生成唯一 teaching_action

9. Interaction Agent
   → 生成儿童听到的一句话

10. 内容安全过滤

11. TTS / 灯效 / 世界反馈

12. 儿童回应

13. Assessment Agent
   → learning evidence

14. Learner Model Agent
   → 更新 learner state

15. 写入
   ├── Session State
   ├── Learning History
   ├── Story Memory
   └── candidate / confirmed learner evidence

16. 下一轮
```

---

# 17. 决策优先级

当多个 Agent 建议冲突时：

```text
安全
>
情绪安全
>
让孩子愿意继续互动
>
当前 primary learning goal
>
剧情连续性
>
复习效率
>
内容丰富度
```

例如：

```text
Curriculum:
现在应该练过去式

Scaffold:
孩子已经连续失败

Emotion:
明显挫败
```

最终 Learning Director 应选择：

```text
降低要求 / 暂停目标
```

而不是继续强推课程。

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

---

# 19. Recast 与纠错原则

实时儿童交互默认：

```text
错误
→ Interaction Agent 用正确形式自然回应
```

例如：

```text
Child:
"I like apple."

Agent:
"I like apples too!"
```

不得默认：

```text
"No, you should say apples."
```

显式纠错只能由 Learning Director 在明确教学场景下选择。

---

# 20. 工具边界

## Agent 可以调用

- KG 检索；
- Memory API；
- 本地剧情状态；
- 已批准教学 Skill；
- 指向识别结果；
- 日程 / 程序性任务；
- 已审核本地内容。

## Agent 不可绕过

- 内容安全；
- 隐私；
- 摄像头生命周期；
- 数据删除；
- KG 审核；
- Memory 审计；
- evaluator / assessment 固定约束。

## Agent 不允许

- 直接改 verifier；
- 直接改安全过滤；
- 直接写 KG 数据文件；
- 直接写 Memory 数据文件；
- 直接调用知乎 / 开放互联网实时回答儿童；
- 将低置信错误永久写入 Learner Profile。

---

# 21. 故障降级

任何实时路径必须：

> **不空响应。**

建议顺序：

```text
LLM 正常
↓失败
LLM retry ×1
↓失败
场景模板
↓失败
硬编码安全回应
```

KG 不可用：

```text
不生成未经验证的事实
→ 使用通用安全剧情 / 引导换对象
```

Memory 不可用：

```text
继续当前 session
→ 不伪造跨天记忆
```

视觉不确定：

```text
确认物体
→ 第二候选
→ 优雅退出
```

---

# 22. 旧五大臣架构处理方式

旧文档 `03 五大臣 Agent 调度 PRD` 不再作为目标 Agent 架构。

以下概念废弃：

```text
一个意图 → 一个大臣 Agent
一个大臣 → 一套独立记忆
切换大臣 = 切换后台认知主体
```

原因：

- 不符合幼儿前台关系稳定性；
- 容易导致记忆碎片；
- 将“记忆类型”误做成“Agent 职责”；
- 难以形成统一 Learner Model；
- 教学决策缺少中心协调。

以下资产仍可保留：

```text
角色名
音色
灯色
剧情人物
模板
DLC 角色
```

它们属于：

> **Story / Presentation Assets**

而不是后台认知 Agent。

---

# 23. 新旧代码迁移原则

## 保留

### engine

保留：

```text
recast.py
levels.py
state_machine.py
context.py
stuck.py
schema.py
templates.py
llm.py
memory.py
safety.py
events.py
```

### kb

整体保留。

### store

整体保留。

### pointing

整体保留。

### intel

整体保留，且继续与儿童实时路径隔离。

## 重构

```text
engine/router.py
prompts.py 中的 minister routing
03 Agent 调度
```

目标：

```text
intent → minister
```

改为：

```text
observation
→ learner state
→ curriculum
→ scaffold
→ story
→ learning decision
→ interaction
```

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
engine/
kb/
store/
pointing/
intel/
```

继续作为 deterministic service / infrastructure 使用。

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

# 26. 测试要求

新增 Agent 不能只测试“LLM 回答看起来不错”。

至少测试：

## Interaction Agent

- Recast 不直接指出错误；
- language_level 句长限制；
- 无空响应；
- approved facts 之外不生成事实型万物回答。

## Learning Director

- 每轮只有一个 primary goal；
- 情绪风险覆盖课程推进；
- 低置信 assessment 不产生 confirmed memory write；
- 多 Agent 冲突有确定优先级。

## Learner Model

- 单次错误不直接降级 mastery；
- repeated evidence 才 confirmed；
- spontaneous evidence 权重大于 prompted evidence。

## Curriculum

- 不超出 language_level；
- i+1；
- 到期复习优先；
- 当前物体与学习目标相关。

## Scaffold

- 连续失败提高 scaffold；
- 连续成功降低 scaffold；
- 抗拒时允许只输入不要求输出。

## Story

- 不改变教学目标；
- 跨天 StoryArc 可恢复；
- 世界反馈与儿童开口行为绑定。

## Assessment

- 区分 spontaneous / prompted；
- 低 ASR 置信度降低 assessment_confidence；
- 不直接修改长期状态。

---

# 27. 系统级北极星指标

现有技术指标继续保留，同时新增学习指标。

## 交互

```text
端到端回应 ≤ 2.5s
无空响应 = 100%
指向目标准确率 ≥ 85%
```

## 开口

重点监控：

```text
主动开口次数
无提示输出占比
提示等级变化
平均响应延迟
剧情推进所需开口
```

## 学习

重点监控：

```text
PROMPTED_OUTPUT → SPONTANEOUS_OUTPUT 转化率
SPONTANEOUS_OUTPUT → TRANSFERRED 转化率
复习后保持率
错误重复率
```

## 安全

```text
打断式纠错极低
错误长期记忆写入率
低置信评估长期写入率 = 0
未经审核外部知识进入儿童输出 = 0
```

---

# 28. Coding Agent 工作纪律

对本仓库进行修改的 Coding Agent 必须遵守：

1. **先确认改的是 Agent 层还是基础设施层。**
2. 不把每个功能都做成 Agent；确定性逻辑优先普通代码。
3. 不恢复“五大臣=五后台 Agent”的旧架构。
4. 儿童可见人格只有 Interaction Agent。
5. 所有长期状态通过 Shared State API 写入。
6. 任何 KG 修改必须可审查、可回滚。
7. 外部互联网数据不得进入儿童实时链路。
8. 安全过滤、隐私、数据删除属于 trust boundary，Agent 不可修改或绕过。
9. 新 Agent 输出必须有明确 Schema。
10. 每个新 Agent 必须写清：
    - 输入；
    - 输出；
    - 做什么；
    - 不做什么；
    - 使用哪些后台组件；
    - 写哪些状态；
    - 失败怎么降级。
11. 不允许仅通过增加 Prompt 复杂度替代明确状态和代码逻辑。
12. 所有架构修改必须补测试和审计字段。

---

# 29. 当前后台组件一览

| 组件 | 做什么 | 在新架构中的位置 |
|---|---|---|
| `engine` | LLM 输出、Recast、语言等级、剧情状态、模板、降级 | Interaction + Story 的执行底座 |
| `kb` | 儿童英语通用知识、词汇关系、检索、热更新 | Curriculum / Story 的知识底座 |
| `store` | 工作/情景/显著性/程序性记忆、快照、删除 | Shared State 持久化底座 |
| `pointing` | 手势 + 物体指向识别 | 感知层 |
| `intel` | 外部内容采集、运营情报、人工审核入 KG | 离线内容生产层 |
| ASR / 发音评估 | 语音识别与语言评估 | Assessment 上游；具体实现不在本批文档 |
| Safety | 儿童内容安全硬钩子 | Trust Boundary；具体实现不在本批文档 |
| TTS / 设备灯效 | 输出执行 | Interaction 下游 |

---

# 30. 最终设计原则

```text
前台：
一个孩子信任的角色

后台：
一支分工明确的教学团队

状态：
统一共享，不按角色割裂

知识：
可审核、可回滚

教学：
先诊断，再选目标，再给最小提示

评估：
隐藏进行，不打断孩子

长期学习：
一次错误不是能力结论

多 Agent：
按教学职责分，不按人格分
```

系统最终要实现的不是：

> “多个 AI 角色陪孩子聊天。”

而是：

> **一个能够持续理解这个孩子、选择下一步学习目标、用最小脚手架推动主动开口，并在现实场景中形成长期学习闭环的后台教学系统。**

# 31. 硬件端：地瓜 RX5 + 摄像头

硬件端是儿童真正使用的实时交互终端。

## 31.1 做什么

硬件端负责：

```text
唤醒
采集语音
采集图像/短帧
触摸/按键事件
设备状态上报
播放 TTS
灯效/提示反馈
断网时基础兜底
```

硬件端应尽量承担 **确定性、低延迟、隐私敏感** 的工作。

推荐职责：

```text
RX5
├── Wake / Button / Touch Event
├── Audio Capture
├── Camera Capture
├── Local Vision Preprocess
├── Pointing / Object Candidate
├── Device State
├── Audio Playback
├── LED / Light Feedback
└── Network / Reconnect / Local Fallback
```

## 31.2 摄像头负责什么

摄像头只为“当前现实场景理解”提供输入。

典型输出：

```json
{
  "frame_id": "",
  "detected_objects": [
    {
      "label": "fridge",
      "bbox": [0, 0, 0, 0],
      "confidence": 0.0
    }
  ],
  "pointing_target": "fridge",
  "pointing_confidence": 0.0
}
```

摄像头链路不负责：

- 判断今天学什么；
- 判断孩子是否掌握某词；
- 直接生成回复；
- 直接写长期记忆。

视觉结果只能作为：

```text
Learning Director
Curriculum Agent
Story World Agent
```

的环境上下文。

## 31.3 本地与服务端边界

优先本地：

```text
唤醒
触摸
摄像头生命周期
基础手势判断
图像裁切
设备状态
隐私控制
本地兜底提示
```

可以送服务端：

```text
ASR 所需音频
必要的裁切图像 / 特征
pointing/object 结构化结果
设备事件
```

不得默认持续上传：

```text
全天摄像头视频
无触发环境音
无关家庭场景原图
```

## 31.4 硬件端接口建议

### 设备 → 服务端

```text
WS /device/session
```

事件：

```json
{
  "type": "wake|touch|audio|pointing|device_state",
  "device_id": "",
  "session_id": "",
  "ts": 0,
  "payload": {}
}
```

### 服务端 → 设备

```json
{
  "type": "speak|led|capture|stop_capture|fallback",
  "session_id": "",
  "payload": {}
}
```

## 31.5 硬件端红线

1. 摄像头必须事件触发，不默认持续上传。
2. 采集窗口结束后必须停止采集。
3. 设备端不保存儿童原始视频作为长期学习数据。
4. Agent 不允许自行打开摄像头；必须通过硬件权限层。
5. 网络失败时必须有确定性回应，不允许孩子得到空响应。
6. 设备 ID 只用于设备会话，不作为儿童身份画像本身。

---

# 32. Web 端

Web 端不是儿童主要学习终端。

它承担三类职责：

```text
A. 浏览器版交互验证
B. 开发 / 调试 / Demo
C. 运营 / 审核后台
```

## 32.1 浏览器交互验证

现有 pointing 浏览器模块继续保留。

做什么：

- 手机 / 平板摄像头调用；
- MediaPipe 手势识别；
- YOLO 物体框；
- 指向确认；
- 浏览器版万物模式 MVP；
- 在 RX5 硬件完全稳定前验证交互。

它与硬件版使用相同的结构化输出契约：

```json
{
  "detected_object": "",
  "bbox": [],
  "pointing_confidence": 0.0,
  "confirmation_state": ""
}
```

因此：

```text
Web 摄像头
和
RX5 摄像头
```

只允许实现不同，不能产生两套上层 Agent API。

## 32.2 开发调试台

Web 调试端应能查看：

```text
当前 Session
当前学习目标
Learner Model 摘要
Curriculum Proposal
Scaffold Level
Story State
Assessment Result
Agent 调用顺序
LLM latency
fallback
memory write
KG retrieval
```

推荐页面：

```text
/debug/session/{session_id}
```

主要用于回答：

> “系统为什么刚刚说了这句话？”

必须展示结构化决策链，而不是只展示最终 LLM 输出。

## 32.3 Agent Trace

Web 调试端建议显示：

```text
Perception
↓
Learner Model
↓
Curriculum
↓
Scaffold
↓
Story
↓
Director
↓
Interaction
↓
Assessment
```

每一步至少显示：

```text
input summary
output
confidence
latency
fallback
```

不得默认显示敏感原始儿童音视频。

## 32.4 运营后台

Web 端还负责：

- KG 冲突审核；
- 外部内容审核；
- Prompt / Teaching Skill 版本查看；
- 模板管理；
- 数据情报周报；
- 系统指标；
- 回滚操作；
- 测试设备状态。

现有 `intel` 人工审核工作台属于这里。

KG 热更新必须：

```text
候选
→ Web 审核
→ approve
→ KG
```

## 32.5 Web 端不做什么

Web 端不得：

- 自己保存另一份 Learner Profile；
- 绕过服务端直接写 KG 数据文件；
- 绕过 store 直接改儿童记忆；
- 把调试 Prompt 暴露给儿童；
- 让浏览器版和硬件版形成两套教学逻辑。

---

# 33. App 端：家长端

App 是 **家长与系统之间的控制面**，不是儿童实时教学 Agent。

## 33.1 做什么

App 负责：

```text
设备绑定
儿童档案
学习目标
学习报告
历史趋势
兴趣设置
使用时间
家长反馈
隐私授权
数据导出/删除
设备设置
```

## 33.2 首页建议数据

App 首页重点显示真实学习进展，而不是“学习时长”。

推荐：

```text
今日主动开口次数
无提示输出次数
最高完成 Scaffold Level
新增主动词汇
跨场景迁移词汇
今日探险剧情
需要家长注意的异常
```

## 33.3 学习报告

报告来源必须是：

```text
Assessment
+
Learner Profile
+
Learning History
```

而不是让 LLM 根据聊天记录自由总结。

示例结构：

```json
{
  "spontaneous_speaking_count": 12,
  "prompted_speaking_count": 7,
  "new_spontaneous_words": ["milk", "open"],
  "transferred_words": ["apple"],
  "current_focus": "主动表达食物需求",
  "scaffold_trend": "L3 -> L2",
  "parent_note": ""
}
```

## 33.4 家长输入

家长可以提供约束：

```text
今天最多 10 分钟
明天去动物园
最近喜欢恐龙
今天状态不好
暂时不练某主题
```

这些输入写入：

```text
Parent Constraints
```

由 Learning Director / Curriculum Agent 消费。

家长输入 **不能直接修改 mastery**。

例如：

```text
“我觉得他已经会 apple 了”
```

不能直接：

```text
apple = TRANSFERRED
```

只能作为一条辅助 evidence。

## 33.5 设备管理

App 负责：

- RX5 设备绑定；
- Wi-Fi 配置；
- 音量；
- 灯效开关；
- 摄像头权限；
- 麦克风权限；
- 固件版本；
- 在线状态；
- 设备解绑。

App 不承担实时音视频推理。

## 33.6 隐私与数据

必须提供：

```text
查看儿童数据
导出
删除
关闭长期记忆
关闭摄像头能力
关闭原始音频上传
```

删除操作走：

```text
POST /memory/erase
```

不得只删除 App 展示层数据。

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

---

# 35. 端到端一次完整交互

以孩子戴着设备指向冰箱为例：

```text
01 儿童触摸蛇首
↓
02 RX5 产生 wake 事件
↓
03 摄像头进入短时采集窗口
↓
04 端侧/视觉服务识别：
   pointing_target = fridge
↓
05 RX5 上传结构化 pointing event
↓
06 Backend 建立/更新 Session State
↓
07 Learner Model：
   milk = PROMPTED_OUTPUT
   water = SPONTANEOUS_OUTPUT
↓
08 Curriculum：
   primary_target = milk
↓
09 Scaffold：
   scaffold_level = L2
↓
10 Story：
   “冰箱精灵想喝东西”
↓
11 Director：
   要求二选一诱导 milk
↓
12 Interaction：
   "Milk or water?"
↓
13 TTS 返回 RX5
↓
14 RX5 播放
↓
15 儿童："Milk!"
↓
16 RX5 上传语音
↓
17 ASR + Assessment
↓
18 Assessment：
   target_reached = true
   spontaneous = false
   scaffold = L2
↓
19 Learner Model：
   milk evidence +1
↓
20 Story：
   冰箱精灵回应
↓
21 Interaction：
   "Milk! Yum! You found it!"
↓
22 RX5 播放 + 灯效
↓
23 Learning History 写入 store
↓
24 App 报告异步更新
↓
25 Web trace 可供开发查看
```

---

# 36. 端侧与 Agent 层的原则

必须明确：

```text
硬件端
负责 感知和执行

Agent 层
负责 教学决策

共享状态
负责 记住孩子

KG
负责 通用知识约束

App
负责 家长控制

Web
负责 开发/审核/运营
```

不得出现：

```text
摄像头模块决定学什么
App 自己维护一份学习画像
Web 调试台直接修改长期记忆
某个 Agent 直接控制摄像头
Interaction Agent 自己决定课程
```

所有跨层操作都必须经过明确接口。

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

---

# 38. Coding Agent 跨端修改纪律

修改任何代码前，先判断属于哪一层：

```text
Hardware
Web
App
Agent
Backend Service
Shared State
Trust Boundary
```

然后遵守：

1. Hardware 不承担长期教学决策。
2. Web 不复制 Agent 业务逻辑。
3. App 不直接修改 Learner mastery。
4. Agent 不直接访问设备驱动。
5. 设备控制统一经过 Device Gateway。
6. 摄像头开启必须由显式事件触发。
7. 浏览器 pointing 与 RX5 pointing 共用同一上层 Schema。
8. 所有儿童长期状态只在服务端 Shared State 有唯一真源。
9. App/Web 都只能通过 API 操作状态。
10. 儿童实时链路和外部互联网严格隔离。
11. Safety / Privacy / Erase 不能被 Agent 绕过。
12. 新增跨端字段时，先更新共享 contract，再改各端。

---

# 39. 工程记忆与可复用技能纪律

所有 Coding Agent 在 `A:\working\she` 工作时必须使用绝对路径，并把每个可独立审查的逻辑变更与工程经验留在仓库中。

## 39.1 修改前

1. 先标记所属层：Hardware、Web、App、Agent、Backend Service、Shared State、Trust Boundary 或 Repository。
2. 搜索 `A:\working\she\skills` 与 `A:\working\she\playbooks\incidents` 是否已有同类情境。
3. 命中 skill 时必须先完整读取并按其验证步骤执行；不得凭记忆复述旧步骤。
4. 命中 incident 但没有 skill 时，先复现 fingerprint，再采用已验证 resolution。
5. 跨端字段变化必须先改 `A:\working\she\shared\contracts`，不得先在某一个客户端私加字段。

## 39.2 修改中

1. 功能与修复遵循测试先行：先观察目标测试因缺少行为而失败，再写最小实现。
2. 新发现错误先做根因分析，不把猜测或无效尝试写成解决方案。
3. 不在日志、fixtures、playbooks 或测试快照中写入密钥、儿童原话、原始音频、原始图像或生产数据库内容。
4. 未经真实 RDK X5 验证的硬件步骤必须标记为待真机验收，不能声称成功。

## 39.3 修改后

1. 每个逻辑变更必须在 `A:\working\she\playbooks\changes` 留下一条记录，并与代码放在同一 commit。
2. 错误解决记录使用 `A:\working\she\playbooks\templates\incident.md`，必须包含复现与通过证据。
3. 只有可重复、步骤稳定、输入输出明确且有验证命令的流程才能升级为 skill。
4. 同一错误或情境再次出现时，优先运行已有 skill；skill 与现实不符时先记录新证据，再修订 skill。
5. 可由脚本或测试机械执行的规则优先自动化，不用冗长 skill 替代检查器。

## 39.4 首批项目 skills

```text
A:\working\she\skills\she-ios-soft-orbit\SKILL.md
```

跨端契约顺序与 incident recovery 已由本文件、Schema validator 和 playbook 模板约束。无 skill 压力测试表明通用 Agent 能正确处理这两类问题，因此不重复建立文档 skill；机械约束优先自动化。

RDK X5 首次连接流程当前保存在 release playbook。只有完成一次真实板端执行、修正和复验后，才允许建立 `she-rx5-preflight` skill。
