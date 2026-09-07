# 04 记忆存储 · 实现说明

PRD 见 [README.md](README.md)。五库 ER 图见 [docs/er.md](docs/er.md)。

## 快速开始

```bash
pip install -r requirements.txt
python -m pytest tests/ -q     # 61 用例: 9 条 FR 验收 + 非功能 + HTTP e2e
python scripts/acceptance.py   # 红线实测: 20/20 通过
python server.py               # 启动服务(默认 127.0.0.1:8789, STORE_PORT 可配)
```

```bash
# 冒烟: 每轮对话落一条 episode(来自 route FR-G04 调度)
curl -s http://127.0.0.1:8789/memory/episodes -H 'content-type: application/json' \
  -d '{"utterance":"I like apples","scene":"朝会","assess":92,"salience":0.6,"session_id":"s1"}'

# 跨天召回(阿海), 支持"第一次/上周/第N章"时间查询
curl -s "http://127.0.0.1:8789/memory/recall?query=上周第一次说的apple&k=5"
```

环境变量:`STORE_PORT`(8789) / `STORE_DATA`(data/) / `KG_URL`(http://127.0.0.1:8787,
指向 kb/server.py) / `KG_TIMEOUT_S`(30, 超时批次落 outbox 可重推) /
`DECAY_LAMBDA`(0.05) / `PRUNE_FLOOR`(0.05) /
`CONSOLIDATE_MIN_ASSESS`(80) / `WHITELIST_THRESHOLD`(0.8) / `AUTO_JOBS`(1)。

## 目录结构

```
store/
├── README.md                PRD(需求来源, 未改动)
├── IMPLEMENTATION.md        本文档
├── requirements.txt
├── server.py                Flask HTTP(§6 接口冻结 + 管理/合规端点)
├── memstore/
│   ├── config.py            环境变量配置(全部有默认值)
│   ├── schema.py            五库 DDL(FR-M01, ER 见 docs/er.md)
│   ├── db.py                SQLite(WAL) 连接 + meta/单调版本
│   ├── vector.py            哈希嵌入 + FAISS IndexIDMap2(numpy 兜底)
│   ├── temporal.py          时间查询解析(FR-M03, 语义文档化)
│   ├── working.py           库1 工作记忆(10 条, LRU 溢出, 崩溃恢复)
│   ├── episodic.py          库2 情景库(SQLite+FAISS, 冷存储分表)
│   ├── salience.py          库4 显著性缓冲(1k)+白名单(物理隔离只增不删)
│   ├── procedural.py        库5 程序性库(500, 触发-动作, due 纯函数)
│   ├── lifecycle.py         EMA 衰减剪枝(FR-M05) + 再巩固(FR-M06)
│   ├── consolidate.py       巩固管线(FR-M04): 发音闸门→KG 热更→冲突待审, outbox
│   ├── snapshot.py          快照/回滚(FR-M08) + FAISS 损坏自愈
│   ├── erase.py             72h 删除合规 + 微调数据集剔除清单
│   ├── audit.py             统一审计(表+按天 JSONL, 3 年保留)
│   └── metrics.py           §8 埋点 + 延迟分位
├── tests/                   pytest(61 用例)
└── scripts/acceptance.py    红线实测(自包含, 含 KG 桩)
```

## 接口清单

**§6 冻结接口**:`POST /memory/episodes` · `GET /memory/recall?query=` ·
`POST /memory/consolidate` · `GET /memory/procedural/due` ·
`POST /memory/snapshot` / `POST /memory/rollback/{v}`

**扩展端点**:工作记忆 `POST /memory/working/{sid}/push` · `GET /memory/working/{sid}`
(空则自动从情景库重建);剧本状态 `POST /memory/session/{sid}/state`(FR-E03 跨天续剧情);
程序性管理 `POST /memory/procedural` · `POST /memory/procedural/{id}/fired`;
白名单 `POST /memory/whitelist`(只增不删);冲突待审 `GET /memory/conflicts` ·
`POST /memory/conflicts/{id}/resolve`(对齐 route `/admin/kg/pending-review`);
outbox 重推 `POST /memory/consolidate/flush`;运维 `GET /memory/metrics` ·
`GET /memory/audit` · `GET /memory/snapshots` · `POST /memory/index/rebuild` ·
`POST /memory/jobs/run`;合规 `POST /memory/erase` · `GET /memory/erase/jobs`。

## 验收对照

