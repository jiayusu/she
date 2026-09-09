"""service.py — 记忆存储服务门面: 组装五库与生命周期引擎, 提供全链路操作。

写路径(FR-M02/M09/G05): episode 落情景库+向量 → 显著性≥阈值自动进白名单(物理隔离)
→ 可选镜像进显著性缓冲(满则最低分降级) → 可选镜像进工作记忆(满则 LRU 溢出回情景库)
→ 审计 + 埋点 + 版本+1。
"""
import json
import threading
import time
from pathlib import Path

from .audit import Audit
from .config import Config
from .consolidate import Consolidator
from .db import DB, dump, local_day, now
from .episodic import EpisodicStore
from .erase import Erase
from .lifecycle import Lifecycle
from .metrics import Metrics
from .procedural import ProceduralStore
from .salience import SalienceBuffer
from .snapshot import Snapshots
from .temporal import is_temporal, parse
from .vector import HashingEmbedder, VectorIndex
from .working import WorkingMemory
from .learning import LearningStore


class MemoryService:
    def __init__(self, cfg: Config | None = None):
        self.cfg = cfg or Config()
        self.cfg.ensure_dirs()
        self.metrics = Metrics()
        self.db = DB(self.cfg.db_path())
        self.embedder = HashingEmbedder(self.cfg.embed_dim)
        self.index = VectorIndex(self.cfg.embed_dim, use_faiss=self.cfg.use_faiss)
        self.working = WorkingMemory(self.db, cap=self.cfg.working_cap)
        self.episodic = EpisodicStore(self.db, self.embedder, self.index)
        self.salience = SalienceBuffer(self.db, cap=self.cfg.salience_cap)
        self.procedural = ProceduralStore(self.db, cap=self.cfg.procedural_cap)
        self.audit = Audit(self.db, self.cfg.audit_dir(),
                           retention_days=self.cfg.audit_retention_days)
        self.learning = LearningStore(self.db, self.audit)
        self.lifecycle = Lifecycle(
            self.db, self.episodic, self.salience, self.audit, self.metrics,
            decay_lambda=self.cfg.decay_lambda_per_day, floor=self.cfg.prune_floor,
            boost_mult=self.cfg.reconsolidate_boost, boost_add=self.cfg.reconsolidate_add)
        self.consolidator = Consolidator(
            self.db, self.audit, self.metrics, self.cfg.kg_url,
            min_assess=self.cfg.consolidate_min_assess,
            timeout=self.cfg.kg_timeout)
        self.snapshots = Snapshots(
            self.db, self.cfg.snapshot_dir(), self.cfg.vector_path(), self.episodic,
            self.embedder)
        self.erasure = Erase(self.db, self.audit, self.metrics, self.cfg.report_dir(),
                             self.consolidator, index_purger=self._purge_vectors,
                             snapshot_purger=self.snapshots.purge_all)
        self._jobs_thread = None
        self._stop = threading.Event()
        self._last_job_day = {"snapshot": "", "decay": "", "retention": ""}
        self.snapshots.startup_check()  # FAISS 损坏/缺失 → 自动重建

    def close(self):
        self._stop.set()
        if self._jobs_thread:
            self._jobs_thread.join(timeout=2)
        self.snapshots.persist_index()
        self.db.close()

    # ================================================================ 情景写入(FR-M02)
    def write_episode(self, *, utterance, scene="", assess=None, emotion="",
                      emotion_v=None, salience=0.3, session_id="", child_id="default",
                      day=None, chapter=None, arc_id="", role="child", kind="dialogue",
                      ref_id="", ts=None, push_working=False, mirror_salience=False,
                      actor="agent:route") -> dict:
        t0 = time.perf_counter()
        ts = now() if ts is None else float(ts)
        salience = float(salience if salience is not None else 0.3)

        # 显著性 ≥ 阈值自动进"永不遗忘"白名单(FR-G05 落库侧)
        whitelisted = 1 if salience >= self.cfg.whitelist_threshold else 0
        row = self.episodic.add(
            ts=ts, scene=scene, utterance=utterance, assess=assess, emotion=emotion,
            emotion_v=emotion_v, salience=salience, session_id=session_id,
            child_id=child_id, day=day, chapter=chapter, arc_id=arc_id, role=role,
            kind=kind, whitelisted=whitelisted)
        if whitelisted:
            self.salience.whitelist_add(
                ref_id=ref_id or f"ep_{row['id']}", reason="milestone/salience≥阈值",
                content=utterance, salience=max(salience, 1.0), source="auto",
                child_id=child_id, episode_id=row["id"])
            self.audit.log(actor, "whitelist_add", f"episode:{row['id']}",
                           f"salience={salience} 自动进白名单")
        self.db.bump_version()
        ms = (time.perf_counter() - t0) * 1000
        self.metrics.ep_write(ms)

        out = {**row, "whitelisted": bool(whitelisted), "write_ms": round(ms, 2)}
        if mirror_salience:  # 显著性缓冲镜像(满则最低分降入情景库, FR-M09)
            ev = self.salience.add(content=utterance, salience=salience,
                                   ref_id=ref_id or f"ep_{row['id']}",
                                   episode_id=row["id"], kind=kind, child_id=child_id,
                                   source=actor)
            out["salience_evicted"] = ev["evicted"]
        if push_working:  # 工作记忆镜像(满则 LRU 溢出, FR-M09)
            w = self.working.push(session_id, utterance, role=role, scene=scene,
                                  ts=ts, child_id=child_id)
            if w["evicted"]:
                overflow = self.working.overflow_to_episodic(
                    session_id, w["evicted"], self._overflow_add)
                out["working_evicted_to"] = overflow["id"] if overflow else None
        self.audit.log(actor, "ep_write", f"episode:{row['id']}",
                       f"scene_present={bool(scene)} role={role} "
                       f"salience={salience} day={row['day']} ch={row['chapter']}")
        return out

    def _overflow_add(self, **kw) -> dict:
        row = self.episodic.add(**kw)
        self.db.bump_version()
        self.audit.log("system:working", "working_overflow", f"episode:{row['id']}",
                       f"LRU 溢出 → 情景库 session={kw.get('session_id')}")
        return row

    def _purge_vectors(self, ep_ids, cold_ids):
        if ep_ids or cold_ids:
            self.index.remove([*ep_ids, *[-i for i in cold_ids]])

    # ================================================================ 工作记忆
    def working_push(self, session_id: str, text: str, role="child", scene="",
                     child_id="default", ts=None, actor="agent:engine") -> dict:
        out = self.working.push(session_id, text, role=role, scene=scene, ts=ts,
                                child_id=child_id)
        if out["evicted"]:
            overflow = self.working.overflow_to_episodic(session_id, out["evicted"],
                                                         self._overflow_add)
            out["overflow_episode_id"] = overflow["id"] if overflow else None
        self.audit.log(actor, "working_push", f"session:{session_id}",
                       f"role={role} chars={len(text)}")
        return out

    def working_get(self, session_id: str) -> dict:
        if self.working.touch_session(session_id):
            return {"session_id": session_id, "turns": self.working.items(session_id),
                    "recovered": False}
        state = self.session_recover(session_id)  # 崩溃恢复: 从情景库重建
        state["recovered"] = True
        return state

    def session_recover(self, session_id: str) -> dict:
        """崩溃恢复(非功能): session 状态从情景库重建, ≤2s。"""
        state = self.working.recover(session_id)
        self.audit.log("system:recover", "session_recover", f"session:{session_id}",
                       f"rebuilt={state['rebuilt']} turns in {state['recovered_ms']}ms")
        self.metrics.observe("recover_ms", state["recovered_ms"])
        state["script_state"] = json.loads(state["script_state"] or "{}")
        return state

    def session_state(self, session_id: str, script_state: dict | None = None,
                      chapter: int | None = None, child_id: str | None = None) -> dict:
        """剧本状态持久化(剧情引擎 FR-E03 跨天续剧情)。"""
        with self.db.tx() as conn:
            conn.execute(
                "INSERT INTO sessions(session_id, child_id, script_state, chapter) "
                "VALUES(?,?,?,?) ON CONFLICT(session_id) DO UPDATE SET "
                "script_state=excluded.script_state, chapter=excluded.chapter, "
                "updated_at=datetime('now')",
                (session_id, child_id or "default",
                 dump(script_state) if script_state is not None else "{}",
                 int(chapter or 1)))
        self.db.bump_version()
        row = self.db.q1("SELECT * FROM sessions WHERE session_id=?", (session_id,))
        return {**dict(row), "script_state": json.loads(row["script_state"] or "{}")}

    # ================================================================ 跨天召回(FR-M03/M06)
    def recall(self, query: str, k: int = 5, include_cold: bool = True,
               session_id: str | None = None, child_id: str | None = None,
               actor: str = "agent:ahai", now: float | None = None) -> dict:
        t0 = time.perf_counter()
        parsed = parse(query, now=now)
        vec = self.embedder.embed(parsed["text"] or query)
        active, cold = self.episodic.search(
            vec, k=k, day_from=parsed["day_from"], day_to=parsed["day_to"],
            chapter=parsed["chapter"], text=parsed["text"] or None,
            include_cold=include_cold)

        restored = []
        if parsed["first"]:  # "第一次 X": 窗口内最早匹配置顶
            row = self.episodic.first_in_window(parsed["text"], parsed["day_from"],
                                                parsed["day_to"], parsed["chapter"])
            if row:
                active = [a for a in active if a[0]["id"] != row["id"]]
                active.insert(0, (row, 1.0))
                active = active[:k]

        results = []
        for row, score in active:
            results.append({**row, "score": round(score, 4), "cold": False})
        for row, score in cold:
            results.append({**row, "score": round(score, 4), "cold": True})
            if child_id in (None, row["child_id"]):  # 再巩固: 冷存储命中即恢复加权
                r = self.lifecycle.reconsolidate(row["id"], actor=actor)
                if r:
                    restored.append({**r, "score": round(score, 4)})
        if child_id:
            results = [r for r in results if r["child_id"] == child_id]
            restored = [r for r in restored if r["child_id"] == child_id]

        ms = (time.perf_counter() - t0) * 1000
        self.metrics.recall_hit(k, ms, len(results))
        self.audit.log(actor, "recall", "query:redacted",
                       f"k={k} hits={len(results)} restored={len(restored)} "
                       f"temporal={[m['marker'] for m in parsed['matched']]} "
                       f"in {ms:.1f}ms")
        return {"query": query, "parsed": parsed, "results": results[:k],
                "restored": restored, "latency_ms": round(ms, 2)}

    # ================================================================ 巩固(FR-M04)
    def consolidate(self, batch: dict, actor: str = "agent:route") -> dict:
        out = self.consolidator.run(batch, actor=actor)
        self.db.bump_version()
        return out

    # ================================================================ 快照/回滚(FR-M08)
    def snapshot(self, note: str = "manual", actor: str = "system") -> dict:
        out = self.snapshots.create(note=note)
        self.metrics.snapshot_ok(True, out["duration_ms"])
        self.audit.log(actor, "snapshot", f"v{out['version']}",
                       f"{out['counts']} in {out['duration_ms']}ms")
        return out

    def rollback(self, v: int, actor: str = "parent") -> dict:
        out = self.snapshots.rollback(v)
        if "error" in out:
            return out
        self.metrics.snapshot_ok(True, out["duration_ms"])
        self.audit.log(actor, "rollback", f"v{v}",
                       f"from v{out['rolled_back_to']} reindexed={out['reindexed']} "
                       f"in {out['duration_ms']}ms")
        return out

    # ================================================================ 程序性(FR-M07)
    def procedural_due(self, ts=None, scene=None, actor="agent:xiaoji") -> list[dict]:
        tasks = self.procedural.due(ts=ts, scene=scene)
        if tasks:
            self.audit.log(actor, "procedural_due", "",
                           f"{len(tasks)} due: {[t['name'] for t in tasks]}")
        return tasks

    # ================================================================ 白名单(FR-G05 落库)
    def whitelist_add(self, ref_id: str, reason: str, content: str = "",
                      child_id: str = "default", actor: str = "parent",
                      episode_id=None) -> dict:
        row = self.salience.whitelist_add(ref_id, reason, content=content,
                                          source="manual" if actor != "agent" else "auto",
                                          child_id=child_id, episode_id=episode_id)
        self.audit.log(actor, "whitelist_add", ref_id, f"reason={reason} (只增不删)")
        self.db.bump_version()
        return row

    # ================================================================ 删除合规
    def erase(self, child_id: str, requested_by: str = "parent",
              purge_all: bool = False) -> dict:
        out = self.erasure.request(child_id, requested_by=requested_by,
                                   purge_all=purge_all)
        if purge_all:
            self.working.forget_all()
        else:
            self.working.forget_child(child_id)
        return out

    # ================================================================ 后台任务
    def start_jobs(self):
        """每日自动快照(FR-M08) + 每日衰减剪枝(FR-M05) + 审计保留清理。"""
        if not self.cfg.auto_jobs or self._jobs_thread:
            return
        self._jobs_thread = threading.Thread(target=self._job_loop, daemon=True,
                                             name="memstore-jobs")
        self._jobs_thread.start()

    def _job_loop(self):
        while not self._stop.wait(self.cfg.job_interval_s):
            try:
                self.run_daily_jobs()
            except Exception as e:  # noqa: BLE001 - 后台任务不中断服务
                self.audit.log("system:jobs", "job_error", "", repr(e))

    def run_daily_jobs(self, ts: float | None = None) -> dict:
        ts = now() if ts is None else ts
        today = local_day(ts)
        out = {}
        if self._last_job_day["snapshot"] != today:
            out["snapshot"] = self.snapshot(note="daily-auto", actor="system:jobs")
            self._last_job_day["snapshot"] = today
        if self._last_job_day["decay"] != today:
            out["decay"] = self.lifecycle.decay_pass(ts=ts)
            self._last_job_day["decay"] = today
        if self._last_job_day["retention"] != today:
            removed = self.audit.enforce_retention(ts)
            out["audit_retention_removed"] = removed
            self._last_job_day["retention"] = today
        return out

    # ================================================================ 状态
    def health(self) -> dict:
        return {
            "ok": True,
            "version": self.db.version(),
            "stores": {
                "working": {"sessions": len(self.working._sessions),
                            "cap": self.cfg.working_cap},
                "episodic": self.episodic.counts(),
                "semantic": {"kind": "kg", "url": self.cfg.kg_url,
                             "note": "语义库=KG(kb 模块 kg.db), 经热更接口衔接"},
                "salience": {"buffer": self.salience.count(),
                             "cap": self.cfg.salience_cap,
                             "whitelist": len(self.salience.whitelist_items())},
                "procedural": {"count": self.procedural.count(),
                               "cap": self.cfg.procedural_cap},
            },
            "vector_backend": self.index.backend,
            "embed_dim": self.cfg.embed_dim,
        }
