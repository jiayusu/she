# Agent 清单与各 Agent 职责

> 本文同时描述职责模型与代码现状。硬规则、组件归属与导航见仓库根
> [`AGENTS.md](../../AGENTS.md)，现实语言 RPG 的状态机与验收边界见
> [`12-embodied-language-rpg.md](12-embodied-language-rpg.md)。
>
> 当前软件主链尚未执行本轮完整验证；本文的“已实现”表示代码已存在，不表示真实 ASR、设备或
> 儿童效果已经验收。

---

# 2. Agent 清单

“7 个 Agent”首先是 7 类可审计的教学职责，不等于 7 个独立服务，更不等于 7 个都可自由生成
文本的 LLM。确定性判断优先普通代码；儿童可见人格只有 Interaction Agent 的“小P”。

| 职责 | 核心问题 | 当前实现 | 是否直接对儿童说话 |
|---|---|---|---|
| Interaction Agent | “已决定的这一句话具体怎么说？” | `agents/interaction` 的审核渲染服务 | 是 |
| Learning Director | “这一轮系统到底应该做什么？” | `agents/director` 的 `POST /agent/direct` | 否 |
| Learner Model | “孩子当前有哪些可信学习证据？” | Director 内的单轮逻辑 + Memory 的保守 evidence profile；尚非完整长期模型 | 否 |
| Curriculum | “当前节点最值得练什么？” | RPG 从审核 StorySeed 取目标；通用路径有确定性 fallback | 否 |
| Scaffold | “给多少帮助才能安全开口？” | Director 内确定性 S0–S6 计算 | 否 |
| Story World | “语言如何改变有限世界？” | `milk_picnic.v1` StorySeed + 确定性状态转换 | 否 |
| Assessment | “这次回应提供了什么学习证据？” | Director 内基础文本观察；真实发音 evaluator 未实现 | 否 |

可选的 Parent Agent 是目标态异步摘要能力；当前没有独立 Parent Agent 服务。现有 Web/iOS 家长端
读取 Gateway 的演示 dashboard/report，不能据此认定异步摘要链已落地。

当前 RPG 主链是：

~~~text
RpgTurn
  → Learning Director
  → SpeechActResolver / Curriculum / Scaffold / Story / Assessment
  → 一个 TeachingAction + 一个受限 RpgDecision
  → Memory 原子提交
  → Interaction 把 TeachingAction 渲染为 text
  → Gateway 发设备命令并等待 ACK
~~~

其中 `SpeechActResolver` 是确定性解析器，不是第八个会自主行动的 Agent。

---

# 3. Interaction Agent

## 3.1 触发与职责

Interaction 是唯一儿童语言出口。只有 Director 已决定动作、且持久模式下该回合已经由 Memory
提交后，Gateway 才调用内部接口：

~~~text
POST /interaction/render
~~~

它负责：

- 把结构化 `TeachingAction` 转成小P的一句儿童可见文本；
- 校验动作、节点、角色、目标句、`prompt_id`、`feedback_id` 与 `story_action` 的有限白名单；
- 对 `ask`、`prompt`、`reinvite`、`advance_story`、`pause`、`explore` 使用审核文案；
- 对所有正常和降级出口执行最终本地安全过滤；
- 在同一 scaffold 等级重邀时复述真实上下文，例如 S2 的 “Milk or water?”。

RPG 渲染输入是 Director 的动作，而不是儿童原话。当前形状示例：

~~~json
{
  "action_id": "action-turn-001",
  "learning_goal": "request a familiar object",
  "target_expression": "I want milk.",
  "language_level": 1,
  "scaffold_level": 2,
  "teaching_action": "ask",
  "correction_policy": "recast",
  "story_action": "rpg:collect_milk_s2",
  "prompt_id": "collect_milk_s2",
  "feedback_id": "collect_milk_s2",
  "node_id": "collect_milk",
  "phase": "presenting",
  "world_role": "饮品保管员",
  "success_condition": {},
  "memory_policy": "no_write"
}
~~~

输出为有限对象：

~~~json
{
  "text": "Milk or water?"
}
~~~

## 3.2 不做什么

Interaction 不决定课程、Speech Act 是否成功、world revision、下一节点或长期 mastery，也不发送
设备命令、不访问开放互联网、不直接写 Memory/KG。

## 3.3 当前代码与边界

现役实现位于：

~~~text
agents/interaction/src/she_engine/learning_render.py
agents/interaction/src/she_engine/server.py
agents/interaction/assets/
~~~

