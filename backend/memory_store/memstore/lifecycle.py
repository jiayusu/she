"""lifecycle.py — 巩固/遗忘/剪枝引擎(FR-M05 遗忘剪枝, FR-M06 再巩固)。

EMA 置信度衰减: 每次衰减步 salience' = salience * exp(-λ·Δ天), 与
route/config/salience.json 的 score·exp(-lambda·闲置天数) 数学等价, 但按增量步
推进(记录 last_decay), 跨天多次衰减可叠加。
低于 floor(默认 0.05)且不在白名单 → 剪除: 情景库热存储 → 冷存储(可再巩固恢复),
显著性缓冲条目直接出缓冲(其情景库副本仍在)。
白名单(refs + 情景库 whitelisted=1 行)物理隔离不参与剪枝, 3 年模拟零丢失。
"""
import math
import time

from .db import now


class Lifecycle:
    def __init__(self, db, episodic, salience, audit, metrics,
                 decay_lambda=0.05, floor=0.05,
                 boost_mult=1.5, boost_add=0.1):
        self.db = db
        self.episodic = episodic
        self.salience = salience
        self.audit = audit
        self.metrics = metrics
        self.decay_lambda = decay_lambda
        self.floor = floor
        self.boost_mult = boost_mult
        self.boost_add = boost_add

    # ------------------------------------------------------------ 衰减 + 剪枝(FR-M05)
    def decay_pass(self, ts: float | None = None, actor: str = "system:lifecycle") -> dict:
        ts = now() if ts is None else float(ts)
        pruned, demoted = [], []
        rows = self.db.q("SELECT id, salience, last_decay, whitelisted, utterance "
                         "FROM episodes ORDER BY id")
        scanned = len(rows)
        for r in rows:
            if r["whitelisted"]:
                continue  # 白名单物理隔离, 不参与剪枝
            new_sal = self._decay(r["salience"], r["last_decay"], ts)
            if new_sal < self.floor:
                self.episodic.move_to_cold(r["id"], reason="salience_decay",
                                           ts=ts)
                pruned.append({"episode_id": r["id"], "utterance": r["utterance"],
                               "salience": round(new_sal, 4)})
                self.audit.log(actor, "prune", f"episode:{r['id']}",
                               f"salience={new_sal:.4f}<floor={self.floor} → 冷存储")
            else:
                with self.db.tx() as conn:
                    conn.execute("UPDATE episodes SET salience=?, last_decay=? WHERE id=?",
                                 (new_sal, ts, r["id"]))
        for r in self.db.q("SELECT id, salience, last_decay, content "
                           "FROM salience_buffer ORDER BY id"):
            new_sal = self._decay(r["salience"], r["last_decay"], ts)
            if new_sal < self.floor:
                self.salience.remove(r["id"])  # 出缓冲, 情景库副本不清除
                demoted.append({"buffer_id": r["id"], "salience": round(new_sal, 4)})
                self.audit.log(actor, "prune_buffer", f"buffer:{r['id']}",
                               f"salience={new_sal:.4f}<floor 出缓冲")
            else:
                with self.db.tx() as conn:
                    conn.execute("UPDATE salience_buffer SET salience=?, last_decay=? "
                                 "WHERE id=?", (new_sal, ts, r["id"]))
        if pruned:
            self.metrics.prune(len(pruned))
            self.db.bump_version()
        return {"scanned_episodes": scanned, "pruned": pruned, "demoted": demoted,
                "ts": ts}

    def _decay(self, salience: float, last_decay: float, ts: float) -> float:
        idle_days = max(0.0, (ts - (last_decay or ts)) / 86400.0)
        return float(salience) * math.exp(-self.decay_lambda * idle_days)

    # ------------------------------------------------------------ 再巩固(FR-M06)
    def reconsolidate(self, cold_id: int, actor: str = "system:recall") -> dict | None:
        """已剪除记忆被重新提及 → 冷存储恢复并加权。"""
        row = self.episodic.restore_from_cold(cold_id, self.boost_mult, self.boost_add)
        if not row:
            return None
        self.audit.log(actor, "reconsolidate", f"episode:{cold_id}",
                       f"冷存储恢复, salience={row['salience']:.3f}")
        self.metrics.incr("reconsolidate_count")
        self.db.bump_version()
        return row
