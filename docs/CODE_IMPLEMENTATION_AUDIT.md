# SHE 代码实现审计

> 审计基线：2026-09-08，分支 `chore/repo-reorg-for-ai-maintenance`，起始提交 `22fb0d3`。
> 范围：仓库中的 Agent、共享状态、KG、指向识别、数据情报、Gateway、Web、iOS、RX5、
> 共享契约、测试与部署脚本。结论来自代码、自动化测试和合成探针，不代表生产或真机验收。

## 0. 审计后变更说明（2026-09-09）

本文件主体保留 2026-09-08 的**基线判断**，用于解释为什么启动整改；不要把后文“基线未实现”
误读成当前工作区仍完全没有 RPG 代码。审计后已发生：

| 整改 | 当前工作区 | 证据状态 |
|---|---|---|
| Interaction 动态 fallback 最终 Safety | 已修复 | 修复时 110 项 Interaction 测试通过 |
| Memory erase 清理 cache/snapshot，manifest/audit 去原话 | 已修复 | 修复时 73 项 Memory 测试通过 |
| Gateway `RequestInit.body` 类型问题 | 已修复 | 修复时 Gateway/Web 测试与类型检查通过 |
| RPG turn/decision、StorySeed 初版 | 已加入 | 初版契约与 seed 曾单独验证 |
| Speech Act、物体门、Director 决策、Memory world transition | 已加入 | 最新 runtime 改动未运行测试 |
| Interaction RPG 审核文案、Gateway RPG 边界/只读摘要 | 已加入 | 未运行测试 |
| `scripts/rpg-smoke.mjs` 完整合成剧情 | 已编写 | 未运行 |

以上“已加入/已修复”表示文件中存在实现，不等于本轮集成通过。用户要求继续编辑且不运行测试，
因此所有最新 RPG runtime、契约扩展与 Compose 链都必须保持“待验证”。原审计中的 Gateway
capture 授权、KG/Memory/Intel 生产认证、真实 ASR/发音、客户端产品面和真机缺口仍未关闭。

## 1. 结论

**没有实现所有设计功能。** 当前仓库更准确的定位是：

> 一条可运行的单家庭 Mock 纵向切片，加上一个有限规则教学循环和若干较完整的后台原型。

它已经具备可复用的工程骨架：共享 JSON Schema、设备 WebSocket、合成 RX5 runtime、Director
唯一教学动作、持久回合重放/ACK 门槛、Interaction 审核模板、Memory/KG/Intel/Pointing 的独立
实现与大量组件测试。但产品设计中的完整七职责学习闭环、真实语义/发音评估、动态课程、持久
故事世界、浏览器调试/运营台、真实隐私删除、生产认证、真实 RDK X5 与真实儿童效果均未完成。

### 1.1 就绪度判断

| 使用场景 | 判断 | 原因 |
|---|---|---|
| 本地架构演示 | 部分可用 | 组件测试大多通过，Docker/合成设备有骨架；根验证基线仍有类型错误 |
| “物体 → 一轮英语提示”演示 | 可用但有限 | 只支持四个硬编码目标和有限模板 |
| 连续学习闭环 | 部分实现 | 有回合、ACK、候选 evidence；Learner Model、真实复习/i+1、成功撤帮助不完整 |
| 现实语言 RPG | 基线未实现 | Story 只有字符串 patch，没有 quest/node/world revision/Speech Act 状态机 |
| 儿童生产环境 | 不可用 | Safety、Privacy、Erase、认证和审核边界存在可复现绕过 |
| 真实硬件产品 | 未验证 | RX5 adapter 仍返回 `unverified`；无真实板端 SSH 验收 |

## 2. 判定口径

- **已实现**：存在运行代码，有针对性测试或合成执行证据，主要边界与文档一致。
- **部分实现**：主路径存在，但依赖 Mock、硬编码、缺少关键边界或只覆盖部分场景。
- **原型/Mock**：适合本地演示，不能作为生产能力声明。
- **未实现**：只有文档、类型、空壳或没有接入主路径。
- **待验证**：代码存在，但当前环境无法证明真实外部服务、iOS 或硬件行为。

