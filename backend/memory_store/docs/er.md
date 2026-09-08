# 五库 Schema · ER 图（FR-M01 验收）

> 语义库 = KG（`kb/data/kg.db`，由 02 KG 工作流全权所有），本模块不建表，
> 仅经热更接口衔接（`/kg/runtime-consolidate`、`/kg/edges:batch`、`/kg/conflicts`）。
> 其余四库 + 引擎表物理存于 `data/store.db`（SQLite WAL），冷存储 `episodes_cold`
> 与白名单 `whitelist` 均为物理分表（FR-M05 物理隔离）。

```mermaid
erDiagram
    sessions ||--o{ episodes : "session_id 每轮对话落库(FR-M02)"
    sessions ||--o{ working_turns : "工作记忆写穿透"
    episodes ||--o| episodes_cold : "剪枝→冷存储(FR-M05)"
    episodes_cold ||--o| episodes : "再巩固恢复(FR-M06)"
    episodes ||--o| salience_buffer : "episode_id 缓冲镜像(FR-M09)"
    episodes ||--o| whitelist : "episode_id 白名单物理隔离(FR-G05)"
    salience_buffer ||--o| episodes : "降级落情景库(不清除)"
    working_turns ||--o| episodes : "LRU 溢出 evicted_to"
    episodes ||--o{ consolidation_ledger : "episode_ids 巩固回流"
    consolidation_ledger }o--|| pending_conflicts : "冲突边待审(FR-M04)"
    snapshots }o--|| meta : "store_version 快照/回滚(FR-M08)"
    erase_jobs ||--o{ consolidation_ledger : "72h 删除合规(非功能)"

    sessions {
        string session_id PK
        string child_id
        string script_state "剧情引擎 FR-E03 跨天续剧情"
        int chapter "当前剧本章节(StoryArc)"
    }
    working_turns {
        int id PK
        string session_id
        string child_id
        real ts
        string role
        string text
        int evicted_to "溢出后指向情景库"
    }
    episodes {
        int id PK "向量索引正 id"
        real ts
        string day "StoryArc 天"
        int chapter "StoryArc 剧本章节"
        string arc_id "剧本弧"
        string session_id
        string child_id
        string scene
        string utterance
        real assess "发音评估分 0-100"
        string emotion
        real emotion_v "效价 -1..1"
        real salience "EMA 置信度(FR-M05 衰减对象)"
        real last_decay "上次衰减时刻"
        string role
        string kind "dialogue/milestone/overflow/demoted"
        int whitelisted "豁免剪枝"
        int reconsolidated "再巩固次数"
    }
    episodes_cold {
        int id PK "沿用原 id, 向量索引负 id"
        real pruned_at
        string prune_reason
    }
    salience_buffer {
        int id PK
        string ref_id "route mw_* 上游 id"
        int episode_id
        string content
        real salience
        real last_touch
    }
    whitelist {
        int id PK
        string ref_id UK "只增不删"
        string reason
        real salience
        string source "auto/manual"
        int episode_id
    }
    procedural {
        int id PK
        string name
        string trigger "JSON: time|once|scene"
        string action "JSON: remind/summary/..."
        int enabled
        real last_fired "防同周期重复触发"
        int fire_count
    }
    consolidation_ledger {
        int id PK
        string job_id
        string child_id "删除合规依据"
        string episode_ids "JSON"
        string edges "JSON 已入 KG 的边"
        int kg_version
    }
    pending_conflicts {
        int id PK
        int kg_conflict_id
        string head
        string rel
        string tail
        string kind
        string status "open/resolved"
    }
    snapshots {
        int version PK
        string path "store.db + vectors + meta.json"
        string counts "JSON"
    }
    erase_jobs {
        int id PK
        string child_id
        real deadline_ts "请求+72h 合规红线"
        string status "completed/partial"
        string manifest_path "微调数据集剔除清单"
    }
    audit_log {
        int id PK
        string ts "谁/何时"
        string actor "agent:route/parent/system..."
        string action "ep_write/recall/prune/..."
        string target
        string summary "内容摘要, 保留 3 年"
    }
```

## 向量索引（`data/vectors.faiss`）

- `IndexIDMap2(IndexFlatIP)`，dim=256（`EMBED_DIM` 可调）。
- **id 约定**：情景库热存储 = `episodes.id`（正数），冷存储 = `-id`（负数）——
  单索引同时服务跨天召回与冷存储再巩固检索。
- 嵌入为确定性特征哈希（词 token + 中文字符 2/3-gram → L2 归一），保证
  "SQLite 原始数据可重建索引"（FAISS 损坏对策，README §6 风险表）；
  生产可替换神经编码器，`POST /memory/index/rebuild` 全量重嵌入。

## 版本与快照

- `meta.store_version` 单调递增：任何写路径（episode/程序性/剪枝/巩固/白名单/删除）+1。
- 快照以版本号为目录名 `data/snapshots/v{n}/`：`store.db`（SQLite backup API，
  含 WAL 合并）+ `vectors.*` + `meta.json`；先注册后备份，回滚后注册表不丢。
- 回滚：拷回 db+向量 → 从恢复库全量重建索引（保证库/向量一致）→
  版本 `max(当前, v)+1` 继续递增（对齐 kg 侧约定）。