同目录还保留通用 Engine、Recast、语言等级、LLM provider 和旧人格资产，供兼容路径使用。
`ahai` / `laonie` / `xiaop` 等仅是表现资产，不再代表后台路由。现实语言 RPG 主路径使用审核
内容 ID，不让模型临场发明节点或成功反馈。

---

# 4. Learning Director

## 4.1 触发与职责

Director 是实时教学层的唯一调度入口：

~~~text
POST /agent/direct
~~~

每个被 Gateway 接受的 `object_observed`、`speech` 或 `resume` 事件触发一次规划。它按固定阶段
组织输入、Assessment、Curriculum、Scaffold、Story 与最终决策，每轮只产生一个
`teaching_action`。

在配置 `SHE_MEMORY_URL` 的持久模式下，Director 还会：

1. 通过 Memory API 读取同一 child/session 的权威上一回合与 delivery；
2. 校验 `previous_turn_id`、`turn_id` 幂等和设备一致性；
3. 从 `latest.response.rpg` 恢复有限世界，而不是相信客户端传入 world state；
4. 在规划后通过 `POST /memory/learning/commit` 提交受限结果；
5. 不直接访问 SQLite，也不直接发设备命令。

未配置 Memory 时只使用进程内会话，适合组件演示，不是跨重启或多实例的权威状态。

## 4.2 当前 RPG 输入

产品调用应先经过 Gateway 的 `POST /v1/rpg/direct`。共享 `rpg-turn` 不接受客户端自报 world
patch、mastery 或任务成功：

~~~json
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
~~~

## 4.3 当前输出

`DirectResponse` 包含固定阶段 trace、唯一 `TeachingAction`、基础 Assessment 和一个通过
`rpg-decision` 约束的有限世界快照。关键字段：

~~~json
{
  "contract_version": "1.0",
  "session_id": "session-demo",
  "curriculum": {},
  "scaffold": {},
  "story": {},
  "teaching_action": {},
  "assessment": {},
  "rpg": {
    "seed_id": "milk_picnic",
    "seed_version": 1,
    "node_id": "collect_milk",
    "phase": "presenting",
    "world_revision": 1,
    "inventory": [],
    "completed_nodes": [],
    "confirmed_object": "fridge",
    "speech_act_evidence": {},
    "world_events": []
  }
}
~~~

## 4.4 状态触发规则

- 目标物体确认：`seeking_object/confirming_object → presenting`，记录受限
  `confirmed_object`，但不产生语言 evidence；
- 提示 delivery 未完成：后续 speech 不得推进任务；
- 提示完成 + 物体上下文有效 + ASR ≥ 0.8 + criterion 命中：提出 world event 与下一节点；
- ASR 低置信：`reinvite`，不记为清楚失败；
- 清楚但槽位错误：不改 world revision，提高帮助；达到失败上限后 `pause/S6`；
- 情绪风险：优先 `pause`；只有显式 `resume` 才重新呈现；
- transition 成功：下一节点从 `seeking_object` 开始，要求孩子在现实空间寻找新物体。

Director 只提出受限决定；Memory 仍会再次验证 revision、上一动作、提示引用、delivery、物体
上下文、evidence 与事件。两层一致后才算世界改变。

## 4.5 兼容与未完成项

`POST /agent/dispatch` 仍是旧 minister 兼容入口，新客户端不得依赖。真实 ASR、发音 evaluator、
开放多种子课程选择、生产认证和真实设备事件编排均未完成。

---

# 5. Learner Model

## 5.1 目标职责

目标能力状态不是简单的 known/unknown，而是：

~~~text
UNSEEN → HEARD → COMPREHENDED → IMITATED
       → PROMPTED_OUTPUT → SPONTANEOUS_OUTPUT → TRANSFERRED
~~~

只有 Assessment evidence 可推动状态；单次错误不能确认“不会”，单次剧情成功也不能确认 mastery。

## 5.2 当前实现

`agents/director/src/learner-model.ts` 能在单次规划结果中形成 candidate mastery/evidence 状态。
持久路径的 `backend/memory_store/memstore/learning.py` 只保存高置信、已完成提示对应的保守
evidence 计数，并明确返回 `mastery_promoted=false`。当前没有跨故事种子、跨场景的完整个体化
Learner Profile，也不会因为 `Milk!` 推进剧情就自动认定掌握 `I want milk.`。

