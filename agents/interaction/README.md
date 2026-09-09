# Interaction Agent（LLM 剧情引擎）

**儿童唯一的语言出口。** 它只把 Director 已决定、Shared State 已提交的动作渲染成小P的话，
不判断孩子是否成功，也不推进剧情。所有后台职责都隐藏在它之后——儿童前台只面对一个稳定
角色「小P」（`AGENTS.md` §0.2 / §28.4）。

纠错一律走 Recast（吸收式），不打断孩子（[`docs/architecture/02-agents.md`](../../docs/architecture/02-agents.md) §19）。

- 架构定位：`AGENTS.md` §29 与 [`docs/architecture/02-agents.md`](../../docs/architecture/02-agents.md) §3
- 设计与实现：[`docs/design.md`](docs/design.md)

## 运行

```bash
python -m pip install -e '.[dev]'      # 包名 she-engine
python examples/demo.py                # 最小对话演示（MockProvider，不打真实 LLM）
```

本组件同时提供 Python 库与仅供内部调用的审核模板服务。库公开 API：

```python
from she_engine import Engine, EngineConfig, TurnRequest, TurnResponse
from she_engine.llm import MockProvider

engine = Engine(EngineConfig(provider=MockProvider(), session_level=1))
```

其余导出：`MemoryWrite`、`AsrResult`、`AssessResult`、`CtxBundle`。

内部服务由 Device Gateway 调用：

```bash
python -m flask --app server run --port 8791
```

```text
POST /interaction/render
```

请求兼容 Learning Director 现有 `TeachingAction`，并接受 `action_id`、`prompt_id`、
`feedback_id`、`node_id`、`phase`、`world_role` 六个可选 RPG 字段。顶层字段、动作、目标句、
节点、角色、提示与反馈均走有限白名单；未知字段、错误类型或未审核枚举返回
`400 {"error":"invalid_action"}`。`ask`、`prompt`、`reinvite`、`advance_story`、`pause`、
`explore` 分别使用审核文案，所有出口（含降级）最终经过 `LocalSafetyFilter`。

## 测试

```bash
python -m pytest tests -q
python scripts/validate_assets.py      # 资产校验：提示词冻结 + 模板库 + 路由评测
```

> 测试与资产校验都读**相对路径** `assets/`，必须在本组件目录下运行
> （`scripts/verify.ps1` 即如此做）。在仓库根跑 `pytest agents/interaction/tests` 会因
> 加载不到资产而报错。

## 资产

```text
assets/ministers/<name>/v1.yaml   人格提示词，版本冻结
assets/templates/<name>.yaml      兜底模板库（LLM 不可用时仍有话说）
```

`ahai` / `laonie` / `wangguan` / `xiaop` / `xingxing` 是**人格资产**，不是后台 Agent；
不要据此恢复「五大臣 = 五后台 Agent」架构（`AGENTS.md` §28.3）。

## 涉及契约

不直接消费 `shared/contracts/v1`。内部渲染服务只消费 Director 已决定的 TeachingAction，
不判断任务是否完成，也不修改 world state。`MemoryWrite` 属于旧 Engine 库兼容类型；现实语言
RPG 主路径不由 Interaction 生成记忆写请求，长期 evidence 只通过 Director → Shared State
规则提交（`AGENTS.md` §18）。

## 降级

LLM 不可用时走模板库，任何路径都不返回空响应。

## 历史

旧的「01 LLM 剧情引擎 PRD」（含 FR-E01…验收项）已归档在
[`docs/archive/prd/interaction-prd-v1.md`](../../docs/archive/prd/interaction-prd-v1.md)。
