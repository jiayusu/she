"""erase.py — 数据删除合规(非功能红线): 家长发起删除 → 五库 + KG 回流数据
72h 内物理清除, 并产出"微调数据集剔除清单"(风险表: 家长删除权 vs 已训练数据)。

执行即清除(远快于 72h 红线), deadline 仅作合规审计留痕; KG 侧删除走
/kg/edges:batch(del) 尽力推送, 失败则 job 置 partial 可重试。
审计日志自身保留(合规证明), 不在删除范围。
"""
import json
import time
from pathlib import Path

from .db import dump, now

DAY = 86400.0


class Erase:
    def __init__(self, db, audit, metrics, report_dir: Path, consolidator,
                 index_purger=None):
        self.db = db
        self.audit = audit
        self.metrics = metrics
        self.dir = Path(report_dir)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.consolidator = consolidator
        self.index_purger = index_purger  # (episode_ids, cold_ids) -> None 注入向量清理

    def request(self, child_id: str, requested_by: str = "parent",
                purge_all: bool = False) -> dict:
        t0 = time.perf_counter()
        ts = now()
        stats: dict[str, int] = {}
        manifest_rows: list[dict] = []

        where = "WHERE child_id=?" if not purge_all else ""
        args = () if purge_all else (child_id,)

        with self.db.tx() as conn:
            # 采集清单(微调数据集剔除)
            for r in conn.execute(
                    f"SELECT id, ts, day, chapter, scene, utterance, kind FROM episodes "
                    f"{where}", args).fetchall():
                manifest_rows.append({"type": "episode", **dict(r)})
            for r in conn.execute(
                    f"SELECT id, ts, day, scene, utterance, kind FROM episodes_cold "
                    f"{where}", args).fetchall():
                manifest_rows.append({"type": "episode_cold", **dict(r)})
            for r in conn.execute(
                    f"SELECT id, ref_id, content, salience, kind FROM salience_buffer "
                    f"{where}", args).fetchall():
                manifest_rows.append({"type": "salience", **dict(r)})
            for r in conn.execute(
                    f"SELECT id, ref_id, content, reason, source FROM whitelist "
                    f"{where}", args).fetchall():
                manifest_rows.append({"type": "whitelist", **dict(r)})
            for r in conn.execute(
                    f"SELECT id, name, trigger, action FROM procedural {where}",
                    args).fetchall():
                manifest_rows.append({"type": "procedural", **dict(r)})
            for r in conn.execute(
                    f"SELECT id, session_id, role, text FROM working_turns {where}",
                    args).fetchall():
                manifest_rows.append({"type": "working_turn", **dict(r)})
            # 回流台账(KG 侧待删边)
            ledger_edges: list[dict] = []
            for r in conn.execute(
                    f"SELECT id, edges, episode_ids FROM consolidation_ledger {where}",
                    args).fetchall():
                for e in json.loads(r["edges"] or "[]"):
                    ledger_edges.append(e)
                manifest_rows.append({"type": "consolidation_ledger", **dict(r)})

            stats["episodes"] = conn.execute(f"DELETE FROM episodes {where}",
                                             args).rowcount
            stats["episodes_cold"] = conn.execute(
                f"DELETE FROM episodes_cold {where}", args).rowcount
            stats["salience_buffer"] = conn.execute(
                f"DELETE FROM salience_buffer {where}", args).rowcount
            stats["whitelist"] = conn.execute(f"DELETE FROM whitelist {where}",
                                              args).rowcount
            stats["procedural"] = conn.execute(f"DELETE FROM procedural {where}",
                                               args).rowcount
            stats["working_turns"] = conn.execute(f"DELETE FROM working_turns {where}",
                                                  args).rowcount
            stats["sessions"] = conn.execute(f"DELETE FROM sessions {where}",
                                             args).rowcount
            stats["ledger"] = conn.execute(
                f"DELETE FROM consolidation_ledger {where}", args).rowcount

        # 向量索引清理
        ep_ids = [m["id"] for m in manifest_rows if m["type"] == "episode"]
        cold_ids = [m["id"] for m in manifest_rows if m["type"] == "episode_cold"]
        if self.index_purger:
            self.index_purger(ep_ids, cold_ids)

        # KG 侧: 该孩子巩固出的边尽力删除(失败 → partial, 可重试)
        kg_error = None
        if ledger_edges:
            resp, err = self.consolidator.post(
                "/kg/edges:batch",
                {"edges": [{**e, "op": "del"} for e in ledger_edges],
                 "source": "erase"})
            kg_error = err

        deadline = ts + 72 * 3600  # 72h 合规红线(实际即时清除, 红线留痕)
        job_id = f"erase_{int(ts)}"
        manifest_path = self.dir / f"{job_id}.jsonl"
        with open(manifest_path, "w", encoding="utf-8") as f:
            for row in manifest_rows:
                row_out = {**row, "erase_job": job_id, "child_id": child_id,
                           "requested_by": requested_by, "deadline_ts": deadline,
                           "purpose": "fine_tune_dataset_removal"}
                f.write(json.dumps(row_out, ensure_ascii=False) + "\n")

        status = "partial" if kg_error else "completed"
        result = {"job_id": job_id, "child_id": child_id, "status": status,
                  "manifest": str(manifest_path), "manifest_rows": len(manifest_rows),
                  "kg_error": kg_error, "stats": stats, "deadline_ts": deadline,
                  "duration_ms": round((time.perf_counter() - t0) * 1000, 1)}
        with self.db.tx() as conn:
            conn.execute(
                "INSERT INTO erase_jobs(child_id, requested_by, deadline_ts, status, "
                "stats, manifest_path) VALUES(?,?,?,?,?,?)",
                (child_id, requested_by, deadline, status, dump(stats),
                 str(manifest_path)))
        self.audit.log(requested_by, "erase", child_id,
                       f"{status} rows={sum(stats.values())} "
                       f"manifest={len(manifest_rows)}")
        self.db.bump_version()
        return result

    def jobs(self) -> list[dict]:
        return [dict(r) for r in self.db.q(
            "SELECT * FROM erase_jobs ORDER BY id DESC")]
