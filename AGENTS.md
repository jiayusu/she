# AGENTS.md

> 项目级 Agent 架构与后台组件协作约定
> 适用范围：儿童英语启蒙穿戴设备后台、LLM 剧情引擎、知识图谱、记忆、指向识别、数据情报及后续 Agent 实现。

本文件是**索引与硬规则**：组件归属、工具边界、工作纪律。
详细架构说明按主题拆分在 `docs/architecture/`，各节沿用原有编号（§0–§39），既有交叉引用继续有效。

## Canonical Ownership Map

The retired top-level directories `engine`, `route`, `kg`, `store`, `po`, and `zhihu` are migration sources only. New code and operational references use:

```text
agents/interaction       Interaction Agent and presentation assets
agents/director          Learning Director and orchestration
backend/knowledge_graph  reviewed, versioned KG service
backend/memory_store     shared memory service
backend/pointing         pointing recognition service
backend/intel            Zhihu/data intelligence pipeline
backend/digital_twin     documentation only; twin implementation lives in backend/device_gateway/src/digital-twin.ts
backend/device_gateway   sole hardware/software transport boundary
```

The RX5 runtime is mocked until physical SSH validation. See `backend/digital_twin/deployment.md` and `clients/hardware-rx5/docs/deployment.md`.

---

## 导航

先读本文件的硬规则（§20 / §28 / §29 / §38 / §39），再按需要打开对应主题文件。
**不需要为了查一条规则通读全部架构文档。**

| 文件 | 内容 | 原节号 |
|---|---|---|
| [`docs/architecture/01-overview.md`](docs/architecture/01-overview.md) | 项目目标、四层架构、北极星指标、设计原则、端侧原则 | §0, §1, §27, §30, §36 |
| [`docs/architecture/02-agents.md`](docs/architecture/02-agents.md) | 7 个 Agent 的职责与输入输出、Recast 原则 | §2–§10, §19 |
| [`docs/architecture/03-shared-state.md`](docs/architecture/03-shared-state.md) | Shared State Layer、记忆迁移映射、长期写入规则 | §11, §12, §18 |
| [`docs/architecture/04-backend-services.md`](docs/architecture/04-backend-services.md) | 指向识别、KG 后台、数据情报后台 | §13, §14, §15 |
| [`docs/architecture/05-hardware-rx5.md`](docs/architecture/05-hardware-rx5.md) | 硬件端 RX5 与摄像头边界 | §31 |
| [`docs/architecture/06-web.md`](docs/architecture/06-web.md) | Web 端调试台、Agent Trace、运营后台 | §32 |
| [`docs/architecture/07-parent-app.md`](docs/architecture/07-parent-app.md) | 家长端首页、报告、设备管理、隐私 | §33 |
| [`docs/architecture/08-contracts.md`](docs/architecture/08-contracts.md) | Agent 间契约、四端通信关系 | §25, §34 |
| [`docs/architecture/09-runtime-flows.md`](docs/architecture/09-runtime-flows.md) | 单轮执行、决策优先级、故障降级、端到端交互 | §16, §17, §21, §35 |
| [`docs/architecture/10-testing.md`](docs/architecture/10-testing.md) | 各 Agent 测试要求 | §26 |
| [`docs/architecture/11-agentic-loop-design-reference.md`](docs/architecture/11-agentic-loop-design-reference.md) | Agentic Loop / Hook 设计参考（扩展提案） | — |
| [`docs/architecture/12-embodied-language-rpg.md`](docs/architecture/12-embodied-language-rpg.md) | **当前产品主循环**：现实物体、Speech Act、世界状态与下一任务 | — |
| [`docs/architecture/99-target-state.md`](docs/architecture/99-target-state.md) | **目标状态，非现状**：建议目录与完整组件地图 | §24, §37 |
| [`docs/archive/migration-legacy-ministers.md`](docs/archive/migration-legacy-ministers.md) | **历史归档**：旧五大臣架构与迁移原则 | §22, §23 |

### 组件文档约定

每个组件目录下：

```text
<component>/README.md        必需：职责 / 如何运行 / 如何测试 / 涉及哪些契约
<component>/docs/design.md   可选：设计与实现细节
```

其他入口：`README.md`（仓库总览与本地验证命令）、`playbooks/`（变更、事故、决策、发布记录）、
`skills/`（可复用流程）、`docs/archive/`（历史文件，非权威，不要据此判断现状）。

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

> 本表是**磁盘真实状态**，与开头 Canonical Ownership Map 一致。
> 历史目录 `engine`、`kb`、`store`、`route`、`po`、`zhihu` 已退役且不在磁盘上；
> 它们的职责归属见下表"取代者"一列，迁移说明见 `docs/archive/migration-legacy-ministers.md`。

