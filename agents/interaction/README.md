# Interaction Agent（LLM 剧情引擎）

**儿童唯一的语言出口。** 把孩子的开口转化为剧情推进，把人格转化为语言。所有后台 Agent 都隐藏在
它之后——儿童前台只面对一个稳定角色「小P」（`AGENTS.md` §0.2 / §28.4）。

纠错一律走 Recast（吸收式），不打断孩子（[`docs/architecture/02-agents.md`](../../docs/architecture/02-agents.md) §19）。

- 架构定位：`AGENTS.md` §29 与 [`docs/architecture/02-agents.md`](../../docs/architecture/02-agents.md) §3
- 设计与实现：[`docs/design.md`](docs/design.md)

## 运行

```bash
python -m pip install -e '.[dev]'      # 包名 she-engine
python examples/demo.py                # 最小对话演示（MockProvider，不打真实 LLM）
```

本组件是**库，不是服务**，没有端口。公开 API：

```python
from she_engine import Engine, EngineConfig, TurnRequest, TurnResponse
from she_engine.llm import MockProvider

engine = Engine(EngineConfig(provider=MockProvider(), session_level=1))
```

其余导出：`MemoryWrite`、`AsrResult`、`AssessResult`、`CtxBundle`。

## 测试

```bash
python -m pytest tests -q              # 103 用例
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

不直接消费 `shared/contracts/v1`。产出的 `MemoryWrite` 由 `agents/director` 汇总后写入
Shared State，且必须携带 evidence 状态——本组件不得让写入暗示已确认掌握（`AGENTS.md` §18）。

## 降级

LLM 不可用时走模板库，任何路径都不返回空响应。

## 历史

旧的「01 LLM 剧情引擎 PRD」（含 FR-E01…验收项）已归档在
[`docs/archive/prd/interaction-prd-v1.md`](../../docs/archive/prd/interaction-prd-v1.md)。
