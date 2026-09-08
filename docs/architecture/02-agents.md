# Agent 清单与各 Agent 职责

> 实时主链路 7 个 Agent 的输入/输出/做什么/不做什么，以及 Recast 与纠错原则。
>
> 硬规则、组件归属与导航见仓库根 [`AGENTS.md`](../../AGENTS.md)。
> 本文各节沿用 AGENTS.md 原有编号，以保持既有交叉引用有效。

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

现有基础设施（已迁移至规范目录）：

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
