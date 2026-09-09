# Shared Memory Store（共享记忆存储）

Shared State Layer 的持久化底座：工作记忆、情景记忆、显著性缓冲、程序性记忆四库，
以及巩固 / 遗忘 / 再巩固生命周期、快照与回滚。语义层（KG）不在本组件，由
`backend/knowledge_graph` 拥有。

**Agent 不直接读写本组件的 SQLite / FAISS 文件**，只能走下列 HTTP 接口（`AGENTS.md` §20）。

- 架构定位：`AGENTS.md` §29 与 [`docs/architecture/03-shared-state.md`](../../docs/architecture/03-shared-state.md) §11
- 设计与实现：[`docs/design.md`](docs/design.md) · 五库 ER 图：[`docs/er.md`](docs/er.md)

## 运行

```bash
python -m pip install -r requirements.txt     # 只装运行依赖
python server.py          # 默认 127.0.0.1:8789
```

环境变量：`STORE_PORT`(8789) / `STORE_DATA`(data/) / `KG_URL`(http://127.0.0.1:8787，指向
`backend/knowledge_graph` 的热更新服务)。

主要端点：

```text
POST /memory/episodes           写情景
GET  /memory/recall?query=&k=   跨天检索（支持"上周/第一次"类时间查询）
POST /memory/consolidate        巩固批次（走 KG 热更新）
POST /memory/snapshot           快照       GET /memory/snapshots
POST /memory/erase              删除       GET /memory/erase/jobs
GET  /memory/salience  /whitelist  /audit  /metrics  /conflicts  /healthz
POST /memory/procedural         程序性任务  GET /memory/procedural/due
```

学习与 RPG 权威状态：

```text
GET  /memory/learning/state
POST /memory/learning/commit
POST /memory/learning/claim
POST /memory/learning/ack
```

`learning/commit` 在同一 SQLite 事务中校验并保存 `milk_picnic.v1` 的有限状态：上一节点、
连续 `world_revision`、canonical inventory、Speech Act evidence、上一 `action_id`/scaffold 和
world-event 引用。客户端不能直接写该接口；产品入口由 Gateway/Director 编排。同 turn 重放
返回原响应，不会重复发放虚拟道具。RPG 状态位于 `learning_turns.response`，沿用 session/child
删除根级联清除。

## 测试

```bash
python -m pip install -e '.[dev]'    # 运行依赖 + pytest
python -m pytest tests -q
```

`pyproject.toml` 只发布 `memstore/` 包（不发布 `server.py` 等顶层脚本），并通过
`[tool.pytest.ini_options] pythonpath` 让测试无需改 `sys.path` 即可导入。

## 涉及契约

`shared/contracts/v1/learning-event.schema.json` 与
`shared/contracts/v1/rpg-decision.schema.json`。写入必须携带 evidence 状态：
candidate 与 confirmed 语义不可混淆（`AGENTS.md` §18）。

## 运行时数据目录

`data/`（已 gitignore）：SQLite 库、FAISS 索引、快照。生成产物不入库。

## 历史

旧的「04 记忆存储 PRD」（含 FR-M01…FR-M08 验收项）已归档在
[`docs/archive/prd/memory_store-prd-v1.md`](../../docs/archive/prd/memory_store-prd-v1.md)。
它把五库描述为五个对话 Agent，那个模型已废弃（`AGENTS.md` §28.3）；记忆仍作为存储机制存在。