因此，“完整 Learner Model Agent”仍是目标设计；当前事实应表述为“有限 evidence profile 已有，
长期 mastery promotion 未实现”。

---

# 6. Curriculum

## 6.1 目标职责

Curriculum 负责从 Learner Profile、审核 KG、复习到期项和当前场景中选择单一 primary target，
实现 i+1、间隔重复与跨场景迁移。它不能直接写 KG。

通用知识的唯一代码归属是 `backend/knowledge_graph`；新增知识必须经过候选、规则校验、冲突
检测、人工审核和可回滚热更新。

## 6.2 当前实现

在 `milk_picnic.v1` 中，目标表达与 criterion 来自本地审核 StorySeed，不是运行时 KG 检索或
LLM 生成。通用 Director 路径仅有少量确定性 fallback 表达。当前尚未实现“根据长期 mastery
自动选择多个故事种子”的完整课程系统。

---

# 7. Scaffold

Scaffold Level 表示“输出帮助多少”，与 `language_level` 严格分开：

~~~text
S0 自由输出
S1 情景暗示
S2 二选一
S3 句首提示
S4 填空
S5 完整示范
S6 只输入，不要求输出
~~~

当前 `agents/director/src/scaffold.ts` 使用确定性计算：基准 S2，清楚失败提高帮助，最近成功降低
帮助，情绪风险直接进入 S6。RPG 再把结果映射到 StorySeed 审核的
`<node>_s<scaffold_level>` 内容 ID；Interaction 只能渲染该有限集合。

Scaffold 不修改课程语言等级、不判断 world transition，也不能把低置信 ASR 记成失败。当前策略
只基于很短的近期上下文，尚不是成熟的跨会话个体化策略。

---

# 8. Story World

Story World 的职责是把语言变成有后果的剧情动作：

~~~text
Object → Role → Speech → Action → World State → Next Quest
~~~

当前只实现一个审核种子：

~~~text
collect_milk
  -- request_item(item=milk) --> find_red_cup
  -- select_item(item=cup,color=red) --> picnic_ready
~~~

代码与资产归属：

~~~text
agents/director/content/story-seeds/milk_picnic.v1.json
agents/director/src/story-seed.ts
agents/director/src/embodied-rpg.ts
agents/director/src/speech-act.ts
~~~

Story World 只能引用种子声明的节点、角色、提示、道具和事件；`state_patch` 在 RPG 主路径为空，
世界变化只允许出现在 `rpg.world_events` 并由 Memory 校验。它不自行判断长期学习成功，不直接
写数据库，也不远程控制真实冰箱或杯子。

开放世界、运行时生成节点、多种子编排与跨天剧情选择尚未实现。

---

# 9. Assessment

Assessment 回答“这次回应提供了什么学习证据”，SpeechActResolver 回答“当前剧情 criterion 是否
满足”，两者不得合并。

当前 `agents/director/src/assessment.ts` 只做基础文本观察：完整目标表达的全部目标词出现时，
才产生完整表达 evidence。因而上下文支持的 `Milk!` 可以推进任务，但不会被当作掌握
`I want milk.`。当前没有专用发音 evaluator，所以：

~~~json
{
  "pronunciation_intelligibility": null
}
~~~

ASR 置信度只能说明转写可信度，不能冒充发音分。响应延迟、真实语义评估、跨场景迁移与真实
发音评估仍待实现。

Assessment 不直接面向儿童输出分数或“你错了”，也不直接写 KG/world state。

---

# 10. Parent Agent（异步目标）

目标态 Parent Agent 可基于 Assessment、Learner Profile 和 Learning History 生成每日/每周摘要，
接收家长约束，但不进入儿童实时状态机，也不能让一次主观判断覆盖 mastery。

当前没有该独立 Agent。Gateway 的 dashboard/report 默认由 `DemoRepository` 提供示例数据；
Web/iOS 展示的是明确标记的演示家庭。生产学习摘要、家长身份、多家庭隔离和真实隐私处理仍未
完成。

---

# 19. Recast 与纠错原则

儿童交互默认使用吸收式 Recast：

~~~text
Child: I like apple.
小P: I like apples too!
~~~

不得默认用分数、否定或长篇语法说明打断孩子。显式纠错只能由 Director 在明确教学场景下选择。
通用 Recast 能力位于 `agents/interaction` 的兼容 Engine；当前 `milk_picnic.v1` 主路径主要使用
审核提示、重邀和成功反馈，不允许 Interaction 自行发明纠错内容。

