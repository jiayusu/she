# Shared State Layer

> 本文区分 Shared State 的目标模型与当前持久化事实。硬规则、组件归属与导航见仓库根
> [`AGENTS.md](../../AGENTS.md)，跨组件契约见 [`08-contracts.md](08-contracts.md)。
>
> 当前软件主链尚未执行本轮完整验证。“代码已存在”不等于生产隐私、真实设备或跨天学习效果
> 已验收。

---

# 11. Shared State Layer

所有儿童长期状态的唯一真源必须在服务端 Shared State。当前实现归属是
`backend/memory_store`；Agent、Web、App 和设备不得直接读写 SQLite/FAISS 文件。

## 11.0 当前实现总览

| 状态面 | 当前代码事实 | 仍未完成 |
|---|---|---|
| RPG session/world | `learning_turns.response.rpg` 持久保存 `milk_picnic.v1` 有限状态 | 多种子、跨故事选择、完整跨天叙事 |
| Delivery | 同一 turn 保存 `planned/issuing/completed/failed/expired` 元数据 | 真实设备链仍待验收 |
| Learning evidence | 高置信且上一提示已完成时写保守计数 | 完整 mastery graph 与自动确认 |
| Quest projection | Gateway 从 Memory 读取并返回脱敏 `rpg-quest-summary` | Web/iOS 尚未消费 |
| Erase | Memory 有 `POST /memory/erase` 与 session/child 级联 | Gateway/App 当前隐私操作仍是 demo-only |
| 原话处理（RPG） | RPG learning commit 不接收请求原话，response 顶层出现 `utterance` 会被拒绝 | 旧 episodic API 仍保存 `utterance`，系统级原话治理尚未收口 |

## 11.1 Session State

生命周期：一个 child/session 的连续任务。持久模式由以下接口拥有：

~~~text
GET  /memory/learning/state
POST /memory/learning/commit
POST /memory/learning/claim
POST /memory/learning/ack
~~~

`learning_turns` 每回合保存：

~~~text
session_id / child_id / device_id
turn_id / previous_turn_id
learning revision / request_hash
结构化 response
delivery command_id / device_session / status
~~~

这里有两个不同 revision：

- learning revision：Memory 中该 session 的回合顺序，用于 stale turn 与并发控制；
- `world_revision`：有限剧情事件版本，只在合法 world event 时增长。

Director 在配置 `SHE_MEMORY_URL` 时每轮先读权威上一回合，再提交新回合；其进程内 session 只
用于演示，不能替代 Shared State。

## 11.2 RPG World State

当前 `milk_picnic.v1` 的有限状态位于 `learning_turns.response.rpg`：

~~~json
{
  "seed_id": "milk_picnic",
  "seed_version": 1,
  "node_id": "collect_milk",
  "phase": "presenting",
  "world_revision": 1,
  "inventory": [],
  "completed_nodes": [],
  "confirmed_object": "fridge",
  "world_role": "饮品保管员",
  "feedback_id": "collect_milk_s2",
  "next_quest_id": "find_red_cup",
  "speech_act_evidence": {},
  "world_events": []
}
~~~

Memory 不接受任意 JSON Patch。提交时会再次核对 canonical node/inventory、连续 world revision、
上一 `action_id`/scaffold/提示 ID、delivery、`confirmed_object`、Speech Act evidence 与 event
引用。一个合法提交在同一事务中写入新节点、虚拟道具和事件，失败时不产生部分结果。

客户端只读 Gateway 的 `GET /v1/rpg/state`。该投影不返回 request hash、儿童原话、完整
assessment、Speech Act evidence 或内部 learning response，也没有对应的客户端 world 写接口。

## 11.3 Learner Profile

目标态 Learner Profile 保存 mastery graph、candidate/confirmed weakness、兴趣、响应行为和
偏好 scaffold。

当前持久实现更保守：`learning_evidence` 只记录目标、scaffold 与时间；`profile()` 汇总
`OBSERVED_ONCE/REPEATED`、最佳支持等级与复习时间，并明确
`mastery_promoted=false`。Director 的单轮 Learner Model 结果没有形成可跨种子消费的完整长期
mastery graph。

因此：

~~~text
quest_satisfied
≠ target_expression mastered
≠ learner mastery confirmed
~~~

例如二选一上下文中的 `Milk!` 可以推进剧情，但不能自动确认掌握 `I want milk.`。

## 11.4 Knowledge Graph

通用儿童英语知识的代码归属是：

~~~text
backend/knowledge_graph
~~~