| 组件 | 做什么 | 在新架构中的位置 | 取代的历史目录 |
|---|---|---|---|
| `agents/interaction` | LLM 输出、Recast、语言等级、剧情状态、模板、降级 | Interaction + Story 的执行底座 | `engine` |
| `agents/director` | 学习优先调度；Curriculum / Scaffold / Story / Assessment / Learner Model | Agent 教学层入口 | `route` |
| `backend/knowledge_graph` | 儿童英语通用知识、词汇关系、检索、热更新 | Curriculum / Story 的知识底座 | `kb`、`kg` |
| `backend/memory_store` | 工作/情景/显著性/程序性记忆、快照、删除 | Shared State 持久化底座 | `store` |
| `backend/pointing` | 手势 + 物体指向识别 | 感知层 | `po` |
| `backend/intel` | 外部内容采集、运营情报、人工审核入 KG | 离线内容生产层 | `zhihu` |
| `backend/device_gateway` | 唯一硬件/软件传输边界；并**拥有 Digital Twin 实现** (`src/digital-twin.ts`) | 设备边界 | — |
| `backend/digital_twin` | **仅文档目录，无代码**；实现在 `backend/device_gateway/src/digital-twin.ts` | 文档边界 | — |
| ASR / 发音评估 | 语音识别与语言评估 | Assessment 上游；具体实现不在本批文档 | — |
| Safety | 儿童内容安全硬钩子 | Trust Boundary；具体实现不在本批文档 | — |
| TTS / 设备灯效 | 输出执行 | Interaction 下游 | — |

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

所有 Coding Agent 必须使用**仓库相对路径**，并把每个可独立审查的逻辑变更与工程经验留在仓库中。

> 绝对盘符路径（Windows 盘符加冒号开头的路径）不可移植：仓库可以被 clone 到任意位置，CI 在 Linux 上运行。
> 文档与脚本中一律使用相对于仓库根的路径；`scripts/audit_repository.ps1` 会机械阻止绝对盘符路径回归。

## 39.1 修改前

1. 先标记所属层：Hardware、Web、App、Agent、Backend Service、Shared State、Trust Boundary 或 Repository。
2. 搜索 `skills/` 与 `playbooks/incidents/` 是否已有同类情境。
3. 命中 skill 时必须先完整读取并按其验证步骤执行；不得凭记忆复述旧步骤。
4. 命中 incident 但没有 skill 时，先复现 fingerprint，再采用已验证 resolution。
5. 跨端字段变化必须先改 `shared/contracts/`，不得先在某一个客户端私加字段。

## 39.2 修改中

1. 功能与修复遵循测试先行：先观察目标测试因缺少行为而失败，再写最小实现。
2. 新发现错误先做根因分析，不把猜测或无效尝试写成解决方案。
3. 不在日志、fixtures、playbooks 或测试快照中写入密钥、儿童原话、原始音频、原始图像或生产数据库内容。
4. 未经真实 RDK X5 验证的硬件步骤必须标记为待真机验收，不能声称成功。

## 39.3 修改后

1. 每个逻辑变更必须在 `playbooks/changes/` 留下一条记录，并与代码放在同一 commit。
2. 错误解决记录使用 `playbooks/templates/incident.md`，必须包含复现与通过证据。
3. 只有可重复、步骤稳定、输入输出明确且有验证命令的流程才能升级为 skill。
4. 同一错误或情境再次出现时，优先运行已有 skill；skill 与现实不符时先记录新证据，再修订 skill。
5. 可由脚本或测试机械执行的规则优先自动化，不用冗长 skill 替代检查器。

## 39.4 首批项目 skills

```text
skills/she-ios-soft-orbit/SKILL.md
```

跨端契约顺序与 incident recovery 已由本文件、Schema validator 和 playbook 模板约束。无 skill 压力测试表明通用 Agent 能正确处理这两类问题，因此不重复建立文档 skill；机械约束优先自动化。

RDK X5 首次连接流程当前保存在 release playbook。只有完成一次真实板端执行、修正和复验后，才允许建立 `she-rx5-preflight` skill。

## 39.5 当前实现状态（2026-09-09）

新的学习优先调度入口已在 `agents/director/` 提供：

```text
POST /agent/direct
```

该入口返回 `curriculum`、`scaffold`、`story` 和唯一 `teaching_action`，不返回 minister，
并严格区分 `language_level` 与 `scaffold_level`。持久模式经 Memory API 读写，不直接访问
Learner Profile、KG 或 SQLite。

现实语言 RPG MVP 已加入代码，当前只允许审核种子 `milk_picnic.v1`：

```text
Gateway POST /v1/rpg/direct
  → Director: StorySeed + SpeechActResolver + 唯一 TeachingAction
  → Memory: 原子校验 world revision / evidence / event
  → Interaction: 审核话术 + 最终 Safety
  → Gateway POST /v1/learning/execute → 设备 ACK
```

`GET /v1/rpg/state` 只返回 `rpg-quest-summary` 脱敏投影，客户端没有 world/mastery 写接口。
旧 `POST /agent/dispatch` 与 `/v1/learning/*` 仅用于迁移兼容；新产品调用使用 Gateway 的
`/v1/rpg/*`。最新 RPG runtime 改动尚未执行完整验证，详见对应 change records；真实 ASR、
发音 evaluator、自动设备事件编排、生产认证和 RDK X5 真机仍未完成。
