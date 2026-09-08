"""consolidate.py — 巩固管线(FR-M04): 接收 Agent 调度的巩固批次, 走 KG 热更新接口。

链路: 发音评估闸门(assess ≥ 阈值, 防"孩子说错的词被固化") →
      KG /kg/runtime-consolidate(共现词对) 或 /kg/edges:batch(显式边) →
      版本+1 / 冲突边镜像进待审队列 / 回流台账(删除合规依据)。
KG 不可达 → 批次落 outbox(consolidation_jobs), flush 重推, 写失败不丢批。
"""
import requests

from .db import dump, load, now


def memories2ids(memories) -> list[int]:
    ids = []
    for m in memories:
        ids.extend(m.get("episode_ids") or [])
    return ids


def edges2keys(edges) -> list[dict]:
    return [{"head": e.get("head"), "rel": e.get("rel"), "tail": e.get("tail")}
            for e in edges]


class Consolidator:
    def __init__(self, db, audit, metrics, kg_url: str,
                 min_assess: float = 80.0, timeout: float = 10.0):
        self.db = db
        self.audit = audit
        self.metrics = metrics
        self.kg_url = kg_url.rstrip("/")
        self.min_assess = min_assess
        self.timeout = timeout

    # ------------------------------------------------------------ 批次入口
    def run(self, batch: dict, actor: str = "agent") -> dict:
        """batch: {memories:[{scene,words,assess,episode_ids?}],
                   edges:[{head,rel,tail,weight?,assess}],
                   threshold?}"""
        memories = batch.get("memories") or []
        edges = batch.get("edges") or []
        threshold = int(batch.get("threshold", 3))
        child_id = str(batch.get("child_id", "default"))
        rejected = []

        gated_mem, gated_edges = [], []
        for m in memories:
            assess = m.get("assess")
            if assess is not None and float(assess) < self.min_assess:
                rejected.append({"item": m, "reason": "assess_below_gate",
                                 "detail": f"assess={assess} < {self.min_assess}"})
                continue
            gated_mem.append(m)
        for e in edges:
            assess = e.get("assess")
            if assess is not None and float(assess) < self.min_assess:
                rejected.append({"item": e, "reason": "assess_below_gate",
                                 "detail": f"assess={assess} < {self.min_assess}"})
                continue
            gated_edges.append(e)

        results = {"promoted": 0, "kg_versions": [], "conflicts": [], "rejected": rejected,
                   "queued": False, "jobs": []}

        if gated_mem:
            self._send_memories(gated_mem, threshold, child_id, actor, results)
        if gated_edges:
            self._send_edges(gated_edges, child_id, actor, results)

        if results["queued"]:
            self.audit.log(actor, "consolidate_queued", child_id,
                           f"KG 不可达, {len(results['jobs'])} 批入 outbox")
        else:
            self.audit.log(actor, "consolidate", child_id,
                           f"promoted={results['promoted']} "
                           f"rejected={len(rejected)} conflicts={len(results['conflicts'])}")
        return results

    def _send_memories(self, memories, threshold, child_id, actor, results):
        payload = {"memories": memories, "threshold": threshold,
                   "source": "memory-consolidate"}
        resp, err = self._post("/kg/runtime-consolidate", payload)
        if err is not None:
            self._queue(payload, child_id, memories2ids(memories), err, results)
            return
        self._absorb(resp, child_id, [], memories2ids(memories), results)

    def _send_edges(self, edges, child_id, actor, results):
        payload = {"edges": edges, "source": "memory-consolidate"}
        resp, err = self._post("/kg/edges:batch", payload)
        if err is not None:
            self._queue(payload, child_id, [], err, results)
            return
        self._absorb(resp, child_id, edges2keys(edges), [], results)

    # ------------------------------------------------------------ KG 客户端
    def post(self, path, payload):
        """KG HTTP 调用(公开给 erase 等模块复用); 返回 (resp|None, err|None)。"""
        try:
            r = requests.post(self.kg_url + path, json=payload, timeout=self.timeout)
            if r.status_code >= 500:
                return None, f"kg_http_{r.status_code}"
            return r.json(), None
        except requests.RequestException as e:
            return None, f"kg_unreachable:{type(e).__name__}"

    def _post(self, path, payload):
        return self.post(path, payload)

    def _absorb(self, resp: dict, child_id: str, edge_keys, episode_ids, results):
        """成功响应: 台账(回流数据, 删除合规依据) + 冲突待审队列 + 埋点。"""
        version = resp.get("version")
        applied = resp.get("applied", resp.get("promoted", 0))
        results["promoted"] += int(applied or 0)
        if version:
            results["kg_versions"].append(version)
        conflicts = resp.get("conflicts") or []
        for c in conflicts:
            with self.db.tx() as conn:
                conn.execute(
                    "INSERT INTO pending_conflicts(kg_conflict_id, head, rel, tail, "
                    "kind, detail) VALUES(?,?,?,?,?,?)",
                    (c.get("id"), c.get("head", ""), c.get("rel", ""),
                     c.get("tail", ""), c.get("kind", "conflict"),
                     c.get("detail", "")))
        results["conflicts"].extend(conflicts)
        with self.db.tx() as conn:
            conn.execute(
                "INSERT INTO consolidation_ledger(job_id, child_id, episode_ids, edges, "
                "kg_version) VALUES(?,?,?,?,?)",
                (f"c_{now():.0f}", child_id, dump(episode_ids),
                 dump(edge_keys), version))
        self.metrics.consolidate_edges(int(applied or 0))

    def _queue(self, payload, child_id, episode_ids, err, results):
        with self.db.tx() as conn:
            conn.execute("INSERT INTO consolidation_jobs(payload, status, attempts, "
                         "last_error) VALUES(?,?,1,?)",
                         (dump({"payload": payload, "child_id": child_id,
                                "episode_ids": episode_ids}), "queued", err))
        results["queued"] = True
        results["jobs"].append({"error": err})

    # ------------------------------------------------------------ outbox 重推
    def flush(self, actor: str = "system") -> dict:
        jobs = self.db.q("SELECT * FROM consolidation_jobs WHERE status='queued' "
                         "ORDER BY id")
        sent = failed = 0
        for job in jobs:
            wrap = load(job["payload"], {})
            payload = wrap.get("payload", {})
            path = "/kg/runtime-consolidate" if "memories" in payload else "/kg/edges:batch"
            resp, err = self._post(path, payload)
            with self.db.tx() as conn:
                if err is None:
                    conn.execute("UPDATE consolidation_jobs SET status='sent', "
                                 "attempts=attempts+1 WHERE id=?", (job["id"],))
                    sent += 1
                    self._absorb(resp, wrap.get("child_id", "default"), [],
                                 wrap.get("episode_ids", []),
                                 {"promoted": 0, "kg_versions": [], "conflicts": []})
                else:
                    conn.execute("UPDATE consolidation_jobs SET attempts=attempts+1, "
                                 "last_error=? WHERE id=?", (err, job["id"]))
                    failed += 1
        self.audit.log(actor, "consolidate_flush", "",
                       f"sent={sent} failed={failed}")
        return {"sent": sent, "failed": failed}

    # ------------------------------------------------------------ 冲突待审队列
    def conflicts(self, status: str = "open", limit: int = 100) -> list[dict]:
        return [dict(r) for r in self.db.q(
            "SELECT * FROM pending_conflicts WHERE status=? ORDER BY id DESC LIMIT ?",
            (status, int(limit)))]

    def resolve(self, conflict_id: int, accept: bool, actor: str = "parent") -> dict:
        row = self.db.q1("SELECT * FROM pending_conflicts WHERE id=? AND status='open'",
                         (conflict_id,))
        if not row:
            return {"error": "conflict not found or already resolved"}
        action = "allow" if accept else "delete"
        resp, err = self._post(f"/kg/conflicts/{row['kg_conflict_id']}/resolve",
                               {"action": action})
        if err is not None:
            return {"error": err}
        with self.db.tx() as conn:
            conn.execute("UPDATE pending_conflicts SET status='resolved' WHERE id=?",
                         (conflict_id,))
        self.audit.log(actor, "conflict_resolve", f"conflict:{conflict_id}",
                       f"action={action}")
        return {"resolved": conflict_id, "action": action, "kg": resp}
