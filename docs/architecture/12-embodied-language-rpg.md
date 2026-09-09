# 现实语言 RPG（Embodied Language RPG）

> 状态：MVP 软件主链已写入代码，尚未执行本轮集成验证。本文定义产品主循环、Agent 职责、
> 剧情状态机、故事资产和验收边界。
> 当前代码实现程度另见 [`../CODE_IMPLEMENTATION_AUDIT.md`](../CODE_IMPLEMENTATION_AUDIT.md)。

当前落地范围：

| 能力 | 代码状态 | 验证状态 |
|---|---|---|
| `milk_picnic.v1` 审核 seed 与严格 loader | 已实现 | seed/初版契约曾单独验证；后续集成未重跑 |
| Speech Act、物体门、唯一 TeachingAction、持久会话恢复 | 已实现 | 本轮未运行 |
| Memory 原子 world transition / 交付与审核提示门 / 幂等 / erase 级联 | 已实现 | 本轮未运行 |
| Interaction 审核提示/结果白名单与最终 Safety | 已实现 | 最终 Safety 修复曾验证；RPG 契约对齐本轮未运行 |
| Gateway 输入/输出契约与脱敏 quest summary | 已实现 | 本轮未运行 |
| 合成完整剧情脚本 | 已编写 `scripts/rpg-smoke.mjs` | 未运行 |
| Web/iOS 任务卡、自动设备事件编排、真实 ASR/真机 | 未实现或待验证 | 不得宣称完成 |

## 1. 产品定义

SHE 的核心不是围绕识别到的物体闲聊，而是让英语成为改变一个安全虚拟世界的动作：

```text
Object → Role → Speech → Action → World State → Next Quest
```

- **Object**：经感知链路确认的现实物体或场景线索。
- **Role**：审核故事资产赋予物体的剧情身份；它不是新的儿童可见 Agent。
- **Speech**：当前任务要求的有限 Speech Act，例如请求、选择、描述。
- **Action**：Speech Act 满足任务条件后产生的剧情动作。
- **World State**：服务端权威、带 revision 的有限虚拟状态。
- **Next Quest**：由合法节点转换确定的下一任务，不由模型即兴改写。

儿童始终只听见“小P”一个稳定角色。小P 可以转述“冰箱管理员说……”，但系统不在多个
人格之间切换。现实物体不会被远程操控；`milk_token`、`red_cup_token` 等均为虚拟剧情道具。

### 1.1 要验证的产品假设

当孩子为了推动剧情而说出有意义的英语动作，并立刻观察到世界反馈时，英语会从“回答系统”
转变为“达成目的的工具”。MVP 必须证明：

1. 现实物体能自然触发一个审核任务；
2. 只在对应提示确实播放完成后才评估回答；
3. 正确 Speech Act 会原子地产生世界事件并推进节点；
4. 错误对象、低置信识别、重复请求或播放失败不会误推进；
5. 下一任务会把孩子带到另一个现实物体，而不是继续围绕同一物体闲聊。

### 1.2 MVP 范围

第一版只发布一个审核故事种子 `milk_picnic.v1`：

```text
collect_milk → find_red_cup → picnic_ready
```

MVP 包含确定性故事图、Speech Act 解析、Director 单动作决策、Shared State 持久化、
Interaction 审核模板、Gateway 执行与合成设备端到端测试。

MVP 不包含：开放世界生成、任意 LLM 生成任务、真实冰箱控制、真实物品移动、开放互联网、
生产身份认证、真实 ASR/发音模型、真实 RDK X5 视觉验收以及自动确认 mastery。

## 2. 权威状态与信任边界

| 数据/动作 | 唯一权威 | 其他组件只能做什么 |
|---|---|---|
| 感知事件 | Device Gateway 验证后的事件流 | Agent 读取确认结果，不能开启设备驱动 |
| 当前 quest/world state | Shared State | Director 提交受限 transition proposal；客户端只读 |
| 教学动作 | Learning Director | 其他教学组件提交 proposal；每轮只能选一个 |
| 儿童话术 | Interaction Agent + 最终安全出口 | Story 只能提供结构化内容引用 |
| 设备命令 | Device Gateway | Director 只能给命令意图，不能生成传输层命令 |
| 学习证据 | Assessment 候选 + Shared State 规则 | 单次结果不得直接确认 mastery |
| 故事内容 | 版本化审核资产 | 运行时不得新增节点、事件类型或自由 JSON patch |

必须维持以下边界：