“类名叫 Agent”不等于独立 LLM Agent，也不等于功能完成。本项目把确定性教学职责写成普通类是
合理方向；审计关注的是职责输入、输出、状态、边界和闭环是否真实成立。

## 3. 代码地图

| 组件 | 磁盘中的真实职责 | 当前判断 |
|---|---|---|
| `agents/director` | 新学习决策入口、旧五大臣兼容链、会话/审计/本地存储 | 核心循环部分实现，双架构并存 |
| `agents/interaction` | 新审核模板 HTTP renderer；旧完整 LLM 剧情库 | 新路径有限；旧路径存在人格和安全问题 |
| `backend/memory_store` | SQLite/FAISS 记忆、学习回合、ACK、快照、删除 | 功能多，但删除/隐私不合格 |
| `backend/knowledge_graph` | 构建、清洗、检索、热更、快照/回滚 | 工程原型；无自动测试和强制审核/认证 |
| `backend/pointing` | 浏览器摄像头 + 手势/选物实验室 | 浏览器原型，未消费共享契约 |
| `backend/intel` | 离线采集、结构化、审核候选、KG bridge | 离线链较完整；认证和全局审核边界不足 |
| `backend/device_gateway` | 家长 HTTP、设备 WS、Digital Twin、学习执行 | 合成链可用；命令/隐私/认证仍是演示级 |
| `backend/digital_twin` | 文档 | 正确地没有重复实现 |
| `clients/web` | 家长 Dashboard/报告/设置 | 不是目标 Web 调试台/运营台 |
| `clients/ios` | SwiftUI 家长端原型 | 数据层和 UI 有实现，生产端点/真实隐私未接入 |
| `clients/hardware-rx5` | 合成 runtime、契约、ACK、能力降级 | 模拟器已验证，真实视觉/板端未验证 |
| `shared/contracts/v1` | 设备、家长、学习部分 JSON Schema | 基础可用；完整 Director/RPG/跨语言一致性不足 |

## 4. Agent 设计专项审计

### 4.1 实际拓扑

新主路径不是七个自治模型互相对话，而是 `LearningDirector` 在单进程中按固定顺序调用确定性
组件：Assessment → Curriculum → Scaffold → Story → Decision。Interaction 是单独 Python
服务，Shared State 的 durable 分支负责回放与提交。这种结构更适合儿童实时链路，但当前每个
职责的能力并未全部实现。

### 4.2 七个教学职责

| 职责 | 实现状态 | 代码证据与缺口 |
|---|---|---|
| Learning Director | 部分实现 | `learning-director.ts` 能保证唯一 TeachingAction、情绪优先、两次失败暂停、有限 session；但状态只围绕上一动作，不是完整 quest/world controller |
| Interaction Agent | 部分实现 | `server.py` + `learning_render.py` 提供审核模板与固定小P出口；不使用 `language_level`、Story 成功反馈、Assessment 或完整 Recast；多种动作会渲染为同一句 |
| Learner Model Agent | 未接入 | `learner-model.ts` 有纯类定义，但主循环没有实例化或调用；主响应的 `evidence_status` 固定为 `OBSERVED_ONCE` |
| Curriculum Agent | 原型 | `curriculum.ts` 只有 milk/water/open/apple 四表达；不调用 KG，`i_plus_1_target` 等于当前目标，review target 没有真正成为主目标 |
| Scaffold Agent | 部分实现 | 有 S0–S6 公式；Director 只重建失败历史，成功分支不可达，连续成功不会撤帮助 |
| Story World Agent | 原型 | `story.ts` 只返回 `world_waits_for_*`、固定小P和任意对象 patch；没有 seed、node、合法 transition、revision 或持久世界事件 |
| Assessment Agent | 原型且判定有误 | `assessment.ts` 用目标词重合率代替语义；ASR confidence 冒充发音可理解度，latency 恒为 0 |
| Parent Agent（可选异步） | 未实现 | Web/iOS 展示固定报告；没有异步 Agent 汇总/建议链 |

### 4.3 可复现的 Assessment 错误

目标为 `I want milk.` 时，基线代码会得到：

| 回答 | `target_reached` | 实际含义 |
|---|---:|---|
| `I want water.` | `true` | 错误对象被当作成功，并产生 candidate memory policy |
| `Milk!` | `false` | 合理的二选一短答被当作失败 |

