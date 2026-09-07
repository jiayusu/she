"""salience.py — 库4 显著性缓冲: 容量 1000(FR-M01),
满则最低分降入情景库且不清除(FR-M09); 白名单物理隔离只增不删(FR-G05)。"""
import time

from .db import now


class SalienceBuffer:
    def __init__(self, db, cap: int = 1000):
        self.db = db
        self.cap = cap

    # ------------------------------------------------------------ 写入
    def add(self, content: str, salience: float, ref_id: str = "",
            episode_id: int | None = None, kind: str = "dialogue",
            child_id: str = "default", source: str = "agent",
            ts: float | None = None) -> dict:
        ts = now() if ts is None else float(ts)
        evicted = None
        with self.db.tx() as conn:
            while conn.execute("SELECT COUNT(*) c FROM salience_buffer").fetchone()["c"] \
                    >= self.cap:
                evicted = self._demote_lowest(conn)
            conn.execute(
                "INSERT INTO salience_buffer(ref_id, episode_id, content, salience, kind, "
                "child_id, source, last_touch, last_decay) VALUES(?,?,?,?,?,?,?,?,?)",
                (ref_id, episode_id, content, float(salience), kind, child_id, source,
                 ts, ts))
            rid = conn.execute("SELECT last_insert_rowid() r").fetchone()["r"]
        return {"id": rid, "evicted": evicted}

    def _demote_lowest(self, conn) -> dict | None:
        """缓冲满: 最低分降入情景库(不清除), 从缓冲移除。"""
        row = conn.execute("SELECT * FROM salience_buffer ORDER BY salience ASC, "
                           "last_touch ASC LIMIT 1").fetchone()
        if not row:
            return None
        if row["episode_id"] is None:
            # 独立条目 → 落情景库, 记忆不丢
            conn.execute(
                "INSERT INTO episodes(ts, day, chapter, session_id, child_id, scene, "
                "utterance, salience, last_decay, kind) VALUES(?,?,?,?,?,?,?,?,?,?)",
                (row["last_touch"] or now(),
                 time.strftime("%Y-%m-%d", time.localtime(row["last_touch"] or now())),
                 1, "", row["child_id"], "salience-demoted", row["content"],
                 row["salience"], row["last_decay"] or now(), "demoted"))
            new_id = conn.execute("SELECT last_insert_rowid() r").fetchone()["r"]
        else:
            new_id = row["episode_id"]  # 已在情景库, 仅出缓冲
        conn.execute("DELETE FROM salience_buffer WHERE id=?", (row["id"],))
        return {"buffer_id": row["id"], "ref_id": row["ref_id"],
                "salience": row["salience"], "episode_id": new_id}

    # ------------------------------------------------------------ 查询
    def items(self, child_id: str | None = None, limit: int = 50) -> list[dict]:
        sql = "SELECT * FROM salience_buffer"
        args = []
        if child_id:
            sql += " WHERE child_id=?"
            args.append(child_id)
        sql += " ORDER BY salience DESC LIMIT ?"
        args.append(int(limit))
        return [dict(r) for r in self.db.q(sql, args)]

    def touch(self, buf_id: int, ts: float | None = None):
        ts = now() if ts is None else ts
        with self.db.tx() as conn:
            conn.execute("UPDATE salience_buffer SET last_touch=? WHERE id=?",
                         (ts, buf_id))

    def count(self) -> int:
        return self.db.q1("SELECT COUNT(*) c FROM salience_buffer")["c"]

    def remove(self, buf_id: int):
        with self.db.tx() as conn:
            conn.execute("DELETE FROM salience_buffer WHERE id=?", (buf_id,))

    # ------------------------------------------------------------ 白名单(只增不删)
    def whitelist_add(self, ref_id: str, reason: str, content: str = "",
                      salience: float = 1.0, source: str = "auto",
                      child_id: str = "default", episode_id: int | None = None) -> dict:
        with self.db.tx() as conn:
            conn.execute(
                "INSERT INTO whitelist(ref_id, content, reason, salience, source, "
                "child_id, episode_id) VALUES(?,?,?,?,?,?,?) "
                "ON CONFLICT(ref_id) DO NOTHING",
                (ref_id, content, reason, float(salience), source, child_id, episode_id))
            row = conn.execute("SELECT * FROM whitelist WHERE ref_id=?",
                               (ref_id,)).fetchone()
        return dict(row)

    def whitelist_has(self, ref_id: str) -> bool:
        return self.db.q1("SELECT 1 FROM whitelist WHERE ref_id=?", (ref_id,)) is not None

    def whitelist_items(self, child_id: str | None = None) -> list[dict]:
        sql = "SELECT * FROM whitelist"
        args = []
        if child_id:
            sql += " WHERE child_id=?"
            args.append(child_id)
        sql += " ORDER BY id"
        return [dict(r) for r in self.db.q(sql, args)]