- 儿童实时链路不访问开放互联网；
- 摄像头只由显式事件触发，且成功或失败都关闭；
- 原始音频、原始图像、儿童逐字话语不进入故事状态、世界事件或审计摘要；
- Safety、Privacy、Erase 和 evaluator 约束不可由 Agent 修改或绕过；
- 世界推进不代表长期语言掌握，quest success 与 mastery evidence 分开判断。

## 3. 有限任务状态机

任务状态和设备执行状态必须分开。只有已完成的提示才能引出可评估回答。

```text
seeking_object
  ├─ 目标物体确认 → presenting
  └─ 识别不确定 → confirming_object

confirming_object
  ├─ 确认目标物体 → presenting
  ├─ 明确不是目标 → seeking_object
  └─ 超时/情绪风险 → paused

presenting
  ├─ delivery.completed → awaiting_speech
  └─ delivery.failed/expired → delivery_failed

awaiting_speech
  ├─ Speech Act 满足 criterion → resolving
  ├─ 清楚但不满足 → presenting（提高 scaffold）
  ├─ ASR 不确定 → presenting（澄清，不记失败）
  └─ 情绪风险/两次清楚失败 → paused

resolving
  └─ 原子提交 evidence + world event + next node
       → seeking_object / presenting / completed

paused
  └─ 显式、自愿的 resume 事件 → presenting
```

`resolving` 是服务端事务过程，不是客户端可写状态。重放同一 `turn_id` 必须返回相同结果，
不得重复发奖或重复推进 revision。

### 3.1 事件顺序硬规则

1. `object_observed` 只更新场景上下文，不会被当作一次语言失败。
2. `speech` 只有在上一 `action_id` 的 delivery 为 `completed` 时可被评估。
3. `speech` 必须携带 `detected_object=null`；物体上下文只来自此前已接受的感知回合。
4. 当前节点尚未确认 `required_objects` 时，`speech` 与 `resume` 都不能跳过现实探索，只能继续寻找。
5. `quest_satisfied` 只由当前节点的 criterion 判定。
6. transition 的 `base_revision` 必须等于 Shared State 当前 revision。
7. Memory 只接受由上一条已完成交付、节点匹配的审核提示所引出的 transition。
8. world event、next node 和新 revision 必须在同一提交中产生。
9. Interaction 成功反馈只能在提交成功后播放；提交失败不能先宣布获得道具。
10. `completed`、`paused`、`delivery_failed` 不会由客户端或 LLM 自述触发。

## 4. 故事资产模型

故事种子是审核、版本化、可回滚的本地内容，不是 Prompt 中的自由文本。

### 4.1 StorySeed

```json
{
  "seed_id": "milk_picnic",
  "version": 1,
  "language_levels": [0, 1, 2],
  "start_node_id": "collect_milk",
  "completion_node_id": "picnic_ready",
  "nodes": [],
  "allowed_world_events": ["virtual_item_granted", "quest_completed"]
}
```

必需字段：

- 稳定的 `seed_id` 与整数版本；
- 有限 node 集合及唯一入口、结束节点；
- 每个 node 的现实物体条件、角色、Speech Act criterion、审核文案引用和合法后继；
- 允许的虚拟事件与道具白名单；
- 适用 `language_level`，与 `scaffold_level` 分离。

### 4.2 StoryNode

| 字段 | 语义 |
|---|---|
| `node_id` | 种子内稳定 ID |
| `required_objects` | 进入任务所需的一组允许物体/场景 |
| `world_role` | 物体的故事身份，仅供小P转述 |
| `motivation` | 孩子为何需要说这句话 |
| `learning_goal` | 教学目标 |
| `target_expression` | 完整目标表达，不等于唯一可接受回答 |
| `criterion` | Speech Act、必需槽位、审核表达变体和上下文规则 |
| `prompts` | 各 scaffold 等级的审核模板引用 |
| `success_event` | 满足 criterion 后允许的虚拟世界事件 |
| `next_node_id` | 唯一合法后继 |
| `failure_action` | 澄清、提高帮助或暂停，不改世界状态 |

### 4.3 WorldState

```json
{
  "seed_id": "milk_picnic",
  "seed_version": 1,
  "node_id": "collect_milk",
  "phase": "presenting",
  "world_revision": 1,
  "inventory": [],
  "completed_nodes": [],
  "confirmed_object": "fridge"
}
```

World State 是有限字段集合，不接受任意 JSON Patch。`inventory`、节点和事件必须引用当前
StorySeed 已声明的 ID。`confirmed_object` 是服务端从已接受感知中派生的当前节点上下文，进入下一
节点时必须清空；客户端不能用它自报“已经找到”。语言失败次数属于 Director 的短期学习循环，
不是客户端可写的世界字段。Durable 模式从 Shared State 恢复的状态不受进程内 15 分钟缓存 TTL
影响；TTL 只约束未配置持久服务的本地演示会话。

