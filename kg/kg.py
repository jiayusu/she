#!/usr/bin/env python3
"""kg.py — 知识库公共库: 建表/查询/万物模式 facts()/next_words()/GraphML/版本管理。

被 build_kg.py / kg_query.py / kg_embed.py / server.py 复用。
kg.db 为 SQLite(WAL), 支持热更新期间读不阻塞。
"""
import json
import sqlite3
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"

SCHEMA = """
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS words(
  word   TEXT PRIMARY KEY,
  level  TEXT NOT NULL,          -- starters/movers/flyers/a1/a2
  pos    TEXT NOT NULL,
  source TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS concepts(           -- 词表外的图概念节点(如 fruit/kitchen)
  word   TEXT PRIMARY KEY,
  source TEXT NOT NULL DEFAULT 'conceptnet'
);
CREATE TABLE IF NOT EXISTS edges(
  id             INTEGER PRIMARY KEY AUTOINCREMENT,
  head           TEXT NOT NULL,
  rel            TEXT NOT NULL,
  tail           TEXT NOT NULL,
  weight         REAL NOT NULL DEFAULT 1.0,
  source         TEXT NOT NULL DEFAULT 'conceptnet',  -- conceptnet/manual/consolidated
  status         TEXT NOT NULL DEFAULT 'active',      -- active/removed
  version_added  INTEGER NOT NULL DEFAULT 1,
  version_removed INTEGER,
  removed_by     TEXT,                                -- rule/llm/human/rollback
  reason         TEXT,
  created_at     TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_edge ON edges(head, rel, tail);
CREATE INDEX IF NOT EXISTS ix_head ON edges(head) WHERE status='active';
CREATE INDEX IF NOT EXISTS ix_tail ON edges(tail) WHERE status='active';
CREATE INDEX IF NOT EXISTS ix_ver ON edges(version_added);
CREATE TABLE IF NOT EXISTS conflicts(
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  head TEXT NOT NULL, rel TEXT NOT NULL, tail TEXT NOT NULL,
  kind   TEXT NOT NULL,        -- duplicate/previously_removed/contradiction/blocked
  detail TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL DEFAULT 'open',                -- open/resolved
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS snapshots(
  version INTEGER PRIMARY KEY,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  path TEXT NOT NULL,
  note TEXT NOT NULL DEFAULT '',
  edge_count INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS audit_log(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts TEXT NOT NULL DEFAULT (datetime('now')),
  action TEXT NOT NULL,
  detail TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);
"""

LEVEL_TO_PACK = {"starters": "L0", "movers": "L1", "flyers": "L2",
                 "a1": "L1", "a2": "L2", "b1": "L3", "b2": "L4", "c1": "L5", "c2": "L5"}


