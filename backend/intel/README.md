# Data Intelligence（数据情报后台）

离线内容生产层：采集外部英语启蒙语料 → LLM 结构化 → 敏感过滤 → **人工审核硬闸门** →
推入 KG → 可回滚。产出运营情报（家长焦虑雷达、品牌舆情）。

**红线：本组件不在儿童实时链路上**（`AGENTS.md` §0.7 / §20）。知乎原文不出现在任何面向孩子的
输出；入 KG 的只有 LLM 提炼 + 人工改写后的三元组。本仓不注册任何 MCP 工具，搜索能力不出服务端
（`tests/test_guard.py` 守卫扫描）。

- 架构定位：`AGENTS.md` §29 与 [`docs/architecture/04-backend-services.md`](../../docs/architecture/04-backend-services.md) §15
- 设计与实现：[`docs/design.md`](docs/design.md)（模块映射、降级矩阵、平台接口速查）

## 运行

```bash
python -m pip install -r requirements.txt
cp .env.example .env      # 填 ZHIHU_API / LLM_API_KEY / WECOM_WEBHOOK

python server.py          # API + 审核工作台，默认 127.0.0.1:8791
python scheduler.py       # 定时管线（另开终端，与 server 共享 SQLite）
```

环境变量：`INTEL_PORT`(8791) / `INTEL_DB` / `KG_URL`(http://127.0.0.1:8787) / `INTEL_TOKEN`
（设非空则变更接口需 `X-Intel-Token`）。生产部署把 `server.py` 与 `scheduler.py` 各注册为系统服务，
`.env` 权限 600。

## 测试

```bash
python -m pip install -r requirements-dev.txt   # 运行依赖 + pytest
python -m pytest tests -q                      # 27 用例，全离线，不打真实网络
```

本组件是扁平模块布局，顶层模块名很通用（`config` / `db` / `server` / `llm_client`），
因此 `pyproject.toml` **只提供工具配置，不声明可安装包**——发布这些名字会与
`backend/knowledge_graph` 的同名模块冲突。测试的导入路径由
`[tool.pytest.ini_options] pythonpath` 提供，不再改 `sys.path`。

## 涉及契约

不直接消费 `shared/contracts/v1`。对外只经 `POST {KG_URL}/kg/edges:batch` 推送三元组，
`source` 标记为 `zhihu_intel:<id>`，失败挂 `kg_pending` 重试。

## 唯一入产品路径（红线）

```text
zhihu_search（仅服务端，Bearer）
  → pipeline 采集/去重（原始 JSON 归档 90 天）
  → LLM 结构化（敏感词前置过滤）
  → 人工审核工作台（approve/discard，修改留痕）   ← 硬闸门：filtered/pending 不可入 KG
  → POST /kg/edges:batch                          ← 只推英文知识三元组
  → 本地检索（可 /kg/rollback 回滚）
```

## 运行时数据目录

`data/`（已 gitignore）：`intel.db` 永久存档、`raw/YYYYMMDD/` 原始抓取保留 90 天。
结构化表只存标题 + 200 字摘录 + 链接；原文全文只在归档，不进工作台、不进 KG。

## 历史

旧的「06 数据情报 PRD」（含 FR-I01…FR-I08 验收项）已归档在
[`docs/archive/prd/intel-prd-v1.md`](../../docs/archive/prd/intel-prd-v1.md)。