根因是 `agents/director/src/assessment.ts` 以目标表达中命中的词数比例 `>= 0.5` 判断成功，
没有校验 Speech Act 的必需槽位。它既会产生错误剧情推进，也会污染候选学习 evidence。

### 4.4 持久学习比部分文档更完整，但语义仍不闭合

`agents/director/src/durable-learning.ts` 已实现：

- 服务端读取 Memory 学习状态；
- 请求哈希、同 turn 重放和冲突拒绝；
- revision / previous turn 检查；
- 只有上一提示 `delivery.completed` 才评估；
- 通过 Memory API 提交，不直接写 Learner Profile。

这与 `agents/director/README.md`、`agents/director/docs/learning-loop.md` 和 `deploy/README.md`
中“未接 Shared State/ACK”的说法不一致。另一方面，`learning-loop.schema.json` 仍把
`state_scope` 固定为 `session_only`、`memory_write` 固定为 `not_performed`，在 durable 模式下会
误报执行事实。

### 4.5 新旧 Interaction/Director 双路径风险

- 新 `/agent/direct` 是学习优先路径；旧 `/agent/dispatch` 仍能写本地 JSONL/本地 KG store，
  不只是薄兼容转换层。
- 新 Interaction renderer 是单一小P；旧 Engine 仍按意图在五个人格间路由。
- 旧 Engine 有 OpenAI-compatible provider，但 compose 中的儿童新路径不调用真实 LLM。
- 旧 Engine 的 Recast 在 corrected form 缺失时可让 LLM 自行推断，不符合“由 Assessment 给定”的
  固定约束。

应明确旧路径为隔离演示/迁移入口，禁止其承担新产品的长期状态和儿童生产输出。

## 5. Trust Boundary 关键发现

### P0：Memory erase 后仍保留儿童原话

合成临时目录探针确认，一次 erase 后测试原话仍存在于：

1. 按 `session_id` 建键但按 `child_id` 清除的 WorkingMemory cache；
2. `erase.py` 生成的 fine-tune removal manifest；
3. 审计 SQLite/JSONL 的前 40 字符摘要；
4. erase 前创建的数据库 snapshot。

相关实现位于 `backend/memory_store/memstore/erase.py`、`service.py`、`working.py`、`audit.py`
和 `snapshot.py`。这意味着“从主表删除”不等于删除全部本地副本；当前实现不能满足仓库声明的
Erase/Privacy 边界。

### P0：旧 Interaction fallback 可重新引入被拒内容

基线 `agents/interaction/src/she_engine/engine.py` 先过滤 provider 输出，再把 Assessment 中的动态
`word` 插入 fallback 模板，但不会对最终模板二次过滤。合成禁词探针中，原输出被拒后，最终
fallback 又包含同一禁词；对最终文本运行同一 Safety filter 仍返回拒绝。

### P0/P1：Gateway 摄像头命令可绕过家长设置

`backend/device_gateway/src/app.ts` 的通用 `/commands` 端点没有 HTTP 认证，也没有在 `capture`
前检查 `camera_enabled` 或显式物理触发。合成 WebSocket 探针确认：先把 camera 设置为 false，
无认证 capture 仍返回 202 并送达模拟设备。Gateway 虽是正确的唯一设备边界，但尚未真正执行
该边界的授权策略。

### P0/P1：KG 审核边界可绕过

- `/kg/edges:batch`、rollback 和 conflict resolve 没有认证；
- caller 可通过 `force` 绕过 conflict；
- edge mutation 与 version/audit 分属事务，进程中断可能产生不一致；
- `KG_ONLINE_FALLBACK=1` 可把未审核 ConceptNet 在线结果直接返回调用方；
- 默认 KG 数据库/embedding 制品不在仓库，启动和检索不能由 CI 证明；
- KG 没有自动测试，也未纳入根验证。

外部网络默认关闭并不能替代硬边界。儿童实时链应完全不能启用该旁路。

## 6. 后台服务审计

### 6.1 Memory Store

已实现 SQLite 五类表、学习回合、候选 evidence、重放、ACK、快照、回滚、容量/遗忘、巩固和
HTTP API，68 项测试通过。主要缺口：

