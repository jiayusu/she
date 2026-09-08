"""episodic.py — 库2 情景库: SQLite + 向量索引(FR-M02), StoryArc 时间线(FR-M03),
冷存储物理分表与再巩固恢复(FR-M06), 索引重建(FAISS 损坏对策)。

向量 id: 热存储 = episode rowid, 冷存储 = -rowid(负数空间), 单索引双区检索。
"""
import time

import numpy as np

from .db import local_day, now
from .vector import HashingEmbedder, VectorIndex

EP_COLS = ("id, ts, day, chapter, arc_id, session_id, child_id, scene, utterance, "
           "assess, emotion, emotion_v, salience, last_decay, role, kind, "
           "whitelisted, reconsolidated, created_at")


class EpisodicStore:
    def __init__(self, db, embedder: HashingEmbedder, index: VectorIndex):
        self.db = db
        self.emb = embedder
        self.index = index

    # ------------------------------------------------------------ 写入(FR-M02)
    def add(self, *, ts=None, scene="", utterance, assess=None, emotion="",
            emotion_v=None, salience=0.3, session_id="", child_id="default",
            day=None, chapter=None, arc_id="", role="child", kind="dialogue",
            whitelisted=0, last_decay=None) -> dict:
        ts = now() if ts is None else float(ts)
        day = day or local_day(ts)
        if chapter is None:
            row = self.db.q1("SELECT chapter FROM sessions WHERE session_id=?",
                             (session_id,)) if session_id else None
            chapter = (row["chapter"] if row else 1)
        last_decay = ts if last_decay is None else float(last_decay)
        with self.db.tx() as conn:
            cur = conn.execute(
                "INSERT INTO episodes(ts, day, chapter, arc_id, session_id, child_id, "
                "scene, utterance, assess, emotion, emotion_v, salience, last_decay, "
                "role, kind, whitelisted) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (ts, day, int(chapter), arc_id, session_id, child_id, scene,
                 utterance, assess, emotion, emotion_v, float(salience),
                 float(last_decay), role, kind, int(whitelisted)))
            eid = cur.lastrowid
            row = conn.execute(f"SELECT {EP_COLS} FROM episodes WHERE id=?", (eid,)).fetchone()
        with self.db.lock:  # 索引与库同锁, Flask 多线程下保持一致
            self.index.add([eid], self.emb.embed(utterance).reshape(1, -1))
        return dict(row)

    # ------------------------------------------------------------ 查询
    def get(self, eid: int):
        return self.db.q1(f"SELECT {EP_COLS} FROM episodes WHERE id=?", (eid,))

    def latest(self, session_id: str | None = None, child_id: str | None = None,
               limit: int = 10) -> list[dict]:
        sql, args = f"SELECT {EP_COLS} FROM episodes WHERE 1=1", []
        if session_id:
            sql += " AND session_id=?"
            args.append(session_id)
        if child_id:
            sql += " AND child_id=?"
            args.append(child_id)
        sql += " ORDER BY ts DESC LIMIT ?"
        args.append(int(limit))
        return [dict(r) for r in self.db.q(sql, args)]

    def first_in_window(self, text: str, day_from=None, day_to=None,
                        chapter=None) -> dict | None:
        """"第一次 X": 窗口内按 ts 升序第一条含 X 的记忆。"""
        sql, args = f"SELECT {EP_COLS} FROM episodes WHERE 1=1", []
        if day_from:
            sql += " AND day>=?"
            args.append(day_from)
        if day_to:
            sql += " AND day<=?"
            args.append(day_to)
        if chapter is not None:
            sql += " AND chapter=?"
            args.append(chapter)
        if text:
            sql += " AND (utterance LIKE ? OR scene LIKE ?)"
            args.extend([f"%{text}%", f"%{text}%"])
        sql += " ORDER BY ts ASC LIMIT 1"
        return self.db.q1(sql, args)

    def search(self, query_vec: np.ndarray, k: int = 5, day_from=None, day_to=None,
               chapter=None, text=None, include_cold=False) -> tuple[list[dict], list[dict]]:
        """向量近邻 + 时间线硬过滤(FR-M03) + 关键词软排序。返回 (active_hits, cold_hits)。"""
        n_probe = max(k * 8, 32)
        with self.db.lock:
            raw = self.index.search(query_vec, n_probe)
        active, cold = [], []
        for eid, score in raw:
            if eid > 0:
                row = self.get(eid)
                if row:
                    active.append((dict(row), score))
            elif include_cold:
                row = self.get_cold(-eid)
                if row:
                    cold.append((dict(row), score))
        active = self._filter_window(active, day_from, day_to, chapter)
        cold = self._filter_window(cold, day_from, day_to, chapter)
        if text:  # 关键词软排序(命中者前置) + LIKE 兜底补齐
            active = self._keyword_boost(active, text)
            cold = self._keyword_boost(cold, text)
            if len(active) < k:
                active = self._keyword_fill(active, k, day_from, day_to, chapter, text)
            if include_cold and len(cold) < k:
                cold = self._keyword_fill(cold, k, day_from, day_to, chapter, text,
                                          cold_table=True)
            active = self._keyword_boost(active, text)
            cold = self._keyword_boost(cold, text)
        return active[:k], cold[:k]

    @staticmethod
    def _keyword_boost(pairs, text):
        def hit(pair):
            row = pair[0]
            return 0 if (text in (row["utterance"] or "")
                         or text in (row["scene"] or "")) else 1
        return sorted(pairs, key=hit)

    @staticmethod
    def _filter_window(pairs, day_from, day_to, chapter):
        out = []
        for row, score in pairs:
            if day_from and row["day"] < day_from:
                continue
            if day_to and row["day"] > day_to:
                continue
            if chapter is not None and row["chapter"] != chapter:
                continue
            out.append((row, score))
        return out

    def _keyword_fill(self, have, k, day_from, day_to, chapter, text,
                      cold_table=False):
        table = "episodes_cold" if cold_table else "episodes"
        seen = {r["id"] for r, _ in have}
        sql, args = f"SELECT {EP_COLS} FROM {table} WHERE 1=1", []
        if day_from:
            sql += " AND day>=?"
            args.append(day_from)
        if day_to:
            sql += " AND day<=?"
            args.append(day_to)
        if chapter is not None:
            sql += " AND chapter=?"
            args.append(chapter)
        sql += " AND (utterance LIKE ? OR scene LIKE ?) ORDER BY ts DESC LIMIT ?"
        args.extend([f"%{text}%", f"%{text}%", k])
        filled = list(have)
        for r in self.db.q(sql, args):
            if r["id"] not in seen:
                filled.append((dict(r), 0.0))
        return filled

    # ------------------------------------------------------------ 冷存储(FR-M05/M06)
    def get_cold(self, cid: int):
        row = self.db.q1(f"SELECT id, ts, day, chapter, arc_id, session_id, child_id, "
                         f"scene, utterance, assess, emotion, emotion_v, salience, "
                         f"role, kind, whitelisted, reconsolidated, created_at, "
                         f"pruned_at, prune_reason FROM episodes_cold WHERE id=?", (cid,))
        return row

    def move_to_cold(self, eid: int, reason: str, ts: float | None = None) -> bool:
        """剪除: 热存储 → 冷存储物理搬移 + 向量移除。"""
        row = self.get(eid)
        if not row:
            return False
        ts = now() if ts is None else ts
        with self.db.tx() as conn:
            conn.execute(
                "INSERT INTO episodes_cold(id, pruned_at, prune_reason, ts, day, chapter, "
                "arc_id, session_id, child_id, scene, utterance, assess, emotion, "
                "emotion_v, salience, last_decay, role, kind, whitelisted, "
                "reconsolidated, created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (eid, ts, reason, row["ts"], row["day"], row["chapter"], row["arc_id"],
                 row["session_id"], row["child_id"], row["scene"], row["utterance"],
                 row["assess"], row["emotion"], row["emotion_v"], row["salience"],
                 row["last_decay"], row["role"], row["kind"], row["whitelisted"],
                 row["reconsolidated"], row["created_at"]))
            conn.execute("DELETE FROM episodes WHERE id=?", (eid,))
        with self.db.lock:
            self.index.remove([eid])
            self.index.add([-eid], self.emb.embed(row["utterance"]).reshape(1, -1))
        return True

    def restore_from_cold(self, cid: int, boost_mult: float, boost_add: float) -> dict | None:
        """再巩固(FR-M06): 冷存储 → 热存储, 恢复并加权。"""
        row = self.get_cold(cid)
        if not row:
            return None
        new_sal = min(1.0, row["salience"] * boost_mult + boost_add)
        with self.db.tx() as conn:
            conn.execute(
                "INSERT INTO episodes(id, ts, day, chapter, arc_id, session_id, child_id, "
                "scene, utterance, assess, emotion, emotion_v, salience, last_decay, role, "
                "kind, whitelisted, reconsolidated) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (cid, row["ts"], row["day"], row["chapter"], row["arc_id"],
                 row["session_id"], row["child_id"], row["scene"], row["utterance"],
                 row["assess"], row["emotion"], row["emotion_v"], new_sal,
                 time.time(), row["role"], row["kind"], row["whitelisted"],
                 row["reconsolidated"] + 1))
            conn.execute("DELETE FROM episodes_cold WHERE id=?", (cid,))
        with self.db.lock:
            self.index.add([cid], self.emb.embed(row["utterance"]).reshape(1, -1))
        return self.get(cid)

    def cold_rows(self, child_id: str | None = None) -> list[dict]:
        sql = "SELECT id, utterance, scene, ts, child_id FROM episodes_cold"
        args = []
        if child_id:
            sql += " WHERE child_id=?"
            args.append(child_id)
        return [dict(r) for r in self.db.q(sql, args)]

    # ------------------------------------------------------------ 重建/统计
    def rebuild_index(self) -> int:
        """SQLite 原始数据重建向量索引(FAISS 损坏对策, 全量重嵌入)。"""
        with self.db.lock:
            index = VectorIndex(self.emb.dim,
                                use_faiss=self.index.backend == "faiss")
            n = 0
            for sign, table in ((1, "episodes"), (-1, "episodes_cold")):
                for r in self.db.q(f"SELECT id, utterance FROM {table}"):
                    index.add([sign * r["id"]],
                              self.emb.embed(r["utterance"]).reshape(1, -1))
                    n += 1
            self.index = index
        return n

    def counts(self) -> dict:
        a = self.db.q1("SELECT COUNT(*) c FROM episodes")["c"]
        c = self.db.q1("SELECT COUNT(*) c FROM episodes_cold")["c"]
        return {"active": a, "cold": c, "indexed": len(self.index)}

    def all_rows(self, child_id: str | None = None) -> list[dict]:
        sql = f"SELECT {EP_COLS} FROM episodes"
        args = []
        if child_id:
            sql += " WHERE child_id=?"
            args.append(child_id)
        return [dict(r) for r in self.db.q(sql, args)]
