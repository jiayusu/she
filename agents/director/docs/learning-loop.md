# 当前学习导向 Agentic Loop

本页描述当前代码。现实语言 RPG 的产品定义见
`docs/architecture/12-embodied-language-rpg.md`（仓库根相对路径）。

## 两种运行范围

`POST /agent/direct` 根据部署配置有两种状态范围：

- 配置 `SHE_MEMORY_URL`：使用 `DurableLearning`，上一回合、幂等、delivery 与 RPG 状态来自
  Shared State；这是 Compose 和 Gateway 主路径。
- 未配置 `SHE_MEMORY_URL`：使用 `LearningDirector` 的进程内 Map，15 分钟过期、最多 1000 个
  session；只适合组件演示，重启后丢失。

两种路径都不直接写 Learner Profile、KG 或设备。持久路径只通过 Memory HTTP API提交。

## 固定阶段

```text
input → assessment → curriculum → scaffold → story → decision
```

`LearningLoopHooks` 强制每阶段最多执行一次且不可越序。它是确定性调用顺序，不会递归创建
Agent、不加载外部 Hook，也不会访问开放互联网。

RPG 回合的关键触发条件：

| 输入/事实 | 触发结果 | 世界是否变化 |
|---|---|---|
| 首次确认 `fridge` | `collect_milk/presenting`，发审核提示 | 否，rev=1 |
| 节点仍在 `seeking_object` 时收到 speech/resume | 继续 `explore` | 否 |
| 上一提示未完成即收到 speech | `no_completed_prompt`，重新邀请 | 否 |
| ASR < 0.8 | `reinvite`，不增加失败次数 | 否 |
| 清楚但槽位错误 | 提高 scaffold；第二次后 pause | 否 |
| 已确认物体 + 提示完成 + `request_item(milk)` | 发 `milk_token`，进入 `find_red_cup` | rev 1→2 |
| 已确认桌/杯 + 提示完成 + `select_item(red cup)` | 发红杯并完成任务 | rev 2→3→4 |
| 情绪 valence < -0.45 | pause | 否 |
| paused 后显式 `resume` | 重新呈现当前节点提示 | 否 |

`presenting` 是持久 RPG 状态；设备 ACK 由 Memory 的 delivery 独立保存。Gateway 的只读摘要把
`presenting + completed` 投影成 `awaiting_speech`，把 `presenting + failed/expired` 投影成
`delivery_failed`。ACK 不产生 world event。

## Assessment 与剧情判定

`SpeechActResolver` 只回答当前剧情 criterion 是否满足；`AssessmentAgent` 只形成教学 evidence
候选。二者不得互相替代。

- “Milk!” 在上一提示明确二选一时可以推进剧情，但完整目标句评估为未达到。
- “I want water.” 是 request act，但 item 槽错误，不推进取奶任务。
- ASR 置信度只表示转写可信度；没有专用 evaluator 时
  `pronunciation_intelligibility=null`。
- 单次成功最多形成 candidate/observed evidence；Memory 不自动提升 mastery。

## 幂等与提交

持久路径为请求计算哈希，并使用 `child_id + session_id + turn_id` 读取状态：

1. 同一 turn、同一请求返回已提交响应；
2. 同一 turn、不同请求返回 idempotency conflict；
3. `previous_turn_id` 与最新回合不一致时拒绝；
4. world transition 在 Memory 事务内核对上一节点、revision、inventory、事件顺序、Speech Act
   evidence、上一 `action_id` 和 scaffold；
5. Interaction 只在提交成功后渲染，Gateway 再 claim、发送和等待 ACK。

## 隐私与审计

新 trace 只记录阶段、原因、失败次数和 ID。持久响应不保存 `utterance` 字段；请求正文不写入
RPG world event。旧 `/agent/dispatch` 仍有历史 JSONL/session 行为，因此只作为迁移入口，不能
承担新产品长期状态。

## 尚未完成

- 真实 ASR、发音 evaluator 与 response latency；
- 跨种子 Learner Model、复习计划和经过儿童研究验证的阈值；
- 生产身份/家庭授权；
- 自动把真实 pointing/ASR 设备事件编排为 RPG turn；
- 真实 RDK X5 与儿童研究验收。

## 验证入口

```sh
npm test --prefix agents/director
npm run typecheck --prefix agents/director
python -m pytest shared/contracts/tests -q
node scripts/rpg-smoke.mjs
```

这些命令是后续授权验证入口；文档本身不构成运行证据。
