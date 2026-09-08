"""schema.py — 五库 Schema(FR-M01)与公共库函数。

五库物理分离:
  库1 工作记忆  working_turns + sessions   (RAM 常驻, SQLite 仅会话状态/恢复源)
  库2 情景库    episodes + episodes_cold   (SQLite, 冷存储物理分表; 向量见 vectors.faiss)
  库3 语义库    = KG(kb 模块 kg.db)        (本模块不建表, 仅走热更接口衔接)
  库4 显著性    salience_buffer + whitelist(白名单物理隔离, 只增不删)
  库5 程序性    procedural                 (触发-动作, 容量 500)

引擎表: consolidation_ledger(回流台账,删除合规) / pending_conflicts(冲突待审队列) /
        consolidation_jobs(KG 离线 outbox) / snapshots / erase_jobs / audit_log / meta。
ER 图见 docs/er.md。
"""
DAY_MS = 86400.0

SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions(               -- 剧本状态持久化(剧情引擎 FR-E03 依赖)
  session_id  TEXT PRIMARY KEY,
  child_id    TEXT NOT NULL DEFAULT 'default',
  script_state TEXT NOT NULL DEFAULT '{}',         -- JSON: {plot, act, chapter...}
  chapter     INTEGER NOT NULL DEFAULT 1,          -- 当前剧本章节(StoryArc)
  updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS working_turns(          -- 工作记忆写穿透镜像(审计可查, 恢复辅证)
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id TEXT NOT NULL,
  child_id TEXT NOT NULL DEFAULT 'default',
  ts REAL NOT NULL,
  role   TEXT NOT NULL DEFAULT 'child',
  text   TEXT NOT NULL,
  scene  TEXT NOT NULL DEFAULT '',
  evicted_to INTEGER                              -- LRU 溢出后指向情景库 episode id
);
CREATE INDEX IF NOT EXISTS ix_wt_session ON working_turns(session_id, ts);

CREATE TABLE IF NOT EXISTS episodes(               -- 库2 情景库(热存储)
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts REAL NOT NULL,                                -- 事件时间(epoch 秒)
  day TEXT NOT NULL,                               -- StoryArc: 天 YYYY-MM-DD
  chapter INTEGER NOT NULL DEFAULT 1,              -- StoryArc: 剧本章节
  arc_id  TEXT NOT NULL DEFAULT '',                -- 剧本弧标识
  session_id TEXT NOT NULL DEFAULT '',
  child_id  TEXT NOT NULL DEFAULT 'default',
  scene TEXT NOT NULL DEFAULT '',
  utterance TEXT NOT NULL,                         -- 原句/内容
  assess REAL,                                     -- 发音/学习评估分(0-100)
  emotion TEXT NOT NULL DEFAULT '',                -- 情绪标签
  emotion_v REAL,                                  -- 情绪效价 -1..1
  salience REAL NOT NULL DEFAULT 0.3,              -- 显著性置信度(EMA 衰减对象)
  last_decay REAL NOT NULL DEFAULT 0,              -- 上次衰减时刻(EMA 增量用)
  role  TEXT NOT NULL DEFAULT 'child',
  kind  TEXT NOT NULL DEFAULT 'dialogue',          -- dialogue/milestone/overflow/demoted
  whitelisted INTEGER NOT NULL DEFAULT 0,
  reconsolidated INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS ix_ep_day ON episodes(day, ts);
CREATE INDEX IF NOT EXISTS ix_ep_chapter ON episodes(chapter, ts);
CREATE INDEX IF NOT EXISTS ix_ep_session ON episodes(session_id, ts);
CREATE INDEX IF NOT EXISTS ix_ep_child ON episodes(child_id, ts);
CREATE TABLE IF NOT EXISTS episodes_cold(          -- 库2 冷存储: 被剪除记忆(FR-M06 可恢复)
  id INTEGER PRIMARY KEY,                          -- 沿用原 episode id
  pruned_at REAL NOT NULL,
  prune_reason TEXT NOT NULL DEFAULT '',
  -- 以下与 episodes 同构
  ts REAL NOT NULL, day TEXT NOT NULL, chapter INTEGER NOT NULL DEFAULT 1,
  arc_id TEXT NOT NULL DEFAULT '', session_id TEXT NOT NULL DEFAULT '',
  child_id TEXT NOT NULL DEFAULT 'default', scene TEXT NOT NULL DEFAULT '',
  utterance TEXT NOT NULL, assess REAL, emotion TEXT NOT NULL DEFAULT '',
  emotion_v REAL, salience REAL NOT NULL DEFAULT 0.3, last_decay REAL NOT NULL DEFAULT 0,
  role TEXT NOT NULL DEFAULT 'child', kind TEXT NOT NULL DEFAULT 'dialogue',
  whitelisted INTEGER NOT NULL DEFAULT 0, reconsolidated INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS ix_epc_child ON episodes_cold(child_id);

CREATE TABLE IF NOT EXISTS salience_buffer(        -- 库4 显著性缓冲(容量 1000)
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ref_id TEXT NOT NULL DEFAULT '',                 -- 上游记忆 id(route mw_* 等)
  episode_id INTEGER,                              -- 关联情景库行(降级时不清除)
  content TEXT NOT NULL,                           -- 内容摘要
  salience REAL NOT NULL DEFAULT 0.3,
  kind TEXT NOT NULL DEFAULT 'dialogue',
  child_id TEXT NOT NULL DEFAULT 'default',
  source TEXT NOT NULL DEFAULT 'agent',            -- actor: agent/parent/system
  last_touch REAL NOT NULL DEFAULT 0,
  last_decay REAL NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS ix_sb_sal ON salience_buffer(salience);
CREATE TABLE IF NOT EXISTS whitelist(              -- 白名单: 物理隔离, 只增不删(FR-G05)
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ref_id TEXT NOT NULL UNIQUE,
  content TEXT NOT NULL DEFAULT '',
  reason  TEXT NOT NULL,
  salience REAL NOT NULL DEFAULT 1.0,
  source  TEXT NOT NULL DEFAULT 'auto',            -- auto(杏杏规则)/manual(家长)
  child_id TEXT NOT NULL DEFAULT 'default',
  episode_id INTEGER,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS procedural(             -- 库5 程序性库(容量 500, 触发-动作)
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  trigger TEXT NOT NULL,                           -- JSON: {type:time/once/scene,...}
  action  TEXT NOT NULL,                           -- JSON: {type,text,...}
  enabled INTEGER NOT NULL DEFAULT 1,
  last_fired REAL,
  fire_count INTEGER NOT NULL DEFAULT 0,
  child_id TEXT NOT NULL DEFAULT 'default',
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS consolidation_ledger(   -- 巩固回流台账(72h 删除合规依据)
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  job_id TEXT NOT NULL,
  child_id TEXT NOT NULL DEFAULT 'default',
  episode_ids TEXT NOT NULL DEFAULT '[]',          -- JSON 数组
  edges TEXT NOT NULL DEFAULT '[]',                -- JSON: [{head,rel,tail}] 已入 KG 的边
  kg_version INTEGER,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS pending_conflicts(      -- 冲突边待审队列(FR-M04, 镜像 KG conflicts)
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  kg_conflict_id INTEGER,
  head TEXT NOT NULL, rel TEXT NOT NULL, tail TEXT NOT NULL,
  kind TEXT NOT NULL DEFAULT '',
  detail TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL DEFAULT 'open',             -- open/resolved
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS consolidation_jobs(     -- KG 不可达时的 outbox(写失败不丢批)
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  payload TEXT NOT NULL,                           -- JSON: 原始巩固批次
  status TEXT NOT NULL DEFAULT 'queued',           -- queued/sent/failed
  attempts INTEGER NOT NULL DEFAULT 0,
  last_error TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS snapshots(
  version INTEGER PRIMARY KEY,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  path TEXT NOT NULL,
  note TEXT NOT NULL DEFAULT '',
  counts TEXT NOT NULL DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS erase_jobs(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  child_id TEXT NOT NULL,
  requested_by TEXT NOT NULL DEFAULT 'parent',
  deadline_ts REAL NOT NULL,                       -- 72h 合规红线
  status TEXT NOT NULL DEFAULT 'completed',        -- completed/partial
  stats TEXT NOT NULL DEFAULT '{}',
  manifest_path TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS audit_log(              -- 统一审计(另落按天 JSONL, 保留 3 年)
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts TEXT NOT NULL DEFAULT (datetime('now')),
  actor  TEXT NOT NULL DEFAULT 'system',
  action TEXT NOT NULL,
  target TEXT NOT NULL DEFAULT '',
  summary TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS ix_audit_ts ON audit_log(ts);
CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);
"""