## 5. 首个故事种子：milk_picnic.v1

### 5.1 节点表

| 节点 | 现实线索 | 物体角色 | Speech Act | 成功事件 | 下一节点 |
|---|---|---|---|---|---|
| `collect_milk` | `fridge` | 饮品保管员 | `request_item(item=milk)` | `virtual_item_granted(milk_token)` | `find_red_cup` |
| `find_red_cup` | `table` 或确认的杯子场景 | 杯子管理员 | `select_item(item=cup,color=red)` | `virtual_item_granted(red_cup_token)` | `picnic_ready` |
| `picnic_ready` | 无 | 野餐向导 | 无 | `quest_completed(milk_picnic)` | 结束 |

### 5.2 审核表达变体

`request_item(item=milk)`：

- `milk`：仅当上一提示明确是 milk/water 二选一；
- `milk please`；
- `I want milk`；
- `I would like milk`。

`select_item(item=cup,color=red)`：

- `red`：仅当上一提示明确是 red/blue 二选一；
- `red cup`；
- `the red cup`；
- `I choose the red cup`。

“I want water.” 不能完成取奶任务；任意句子仅含 `red` 也不能在没有二选一上下文时完成找杯任务。

## 6. Speech Act 与学习评估分离

`SpeechActResolver` 是确定性普通代码，不是自由生成 Agent。它输出：

```json
{
  "evidence_id": "se_t2",
  "source_turn_id": "t2",
  "eliciting_action_id": "a_t1",
  "act": "request_item",
  "slots": {"item": "milk"},
  "confidence": 0.97,
  "context_supported": true,
  "scaffold_level_used": 2,
  "quest_satisfied": true,
  "criterion_id": "request_milk.v1"
}
```

它回答“剧情条件是否满足”。Assessment Agent 另行回答“这次语言表现提供何种教学证据”。
因此：

- `Milk!` 可以在二选一上下文中推进任务，但不证明掌握完整句型 `I want milk.`；
- `I want water.` 是合法 request act，但槽位不匹配，不能推进取奶节点；
- 单词、短语、完整句分别映射到不同 evidence 强度；
- 低置信 ASR 不推进、不记失败、不写长期弱点；
- 发音可理解度必须来自专用 evaluator；ASR 置信度不能冒充发音评分。

## 7. Agent 设计与触发条件

七个教学职责不等于七个独立 LLM。确定性逻辑优先普通代码，只有 Interaction 在需要时使用
受控生成；MVP 默认使用审核模板。

| 组件 | 触发时机 | 输入 | 输出 | 不做什么 | 失败降级 |
|---|---|---|---|---|---|
| Learning Director | 每个已接受输入事件 | 权威快照、感知摘要、上一执行事实 | 唯一 TeachingAction/transition proposal | 不写数据库、不发设备命令 | pause 或审核模板动作 |
| Learner Model | 规划前读取；证据提交后异步归并 | 已审计 evidence/profile | 能力摘要、推荐帮助 | 不因单次结果确认 mastery | 保持原状态 |
| Curriculum | 新节点进入、复习到期 | StoryNode、能力摘要、审核 KG | 单一学习目标 | 不自造故事图、不写 KG | 使用节点默认目标 |
| Scaffold | 提示前、清楚失败后、成功后 | 近期已执行尝试、情绪 | S0–S6 帮助 | 不改语言等级 | 提高帮助或 S6 |
| Story World | 物体确认、transition 提交、节点进入 | seed、world state、目标 | 角色/反馈/受限事件 proposal | 不自行判断学习成功 | 冻结 world state |
| SpeechActResolver | 上一提示完成且收到清楚语音 | criterion、ASR、上下文 | act/slots/quest_satisfied | 不写 mastery/world state | unmatched/uncertain |
| Assessment | 收到有效语言回应 | 回应、目标、scaffold、evaluator | evidence 候选 | 不面向儿童、不改世界 | no_write |
| Interaction | TeachingAction 已确定或 transition 已提交 | 审核内容引用、难度、帮助级别 | 小P的一句话 | 不选课程、不控制设备 | 最终安全模板 |

Parent Agent 是异步摘要能力，不进入实时任务状态机。

## 8. 每轮执行顺序

