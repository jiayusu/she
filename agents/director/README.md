# Learning Director（学习导演）

学习优先的唯一调度入口。它把权威上一回合、当前感知、情绪和学习摘要组织成固定六阶段决策，
每轮只返回一个 `teaching_action`。它不直接对儿童说话、不发设备命令，也不直接写 Learner
Profile、KG 或 SQLite。

- 架构定位：`AGENTS.md` §29 与
  [`docs/architecture/02-agents.md`](../../docs/architecture/02-agents.md) §4
- 现实语言 RPG：
  [`docs/architecture/12-embodied-language-rpg.md`](../../docs/architecture/12-embodied-language-rpg.md)
- 当前学习循环：[`docs/learning-loop.md`](docs/learning-loop.md)
- API / 注入 / 工具边界：[`docs/api.md`](docs/api.md) ·
  [`docs/context-injection.md`](docs/context-injection.md) ·
  [`docs/tool-boundary.md`](docs/tool-boundary.md)

## 当前主路径

```text
Gateway rpg-turn
  → DurableLearning 读取 Memory 权威上一回合与 delivery
  → input → assessment → curriculum → scaffold → story → decision
  → Memory 原子校验并提交 rpg-decision
  → Interaction 渲染审核话术
  → Gateway 发送设备命令并等待 ACK
```

当配置 `SHE_MEMORY_URL` 时，`POST /agent/direct` 使用持久路径：校验身份和输入、执行
`turn_id` 幂等、拒绝 stale turn，并从 `latest.response.rpg` 恢复故事。未配置时仅使用进程内
会话，适合组件演示，不是生产权威状态。

首个审核种子是 `content/story-seeds/milk_picnic.v1.json`：

```text
fridge → request_item(milk) → milk_token
       → table/cup → select_item(red cup) → red_cup_token → completed
```

Speech Act 只有在当前节点已确认现实物体、上一动作 delivery 为 `completed`、ASR ≥ 0.8 且
槽位命中审核 criterion 时才能提出世界 transition。任务成功与完整句学习证据分开：上下文中的
“Milk!” 可以推进剧情，但不等于掌握 “I want milk.”。

## 运行

```bash
npm ci
npm start
```

默认监听 `127.0.0.1:8790`，`PORT` 可覆盖。持久模式还需配置：

```text
SHE_MEMORY_URL=http://127.0.0.1:8789
```

端点：

```text
POST /agent/direct       新客户端/内部 Gateway 使用
POST /agent/dispatch     迁移期旧五大臣入口；不得承担新 RPG 长期状态
WS   /agent/session      旧调试订阅
GET  /healthz
GET/POST /admin/*        旧运维入口
```

RPG 输入示例（所有 ID 为合成值）：

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

对外产品调用优先走 Device Gateway 的 `POST /v1/rpg/direct`，由 Gateway 先校验共享输入契约。

## 实现分工

- `src/story-seed.ts`：审核资产的严格解析、有限图与引用校验。
- `src/speech-act.ts`：确定性 act/slot/context 判定，不修改状态。
- `src/embodied-rpg.ts`：物体门、失败/暂停和有限 transition proposal。
- `src/learning-director.ts`：固定阶段、唯一动作、任务与 Assessment 分离。
- `src/durable-learning.ts`：Shared State 读取、幂等、ACK 门槛和提交。
- `src/assessment.ts`：当前仅做完整目标词文本观察；无专用发音结果时明确返回 `null`。

## 共享契约

- `shared/contracts/v1/rpg-turn.schema.json`
- `shared/contracts/v1/rpg-decision.schema.json`
- `shared/contracts/v1/learning-loop.schema.json`
- `shared/contracts/v1/learning-event.schema.json`

TypeScript 类型仍是手写消费者；跨端字段必须先改 `shared/contracts/`。

## 测试命令

```bash
npm test
npm run typecheck
```

仓库级合成链由 `scripts/rpg-smoke.mjs` 驱动。真实 ASR、发音 evaluator、RDK X5 视觉与真实儿童
学习效果仍是待验证能力，不能由规则单测或模拟器结果替代。

## 已知边界

- 当前只允许一个审核 seed，不支持开放世界或运行时生成节点。
- Learner Model 尚未形成跨种子个体化课程；Memory 只保存保守 evidence，不自动确认 mastery。
- 生产家庭认证、多租户授权和速率限制不在本组件内完成。
- 旧 `dispatch`、minister 类型和包名仍为迁移遗留；新客户端不得依赖它们。