- erase 不彻底；
- HTTP API 无认证，可读写任意 child、伪造 actor、触发 purge/rollback；
- `/memory/episodes` 不验证共享 learning-event schema；
- caller 自报高 salience 可自动进入永久白名单；
- consolidation 对缺失 assessment 的记录保守放行。

### 6.2 Knowledge Graph

构建/清洗/检索/热更/快照/回滚代码量较完整，但属于需要外部产物和手工 acceptance 的工程
原型。仓库明确没有自动测试；默认磁盘也不含 canonical `kg.db`、embeddings 或人工审核报告。
因此 README 中的历史实测数字不能当成本次 checkout 的可复现通过证据。

### 6.3 Intel

离线 fetch/archive/structure/filter、候选审核与 KG bridge 已实现，27 项测试通过，并且没有发现
儿童实时链路直接调用 Intel/Zhihu。缺口是 token 默认空时全部放行，部分写端点和 raw archive
读取不做认证；Intel 内部批准也无法阻止调用者绕过它直接写无认证 KG batch。

### 6.4 Pointing

浏览器摄像头、MediaPipe 手势、2D 选物、track 关闭与模拟测试存在，42/42 项通过；README 中
“41/42”已过时。但它不消费 `shared/contracts/v1`，视觉描述是 stub，没有真实 YOLO 模型，
部分触发/WS 无认证，LLM 文本可绕过统一 Safety。它是有价值的浏览器原型，不是完整跨端感知服务。

## 7. 客户端、Gateway 与硬件

### 7.1 Web

实际 Web 是家长端 Dashboard，已实现首页、周报、设备设置、家长约束和明确 Mock 的隐私按钮。
它没有架构文档要求的浏览器 pointing、`/debug/session`、Agent Trace、KG/内容审核后台或 WebSocket。
基线干净依赖下测试 18 项通过、build 通过，但 typecheck 因 Gateway 的 optional `body` 与
`exactOptionalPropertyTypes` 不兼容而失败，根 `scripts/verify.ps1` 因此中止。

### 7.2 iOS

iOS 17 SwiftUI 工程有 Today、报告、设备、家长约束和隐私演示 UI；模型会拒绝不兼容契约，
也没有 mastery 写入口。隐私导出/删除明确是 Mock，Release 使用 `api.invalid`，Windows 无法运行
XCTest；只有 macOS CI 能证明工程生成和测试。

### 7.3 Gateway / Digital Twin

设备 WebSocket、运行时 JSON Schema、ACK、in-memory Digital Twin、家长 HTTP 和学习执行均有
代码与 13 项测试。Twin 重启丢失；HTTP 无生产身份边界；隐私 API只返回
`accepted_demo_only`，不会调用 Memory erase。`backend/digital_twin` 只有文档，真实实现位于
`backend/device_gateway/src/digital-twin.ts`，归属正确。

### 7.4 RX5

合成 runtime 验证了 hello、pointing、command ACK、重连、能力降级和摄像头 finally-close，
11 项测试通过。`RDKCamera.capture()` 仍返回固定 `unverified`/0 confidence；真实相机、模型、ALSA、
GPIO 和板端部署必须按 release playbook 真机验收。

## 8. 契约与端到端闭环

共享契约的 18 项测试与独立 validator 均通过（9 个 valid 接受、8 个 invalid 拒绝，version 1.0）。
Gateway/RX5 运行时直接消费 schema；iOS、Director 和 Python 有手写副本，存在漂移风险。

当前真实数据流分成两条：

```text
家长演示：Web/iOS → Gateway → DemoRepository

合成学习：synthetic caller → Gateway → Director → Memory
                                      ↓
                                  Interaction
                                      ↓
                             Gateway → RX5 simulator → ACK
```

第二条链的 `scripts/learning-smoke.mjs` 能验证重放、冲突、stale turn、单次播放、ACK 和一次
evidence，但 CI 的 Docker smoke 没有运行它；CI 只检查静态 Web、health、dashboard 和报告。

尚未形成的真实闭环包括：