```text
1. Gateway 接受并校验事件、身份、版本和顺序
2. Director 读取 Shared State 权威快照
3. 检查上一 action 是否真正 delivery.completed
4. SpeechActResolver（仅有效 speech 回合）
5. Assessment 形成独立学习 evidence 候选
6. Curriculum / Scaffold / Story 各自产生有限 proposal
7. Director 选择唯一 TeachingAction 与受限 transition proposal
8. Shared State 原子提交 turn、world event、revision 和 evidence
9. Interaction 渲染提交后的动作并执行最终安全过滤
10. Gateway 生成 canonical device command，发送一次并等待 ACK
```

低置信、情绪风险和安全拒绝优先于课程与剧情推进。

## 9. 共享契约方向

实施时必须先修改 `shared/contracts/`。MVP 新增三个明确 schema：

- `rpg-turn`：客户端/设备只提交身份、输入种类和感知引用，不可提交 world patch/mastery；
- `rpg-decision`：Director 返回受限 RPG 状态、Speech Act evidence、world event 和唯一动作。
- `rpg-quest-summary`：Gateway 返回脱敏只读投影，不暴露儿童原话、Speech Act evidence 或内部响应。

关键类型：

```text
input_kind = object_observed | speech | resume
phase = seeking_object | confirming_object | presenting | awaiting_speech |
        resolving | paused | delivery_failed | completed
speech_act = request_item | select_item | none
world_event.kind = virtual_item_granted | quest_completed
```

`object_observed` 才能携带审核物体枚举；`speech` 与 `resume` 的 `detected_object` 必须为 `null`，
防止把上一帧或客户端自报物体混入语言证据。

新增字段优先保持旧 learning 客户端可后兼容；破坏性设备事件变更另开 `v2/`，不能原地破坏
`device-event` / `device-command` v1。

## 10. 完整示例 Trace

| 步骤 | 输入或执行事实 | 状态变化 | 小P输出 |
|---|---|---|---|
| 1 | 显式唤醒触发短时视觉；确认 `fridge` | `collect_milk/presenting`, rev=1 | “Milk or water?” |
| 2 | 提示 action 的 TTS ACK=`completed` | `awaiting_speech` | 等待孩子 |
| 3 | “Milk!”, ASR=.97 | `request_item(milk)`；写 se1/we1；获得 `milk_token`；转 `find_red_cup/seeking_object`, rev=2 | “Milk is ready. Find a cup!” |
| 4 | 后续显式观察确认 `table` 或杯子场景 | `find_red_cup/presenting`；前一步成功使帮助由 S2 降至 S1 | “Which cup does our picnic need?” |
| 5 | 提示已完成；“Blue cup.” | act 正确但 color 不匹配；失败=1；world rev 不变 | “Red…” |
| 6 | 新提示已完成；“Red cup!” | 写 se2/we2；奖励事件 `2→3`，完成事件 `3→4`；转 `picnic_ready`, rev=4 | “Red cup! Our picnic is ready!” |
| 7 | 最终提示完成 | quest=`completed` | 等待新的显式探索 |

第 3、6 步都是“有提示成功”，不能在家长报告中写成主动表达或迁移掌握。

## 11. 验收条件

### 11.1 必须通过

- 同一 `turn_id` 并发/重放只产生一次 transition 和奖励；
- 未完成、失败或过期的提示不会被评估；
- `Milk!` 在二选一上下文推进取奶；`I want water.` 不推进；
- `Red cup!` 只在找红杯节点推进；
- 世界 revision 单调递增，非法节点/道具/任意 patch 被拒绝；
- 已完成的 quest step 会降低后续节点 scaffold（最多两级），清楚失败提高帮助，两次失败后暂停；
- transition 提交失败时不播放成功反馈；
- 所有动态与 fallback 文本都经过最终安全过滤；
- erase 后缓存、数据库、manifest 和审计中不保留儿童原话；
- 合成设备 E2E 覆盖 Object→Role→Speech→Action→World State→Next Quest。

### 11.2 只能标记为待验证

- 真实 ASR、发音 evaluator 的准确率；
- 真实 RDK X5 摄像头/指向识别；
- 真实儿童学习效果、主动开口率和跨场景迁移；
- 生产身份认证、加密、监控与多家庭隔离。

## 12. 演进原则

新种子必须先通过静态校验、内容审核、状态图可达性检查与回放测试。只有数据证明有限规则无法
覆盖的部分才考虑引入 LLM proposal；即使引入，节点、事件、道具、状态转换和最终输出仍由
确定性边界约束。产品扩展顺序是“多种子 → 更多 Speech Act → 更强课程选择 → 个体化生成”，
而不是先做开放世界生成。