| PRD 验收 | 实现 | 实测(scripts/acceptance.py) |
| --- | --- | --- |
| FR-M01 五库 Schema,物理分离 | `schema.py` 六张主表 + 语义库=KG 衔接 | ✅ 表物理分离,cap 10/1000/500 |
| FR-M02 写入 ≤20ms,top-k ≤50ms | `episodic.py` + `vector.py` 全路径 | ✅ 写 p95=2.1ms,召回 p95=6.2ms(500 库存) |
| FR-M03 时间查询准确率 ≥80% | `temporal.py` 语义文档化 + 章节过滤 | ✅ 19/20=95%,章节/第一次端到端 |
| FR-M04 巩固走 KG 热更新,冲突待审 | `consolidate.py`:闸门→/kg/*→镜像 | ✅ KG 版本+1,assess=55 被拦,冲突入队 |
| FR-M05 EMA 剪枝,白名单 3 年零丢失 | `lifecycle.py` 增量衰减+冷存储搬移 | ✅ 1095 步模拟零丢失,日志可审计 |
| FR-M06 再巩固恢复加权 | 召回命中冷存储(负 id)自动恢复 | ✅ 0.5→0.85,reconsolidated=1 |
| FR-M07 20:30 准时率 100% | `procedural.py` due 纯函数+mark_fired 防重 | ✅ 30 天逐 5 分钟采样 8640/8640 |
| FR-M08 快照回滚 ≤1 分钟 | `snapshot.py` backup API+重建索引 | ✅ 回滚 15.8ms;FAISS 损坏自愈 |
| FR-M09 溢出策略 | `working.py` LRU→overflow;`salience.py` 降级 | ✅ 单测覆盖,内容不清除 |
| 非功能 审计 3 年 | `audit.py` 表+JSONL 双写,enforce_retention | ✅ 过期清理,近期保留 |
| 非功能 崩溃恢复 ≤2s | `working.recover` 从情景库重建 | ✅ 3000 条库存实测 0.3ms |
| 非功能 72h 删除 | `erase.py` 物理清除+剔除清单+KG 推送 | ✅ manifest 含 fine_tune_removal |
| §6 接口 + §8 埋点 | `server.py` / `metrics.py` | ✅ HTTP e2e(tests/test_http.py) |

## 与兄弟模块的衔接

- **route(03,Agent 调度)**:FR-G04 memory_write → `POST /memory/episodes`;
  FR-G05 白名单 → salience≥0.8 自动落 `whitelist` 表或 `POST /memory/whitelist`;
  FR-G06/G07 巩固调度壳 → `POST /memory/consolidate`;冲突待审对齐
  `/admin/kg/pending-review`。衰减参数与 route `config/salience.json` 对齐
  (λ=0.05/天,floor=0.05,白名单阈值 0.8)。
- **kb(02,KG 工作流)**:语义库即 `kb/data/kg.db`;巩固走 `/kg/runtime-consolidate`
  (共现词对)与 `/kg/edges:batch`(显式边),冲突镜像进本模块待审队列,resolve 透传
  `/kg/conflicts/{id}/resolve`;KG 不可达时批次落 outbox,`flush` 重推不丢批。
- **engine(01,剧情引擎)**:FR-E03 剧本状态 → `POST /memory/session/{sid}/state`;
  FR-E08 上下文注入 → `GET /memory/working/{sid}` + recall。

## 设计要点

1. **冷存储物理分表**:`episodes_cold` 独立表 + 向量索引负 id 空间——剪枝是搬移
   不是删除,再巩固(FR-M06)可原样恢复;白名单再物理分表,只增不删。
2. **EMA 增量衰减**:记录 `last_decay`,每步 `salience *= exp(-λ·Δ天)`,与 route
   的 `score·exp(-λ·闲置天数)` 数学等价,但支持按天多次推进与再巩固回血。
3. **可重建性**:嵌入确定性 + SQLite 原始数据全量重嵌入,FAISS 损坏/缺失在
   启动自检自动重建(README §6 风险 1 对策)。
4. **快照先注册后备份**:快照文件自身携带 snapshots 注册行,回滚不丢注册表;
   回滚后一律从恢复库重建索引,杜绝库/向量不一致。
5. **删除合规**:`consolidation_ledger` 记录每个孩子巩固出的 KG 边,删除时一并
   生成 `fine_tune_dataset_removal` 剔除清单并推送 KG 删除(README §6 风险 3 对策);
   审计日志自身保留作为合规证明。