它与个体儿童状态分离。Curriculum/Story 只能通过审核接口读取；任何 KG 修改必须可审核、可回滚，
且不能把孩子个人经历直接写成公共事实。当前 `milk_picnic.v1` 的节点、criterion 和文案引用来自
Director 的本地审核 StorySeed，不依赖实时开放互联网。

## 11.5 Story Memory

目标态 Story Memory 包含 StoryArc、角色、章节、高光与跨天续接。

当前实现只持久保存同一 session 的有限 `milk_picnic.v1` RPG 快照与事件引用。它能从 Memory
恢复当前节点和虚拟 inventory，但尚未实现开放 StoryArc、跨多个 seed 的剧情选择、自动高光或
家长可见的跨天叙事摘要。

## 11.6 Learning History 与原话边界

RPG 持久链只提交 Director 的结构化响应：

~~~text
TeachingAction
Assessment 摘要
Speech Act 的 act / slots / confidence / evidence ID
World events
delivery 元数据
~~~

**RPG learning path 不把儿童逐字原话写入 `learning_turns`。** `DurableLearning` 把原话用于当轮
解析后只提交 response；Memory 还会拒绝 response 顶层的 `utterance`。`rpg-decision` 只允许
结构化 Speech Act evidence，不含 transcript。

但这不是整个旧 Memory 服务已经实现“零原话存储”：兼容端点 `POST /memory/episodes` 与旧
episodic 表目前仍要求并保存 `utterance`。在旧接口完成迁移、保留策略与删除审计通过生产验收
前，只能声称“RPG learning path 不存原话”，不能声称全系统已经完成真实隐私治理。

## 11.7 Teaching Skill Library

目标态保存可复用、可审核的教学流程：

~~~text
触发条件
适用学习问题
教学动作
脚手架策略
成功标准
回退动作
~~~

当前已有 StorySeed、Interaction 审核模板和确定性 scaffold 规则，但尚未形成可版本化调度的完整
Teaching Skill Library。程序性记忆仍是存储机制，不是“程序记忆 Agent”。

---

# 12. 现有记忆系统归属

历史“五记忆”概念可映射到新职责，但所有新引用必须使用规范目录：

| 历史概念 | 新架构位置 | 当前状态 |
|---|---|---|
| 工作记忆 | Session State | 旧 API 保留；RPG 使用 learning turn |
| 情景记忆 | Story Memory + Learning History | 旧 episodic 保留；RPG 使用结构化 response |
| 语义记忆 | Knowledge Graph | `backend/knowledge_graph` |
| 显著性记忆 | Learner/Profile 或 Story salience | 旧显著性机制保留，未接入 RPG mastery |
| 程序性记忆 | Teaching Skill Library / 定时任务 | 程序性 API 保留，完整教学技能库未实现 |

现役服务路径与边界：

~~~text
backend/memory_store      个体状态、学习回合、记忆生命周期
backend/knowledge_graph   审核通用知识
~~~

主要 Memory API 包括：

~~~text
POST /memory/episodes
GET  /memory/recall
POST /memory/consolidate
GET/POST /memory/procedural
POST /memory/snapshot
POST /memory/rollback/{v}
POST /memory/erase
GET  /memory/audit

GET  /memory/learning/state
POST /memory/learning/commit
POST /memory/learning/claim
POST /memory/learning/ack
~~~

Agent 不允许直接操作 SQLite、FAISS 或 KG 数据文件。

---

# 18. 长期学习写入规则

必须区分：

~~~text
raw input
→ structured candidate evidence
→ repeated evidence
→ confirmed learner state
~~~

不得把以下任一情况直接写成 confirmed weakness 或 mastery：

- 单次错误或单次剧情成功；
- ASR 低置信；
- 未完成/失败/过期提示后的 speech；
- 外部服务错误；
- 题目歧义；
- 客户端自报成功；
- 没有专用 evaluator 时推测出的发音分。

当前 Memory 只实现保守 `OBSERVED_ONCE/REPEATED` evidence 汇总，不自动 promotion。目标态进入
confirmed 至少需要不同上下文的重复高置信 evidence、明确主动/迁移表现或经过授权的人工确认，
并保留审计和回滚依据。

删除仍必须沿服务端权威根执行。Memory 内部 `POST /memory/erase` 已存在；但 Web/iOS 经
Gateway 发起的隐私请求当前明确返回 `accepted_demo_only` 与 `store_mutated=false`，不能写成
真实导出/删除已经交付。

