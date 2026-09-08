#!/usr/bin/env python3
"""db.py — SQLite 存储层。

表:
  candidates   候选条目 (FR-I01/02/03 结构化结果, 永久存档)
  review_log   审核留痕 (FR-I04, 修改 before/after 全记录)
  sentiment    舆情条目 (FR-I06)
  reports      周报 (FR-I05)
  quota_ledger 本地调用台账 (FR-I07, 按天×用途计数)
  jobs         降级补跑队列 (FR-I07 超额隔日补跑)
  alerts       告警去重 (§5 单用途失败不影响其他用途, 每用途每天最多1条)
  metrics      埋点事件流 (§9)
  meta         调度水位 (scheduler 上次运行等)

合规 (§5): 结构化表只存 标题+摘要摘录(≤200字)+链接, 不存原文全文;
原文 JSON 只进 data/raw/ 归档, 保留 90 天 (FR-I08)。
"""
import sqlite3
import time
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS candidates (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  batch_id TEXT NOT NULL,
  content_id TEXT NOT NULL UNIQUE,
  content_type TEXT,
  title TEXT NOT NULL,
  url TEXT,
  excerpt TEXT,                -- ContentText 前 200 字摘录(不转载全文)
  vote_up INTEGER DEFAULT 0,
  comment_count INTEGER DEFAULT 0,
  authority TEXT DEFAULT '',
  score REAL DEFAULT 0,        -- FR-I02 排序分
  merged_into INTEGER,         -- 去重时被并入的主条目 id
  week TEXT,                   -- ISO 周 e.g. 2026-W36
  status TEXT DEFAULT 'pending_struct',
        -- pending_struct → structured | llm_failed | filtered
        -- structured → approved | discarded
        -- approved → kg_pushed | kg_pending
  raw_path TEXT,               -- 原始 JSON 归档路径 (90 天保留)
  phenomenon TEXT,
  child_question TEXT,
  fact TEXT,
  difficulty INTEGER,
  related_objects TEXT,        -- JSON ["...", ...]
  kg_edges TEXT,               -- JSON [{head,rel,tail,weight}]
  structure_model TEXT,
  prompt_version TEXT,
  created_at TEXT,
  updated_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_cand_status ON candidates(status, week);
CREATE INDEX IF NOT EXISTS idx_cand_batch ON candidates(batch_id);

CREATE TABLE IF NOT EXISTS review_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  candidate_id INTEGER NOT NULL,
  action TEXT NOT NULL,        -- approve | modify | discard | kg_push | kg_retry | edit
  reviewer TEXT DEFAULT '',
  before_json TEXT,
  after_json TEXT,
  note TEXT,
  kg_result TEXT,              -- KG /kg/edges:batch 响应摘要
  created_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_review_cand ON review_log(candidate_id);

CREATE TABLE IF NOT EXISTS sentiment (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  watchword TEXT NOT NULL,
  watchword_kind TEXT NOT NULL,  -- brand | competitor | category
  content_id TEXT NOT NULL UNIQUE,
  title TEXT,
  url TEXT,
  excerpt TEXT,
  vote_up INTEGER DEFAULT 0,
  comment_count INTEGER DEFAULT 0,
  edit_time INTEGER,
  sentiment TEXT DEFAULT 'unknown',  -- negative | neutral | positive | unknown
  issue_tag TEXT DEFAULT '',
  confidence REAL DEFAULT 0,
  pushed INTEGER DEFAULT 0,
  raw_path TEXT,
  created_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_sent_sentiment ON sentiment(sentiment, created_at);

CREATE TABLE IF NOT EXISTS reports (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  week TEXT NOT NULL,
  kind TEXT DEFAULT 'radar',
  payload TEXT,                -- 结构化周报 JSON (TOP5 焦虑 + 新兴方法论词)
  markdown TEXT,
  status TEXT DEFAULT 'pending',  -- pending | sent | failed
  sent_at TEXT,
  sample_count INTEGER DEFAULT 0,
  created_at TEXT
);

CREATE TABLE IF NOT EXISTS quota_ledger (
  day TEXT NOT NULL,           -- YYYY-MM-DD 本地日期
  purpose TEXT NOT NULL,       -- question_pool | sentiment | radar
  n INTEGER DEFAULT 0,
  PRIMARY KEY (day, purpose)
);

CREATE TABLE IF NOT EXISTS jobs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  kind TEXT NOT NULL,          -- question_pool | sentiment | radar
  payload TEXT,                -- JSON 参数, 隔日补跑用
  run_after TEXT,              -- YYYY-MM-DD 到期日
  reason TEXT,
  status TEXT DEFAULT 'pending',  -- pending | done
  created_at TEXT
);

CREATE TABLE IF NOT EXISTS alerts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  day TEXT NOT NULL,
  purpose TEXT NOT NULL,
  level TEXT DEFAULT 'warn',
  message TEXT,
  dedup TEXT,                  -- 去重键: 每用途每天同类告警最多1条
  created_at TEXT,
  UNIQUE(day, purpose, dedup)
);

CREATE TABLE IF NOT EXISTS metrics (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts TEXT,
  event TEXT NOT NULL,         -- §9: intel_fetched / intel_structured / intel_approved
                               --      intel_report_sent / intel_quota_used
  purpose TEXT DEFAULT '',
  value REAL DEFAULT 1,
  detail TEXT DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_metrics_event ON metrics(event, ts);

CREATE TABLE IF NOT EXISTS meta (
  key TEXT PRIMARY KEY,
  value TEXT
);
"""


def connect(db_path=None):
    import config
    p = Path(db_path) if db_path else config.DB_PATH
    p.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(p, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(SCHEMA)
    return conn


def now():
    return time.strftime("%Y-%m-%d %H:%M:%S")


def today():
    return time.strftime("%Y-%m-%d")


def iso_week(day=None):
    """ISO 周, e.g. 2026-W36 (strftime %G/%V)。"""
    t = time.strptime(day, "%Y-%m-%d") if day else time.localtime()
    return time.strftime("%G-W%V", t)


def metric(conn, event, purpose="", value=1, detail=""):
    """埋点 (§9)。未知事件直接忽略, 防止调用方拼错名字污染数据。自带提交。"""
    import config
    if event not in config.METRIC_EVENTS:
        return
    with conn:
        conn.execute("INSERT INTO metrics(ts, event, purpose, value, detail) VALUES(?,?,?,?,?)",
                     (now(), event, purpose, value, str(detail)[:500]))


def get_meta(conn, key, default=""):
    row = conn.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
    return row["value"] if row else default


def set_meta(conn, key, value):
    with conn:
        conn.execute("INSERT INTO meta(key, value) VALUES(?,?) "
                     "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, str(value)))