- 真实 pointing/ASR 事件自动组成 Director turn；
- 真实 Story node/world state；
- 真实 TTS/灯效反馈；
- Web 调试 trace 与内容审核；
- 家长端 quest summary；
- 真实隐私请求到 Shared State；
- 生产身份、授权、加密和多家庭隔离。

## 9. 文档与实现漂移

| 文档声明 | 实际代码 |
|---|---|
| Interaction 是库、没有服务 | 已有 `/interaction/render` Flask 服务并被 compose 使用 |
| Director 未接 Shared State/ACK/重放 | durable-learning 已接 Memory 并检查 completed delivery |
| deploy 未接 Director/Memory | compose 已构建并连接二者 |
| Pointing 41/42 测试 | 当前 42/42 通过 |
| `engine/kb/store/route` 是现行路径 | 根规则已退休这些目录，但部分架构/组件文档仍引用旧路径 |
| Director 包是学习导演 | `package.json` 名称和若干日志仍是 `five-ministers-dispatch` |

应以根 `AGENTS.md` 的 ownership map 和当前代码为准，并在功能修复后同步组件 README；不能让
历史 PRD 或 target-state 文档替代可运行证据。

## 10. 本次基线验证证据

| 命令/组件 | 结果 |
|---|---|
| Shared contracts pytest | 18 passed |
| Contract validator | 9 valid accepted / 8 invalid rejected / v1.0 |
| Director tests / typecheck | 77 passed / 通过 |
| Interaction tests | 104 passed |
| Memory tests | 68 passed，1 个 FAISS/NumPy warning |
| Intel tests | 27 passed |
| Pointing tests | 42/42 passed |
| Gateway tests / typecheck / build | 13 passed / 通过 / 通过 |
| Web tests / build | 18 passed / 通过 |
| RX5 tests / simulator | 11 passed / hello、pointing、ACK 正常 |
| `release_readiness.ps1` | 通过 |
| `audit_repository.ps1` | 通过 |
| `scripts/verify.ps1` | **失败**：Web test tsconfig 下 Gateway `RequestInit.body` 类型错误 |

没有运行或不能证明：有状态 KG acceptance、远端 LLM、真实 ASR/发音、Docker 完整 RPG 流、
macOS iOS 测试、真实 RDK X5 和真实儿童研究。

## 11. 优先级与执行方向

### P0：先关闭信任边界

1. 最终输出（包括动态 fallback）统一再过 Safety；
2. erase 清除 cache、snapshot 与所有原话副本，manifest/audit 只留不透明 ID/计数；
3. Gateway capture/speak 命令执行授权、家长设置和显式触发规则；
4. KG/Memory/Intel 写端点建立不可选的认证与审核边界。

### P1：让教学判定可信

1. 用 Speech Act + 必需槽位替代词重合世界判定；
2. 区分 quest success、语言 evidence 和 mastery；
3. 接入真实的成功/失败历史，让 scaffold 可升可降；
4. 修复根验证并把合成学习 smoke 接入 CI。

### P2：形成现实语言 RPG

按 [`architecture/12-embodied-language-rpg.md`](architecture/12-embodied-language-rpg.md) 和
[`plans/2026-09-08-embodied-language-rpg.md`](plans/2026-09-08-embodied-language-rpg.md) 实现审核
StorySeed、节点、Speech Act、原子 World State、下一任务与端到端 trace。

### P3：产品化

补 Web 调试/运营面、家长 quest summary、跨语言 codegen、真实隐私工作流、监控、生产身份、
真机验收与儿童研究。未完成前保持“Mock/待验证”标签。

## 12. 最终判断

项目不是空架子：设备契约、合成执行、持久回合、多个后台和测试基础都值得保留。但“所有功能
已实现”不成立，尤其不能把硬编码规则、历史 README 验收数字、组件单测或模拟器成功等同于
完整 Agent 系统、儿童安全产品和真实硬件能力。

新的产品收敛方向应是有限、可审核、可重放的现实语言 RPG，而不是继续增加 Prompt 或人格：

```text
Object → Role → Speech Act → Virtual Action → World State → Next Quest
```

这一路径既能复用当前 Director/ACK/Memory/Gateway 基础，也能把本次审计发现的语义判定、状态
权威和安全边界问题变成可测试的工程约束。
