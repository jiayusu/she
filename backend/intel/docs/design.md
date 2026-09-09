# 06 数据情报 · 实现说明 (IMPL)

本文档描述落地结构与运行方式。运行与测试见 [`../README.md`](../README.md)；
历史 PRD（已归档，非权威）：[`docs/archive/prd/intel-prd-v1.md`](../../../docs/archive/prd/intel-prd-v1.md)

## 运行

```bash
pip install -r requirements.txt          # flask + requests
cp .env.example .env                     # 填 ZHIHU_API (Access Secret)、LLM_API_KEY、WECOM_WEBHOOK

python server.py                         # API + 审核工作台  http://127.0.0.1:8791
python scheduler.py                      # 定时管线 (另开终端; 与 server 共享 SQLite)
python -m pytest tests/ -q               # 测试 (全离线, 不打真实网络)
```

生产部署建议：server.py / scheduler.py 各注册为系统服务；`.env` 权限 600，密钥进密钥管理（§5）。

## 模块 ↔ PRD 映射

| 模块 | 职责 | PRD |
|---|---|---|
| `zhihu_api.py` | Provider 层：`ZhihuProvider`（Bearer + X-Request-Timestamp）↔ `ManualProvider`（inbox/ 人工导入降级） | §8 风险对策 |
| `quota.py` | 共用日配额台账、优先级预留、超额→隔日补跑队列+去重告警 | FR-I07 |
| `pipeline.py` | 多查询词采集 → 排序(互动量加权) → 标题相似度>0.8 去重 → LLM 结构化 → 敏感词前置 | FR-I01/02/03 |
| `llm_client.py` + `prompts/` | OpenAI 兼容客户端（限速/退避）+ 三个提示词契约（version 冻结入库） | FR-I03/05/06 |
| `kg_bridge.py` | 硬闸门审核：approve/modify/discard 留痕 → `POST {KG_URL}/kg/edges:batch`，失败挂起 `kg_pending` 重试 | FR-I04 |
| `radar.py` | 英语启蒙话题语料 → LLM 聚类焦虑 TOP5 + 新兴方法论词 → 周报（附原始样本链接） | FR-I05 |
| `sentiment.py` | 品牌/竞品/品类词 30min 轮询 → LLM 倾向分类 → 高置信负面即时推送 | FR-I06 |
| `notify.py` | 企业微信机器人；webhook 未配置落 `outbox/`；每日 18:30 日报汇总（告警不风暴） | §5 |
| `archive.py` | 原始 JSON 90 天归档/清理/防目录穿越回读 | FR-I08 |
| `server.py` | §6 四接口 + 运维接口；`web/` 审核工作台 | §6 |
| `scheduler.py` | stdlib 定时器：fetch 02:00 / rerun 02:30 / purge 03:30 / sentiment 每30min / digest 18:30 / radar 周一 09:00 | FR-I01/05/06/07 |
| `web/index.html` | 审核工作台：通过/修改/丢弃，修改留痕，敏感条目禁批 | FR-I04 |

## 存储与合规（§5 / FR-I08）

- `data/intel.db`：候选/审核留痕/舆情/周报/配额/埋点，**永久存档**，可经 `GET /intel/archive?q=` 检索。
- `data/raw/YYYYMMDD/<purpose>/*.json`：**原始抓取**，保留 90 天（`RAW_RETENTION_DAYS`），`GET /intel/archive/raw?path=` 争议溯源（限 RAW_DIR 内，防穿越）。
- 结构化表只存 标题+200字摘录+链接；原文全文只存在于归档，不进工作台、不进 KG。
- 密钥只在 `.env`/环境变量，`.gitignore` 已排除。

## 唯一入产品路径（§7 红线）

```
zhihu_search (仅服务端, Bearer)
  → pipeline 采集/去重 (原始 JSON 归档 90 天)
  → LLM 结构化 (敏感词前置过滤, §8)
  → 人工审核工作台 (approve/discard, 修改留痕)   ← 硬闸门: filtered/pending 不可入 KG
  → POST /kg/edges:batch {source:"zhihu_intel:<id>"}   ← 只推英文知识三元组
  → 王冠本地检索 (kb 服务, 可回滚 /kg/rollback)
```

- 本仓**不注册任何 MCP 工具**（`tests/test_guard.py` 守卫扫描），搜索能力不出服务端。
- 知乎原文不出现在任何面向孩子的输出；入 KG 的只有 LLM 提炼 + 人工改写后的三元组。

## 降级矩阵（§5 / §8）

| 故障 | 表现 | 自愈 |
|---|---|---|
| 搜索接口 90001/未开通 | 单用途告警一条，其余用途照常 | hot_list 仍可用；`ZHIHU_PROVIDER=manual` + inbox/ 人工导入 |
| 配额耗尽 | `quota.allow` 拒绝 → jobs 队列 + 告警 | 次日 02:30 `rerun` 自动补跑 |
| LLM 不可用 | 条目挂 `pending_struct` 下轮重试 | 恢复后结构化，不丢数 |
| KG 不可达 | 条目挂 `kg_pending` | 调度器每日重试 `kg_bridge.retry_kg_pending` |
| 企微未配置 | 消息落 `outbox/*.md` | 人工转发 |

实测记录（2026-09-05）：本 key `hot_list` 正常；`zhihu_search`/`global_search` 返回 90001（疑未实名开通）。系统即在降级矩阵下工作——正是 PRD §8 预判场景。

## 平台接口速查（developer.zhihu.com/api/v1）

- `GET content/zhihu_search?Query=&Count≤10`、`GET content/global_search?Query=&Count≤20`、`GET content/hot_list?Limit≤30`
- 头：`Authorization: Bearer <secret>` + `X-Request-Timestamp`（秒级，±10min）
- `GET quota?APIIDs=` 查额度（不耗业务额度；实测 zhihu_search 5000/天、hot_list 100/天）
- 错误码：0 成功 / 20001 鉴权 / 30001 限频 / 90001 内部错误

## 埋点（§9）

`GET /intel/metrics`：`intel_fetched` / `intel_structured`(含 ok_rate) / `intel_approved` / `intel_report_sent` / `intel_quota_used`（本地台账 + 平台侧余额对照）。台账只记 `zhihu_api` Provider 的真实平台调用；manual 导入与测试桩不占用 FR-I07 的"月度实际调用 ≤1 万次"口径。