def connect(db_path, timeout=30.0):
    # check_same_thread=False: Flask 线程池跨线程复用连接(WAL + 写锁保证一致性)
    conn = sqlite3.connect(str(db_path), timeout=timeout, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db(conn):
    conn.executescript(SCHEMA)
    conn.commit()


def get_meta(conn, key, default=None):
    row = conn.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
    return row["value"] if row else default


def set_meta(conn, key, value):
    conn.execute("INSERT INTO meta(key,value) VALUES(?,?) "
                 "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, str(value)))


def get_version(conn) -> int:
    return int(get_meta(conn, "kg_version", "1"))


def bump_version(conn) -> int:
    v = get_version(conn) + 1
    set_meta(conn, "kg_version", v)
    return v


def log_audit(conn, action, detail=""):
    conn.execute("INSERT INTO audit_log(action, detail) VALUES(?,?)", (action, detail))


# ---------------------------------------------------------------- 万物模式 MVP
def facts(conn, word: str, limit: int = 50) -> list:
    """本地优先: 返回该词的知识边(head,rel,tail,weight,source)。"""
    # UNION ALL 让两侧分别命中 ix_head/ix_tail 部分索引(OR 写法会退化为全表扫描)
    rows = conn.execute(
        "SELECT head, rel, tail, weight, source FROM ("
        "  SELECT head, rel, tail, weight, source, id FROM edges"
        "   WHERE status='active' AND head=?"
        "  UNION ALL"
        "  SELECT head, rel, tail, weight, source, id FROM edges"
        "   WHERE status='active' AND tail=?"
        ") ORDER BY weight DESC, id LIMIT ?", (word, word, limit)).fetchall()
    return [dict(r) for r in rows]


def query_conceptnet(word: str, limit: int = 50, timeout: float = 3.0) -> list:
    """在线兜底(仅 KG_ONLINE_FALLBACK=1 时由 server 调用): ConceptNet API 查询。"""
    import requests
    url = f"https://api.conceptnet.io/query?node=/c/en/{word}&other=/c/en"
    out = []
    r = requests.get(url, timeout=timeout)
    r.raise_for_status()
    for e in r.json().get("edges", [])[:limit]:
        start = e.get("start", {}).get("label", "")
        end = e.get("end", {}).get("label", "")
        out.append({"head": start.lower(), "rel": e.get("rel", {}).get("label", ""),
                    "tail": end.lower(), "weight": e.get("weight", 1.0),
                    "source": "conceptnet-online"})
    return out


def next_words(conn, word: str, n: int = 8) -> list:
    """规则版课程推荐: 从该词的邻接词里挑"下一个该学的词"。

    打分 = 边权重 + 级别衔接(优先同级别/下一级别) + 邻词的出边丰富度。
    W3 中当图谱过小(<5000 节点)导致向量不可靠时, 退回本函数。
    """
    rows = conn.execute(
        "SELECT other, rel, weight FROM ("
        "  SELECT tail AS other, rel, weight FROM edges WHERE status='active' AND head=:w"
        "  UNION ALL"
        "  SELECT head AS other, rel, weight FROM edges WHERE status='active' AND tail=:w"
        ")", {"w": word}).fetchall()
    if not rows:
        return []
    level = conn.execute("SELECT level FROM words WHERE word=?", (word,)).fetchone()
    level = level["level"] if level else "starters"
    # 先取所有邻词的级别与出边数, 避免 N+1 查询
    others = {r["other"] for r in rows}
    marks = {}
    for chunk_start in range(0, len(others), 500):
        chunk = list(others)[chunk_start:chunk_start + 500]
        q = ",".join("?" * len(chunk))
        for r in conn.execute(f"SELECT word, level FROM words WHERE word IN ({q})", chunk):
            marks[r["word"]] = r["level"]
    deg = {}
    for r in conn.execute(
            "SELECT node, COUNT(*) AS d FROM ("
            " SELECT head AS node FROM edges WHERE status='active'"
            " UNION ALL SELECT tail FROM edges WHERE status='active') "
            "GROUP BY node"):
        deg[r["node"]] = r["d"]
    rank = {}
    for r in rows:
        o = r["other"]
        rank.setdefault(o, 0.0)
        rank[o] += float(r["weight"] or 1.0)
    out = []
    for o, s in rank.items():
        lv = marks.get(o)
        bonus = 1.0
        if lv:
            gap = abs(list(LEVEL_TO_PACK).index(lv) - list(LEVEL_TO_PACK).index(level)) \
                if lv in LEVEL_TO_PACK and level in LEVEL_TO_PACK else 2
            bonus = 2.0 - 0.4 * min(gap, 4)          # 级别越近加分越多
            bonus += 0.5 if lv in ("starters", "movers", "flyers") else 0.0
        out.append({"word": o, "score": round(s * bonus + 0.001 * deg.get(o, 0), 4),
                    "level": lv or "concept"})
    out.sort(key=lambda x: -x["score"])
    return out[:n]


# ---------------------------------------------------------------- 导出与统计
def export_graphml(conn, path):
    """导出 kg.graphml(Gephi 目视质检用: apple 应与 fruit 同簇)。"""
    import networkx as nx
    g = nx.DiGraph()
    for r in conn.execute("SELECT word, level, pos FROM words"):
        g.add_node(r["word"], kind="word", level=r["level"], pos=r["pos"])
    for r in conn.execute("SELECT word FROM concepts"):
        g.add_node(r["word"], kind="concept", level="", pos="")
    for r in conn.execute("SELECT head, rel, tail, weight FROM edges WHERE status='active'"):
        g.add_edge(r["head"], r["tail"], rel=r["rel"], weight=r["weight"])
    nx.write_graphml(g, str(path), named_key_ids=True)
    return g.number_of_nodes(), g.number_of_edges()


def coverage(conn, min_edges: int = 2):
    """每词知识边数统计与覆盖不足清单。"""
    counts = {}
    for r in conn.execute(
            "SELECT w.word AS word, ("
            " (SELECT COUNT(*) FROM edges e WHERE e.status='active' AND e.head=w.word)"
            "+(SELECT COUNT(*) FROM edges e WHERE e.status='active' AND e.tail=w.word)"
            ") AS n FROM words w"):
        counts[r["word"]] = r["n"]
    low = {w: c for w, c in counts.items() if c < min_edges}
    return counts, low


def db_stats(conn):
    return {
        "version": get_version(conn),
        "words": conn.execute("SELECT COUNT(*) c FROM words").fetchone()["c"],
        "concepts": conn.execute("SELECT COUNT(*) c FROM concepts").fetchone()["c"],
        "edges_active": conn.execute(
            "SELECT COUNT(*) c FROM edges WHERE status='active'").fetchone()["c"],
        "edges_total": conn.execute("SELECT COUNT(*) c FROM edges").fetchone()["c"],
        "conflicts_open": conn.execute(
            "SELECT COUNT(*) c FROM conflicts WHERE status='open'").fetchone()["c"],
        "snapshots": conn.execute("SELECT COUNT(*) c FROM snapshots").fetchone()["c"],
    }


def json_dumps(obj):
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


class Timer:
    def __enter__(self):
        self.t0 = time.perf_counter()
        return self

    def __exit__(self, *a):
        self.ms = (time.perf_counter() - self.t0) * 1000
