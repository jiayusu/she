#!/usr/bin/env python3
"""server.py — 04 记忆存储 HTTP 服务(PRD §6 接口冻结 + 管理/合规端点)。

启动: python server.py   (STORE_PORT 默认 8789, KG_URL 指向 kb 热更新服务)
依赖: ASR(02)剧本引擎(01)经 route(03) 调度写入; 阿海召回; 小基消费程序性任务。
"""
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from flask import Flask, jsonify, request  # noqa: E402

from memstore.config import Config  # noqa: E402
from memstore.service import MemoryService  # noqa: E402

app = Flask(__name__)
svc: MemoryService = None  # type: ignore


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def body():
    return request.get_json(force=True, silent=True) or {}


def err(msg, code=400):
    return jsonify({"error": msg}), code


# ================================================================ PRD §6 接口
@app.post("/memory/episodes")
def episodes_write():
    """写入(来自 Agent 调度 FR-G04): 每轮对话一条 episode, 向量入库。"""
    b = body()
    if not str(b.get("utterance", "")).strip():
        return err("utterance 必填(原句/内容)")
    row = svc.write_episode(
        utterance=str(b["utterance"]), scene=str(b.get("scene", "")),
        assess=b.get("assess"), emotion=str(b.get("emotion", "")),
        emotion_v=b.get("emotion_v"), salience=b.get("salience", 0.3),
        session_id=str(b.get("session_id", "")),
        child_id=str(b.get("child_id", "default")),
        day=b.get("day"), chapter=b.get("chapter"), arc_id=str(b.get("arc_id", "")),
        role=str(b.get("role", "child")), kind=str(b.get("kind", "dialogue")),
        ref_id=str(b.get("ref_id", "")), ts=b.get("ts"),
        push_working=bool(b.get("push_working", False)),
        mirror_salience=bool(b.get("mirror_salience", b.get("salience") is not None
                                   and b["salience"] >= 0.5)),
        actor=str(b.get("actor", "agent:route")))
    return jsonify(row), 201


@app.get("/memory/recall")
def recall():
    """跨天召回(阿海): ?query=&k=5&include_cold=1&child_id=, 支持时间查询。"""
    query = request.args.get("query", "").strip()
    if not query:
        return err("query 必填, 如 ?query=上周第一次学的apple")
    out = svc.recall(query, k=request.args.get("k", default=5, type=int),
                     include_cold=request.args.get("include_cold", default="1") == "1",
                     child_id=request.args.get("child_id") or None,
                     session_id=request.args.get("session_id") or None)
    return jsonify(out)


@app.post("/memory/consolidate")
def consolidate():
    """巩固批次入 KG 热更新(FR-M04): 发音评估闸门→KG 版本+1→冲突进待审队列。"""
    b = body()
    if not (b.get("memories") or b.get("edges")):
        return err("需要 memories[] 或 edges[], "
                   '如 {"memories":[{"scene":"breakfast","words":["milk","cup"],'
                   '"assess":88}]}')
    return jsonify(svc.consolidate(b, actor=str(b.get("actor", "agent:route"))))


@app.get("/memory/procedural/due")
def procedural_due():
    """到期程序性任务(小基): ?now=ISO|epoch&scene=; 执行后 POST .../<id>/fired。"""
    now_raw = request.args.get("now")
    ts = None
    if now_raw:
        try:
            ts = float(now_raw)
        except ValueError:
            from datetime import datetime
            try:
                ts = datetime.fromisoformat(now_raw).timestamp()
            except ValueError:
                return err("now 须为 epoch 秒或 ISO 时间")
    tasks = svc.procedural_due(ts=ts, scene=request.args.get("scene") or None)
    return jsonify({"count": len(tasks), "tasks": tasks})


@app.post("/memory/snapshot")
def snapshot():
    return jsonify(svc.snapshot(note=str(body().get("note", "manual")),
                                actor=str(body().get("actor", "parent")))), 201


@app.post("/memory/rollback/<int:v>")
def rollback(v):
    out = svc.rollback(v)
    return (jsonify(out), 200) if "error" not in out else err(out["error"], 404)


# ================================================================ 工作记忆/会话
@app.post("/memory/working/<sid>/push")
def working_push(sid):
    b = body()
    if not str(b.get("text", "")).strip():
        return err("text 必填")
    return jsonify(svc.working_push(sid, str(b["text"]),
                                    role=str(b.get("role", "child")),
                                    scene=str(b.get("scene", "")),
                                    child_id=str(b.get("child_id", "default")),
                                    ts=b.get("ts")))


@app.get("/memory/working/<sid>")
def working_get(sid):
    return jsonify(svc.working_get(sid))


@app.post("/memory/session/<sid>/state")
def session_state(sid):
    b = body()
    row = svc.session_state(sid, script_state=b.get("script_state"),
                            chapter=b.get("chapter"),
                            child_id=b.get("child_id"))
    return jsonify(row)


@app.post("/memory/session/<sid>/recover")
def session_recover(sid):
    return jsonify(svc.session_recover(sid))


# ================================================================ 程序性库管理
@app.post("/memory/procedural")
def procedural_add():
    b = body()
    if not b.get("name") or not b.get("trigger") or not b.get("action"):
        return err("name/trigger/action 必填, trigger 如 "
                   '{"type":"time","time":"20:30","repeat":"daily"}')
    try:
        return jsonify(svc.procedural.add(b["name"], b["trigger"], b["action"],
                                          child_id=str(b.get("child_id", "default")))), 201
    except (ValueError, KeyError) as e:
        return err(f"trigger/action 非法: {e}")


@app.get("/memory/procedural")
def procedural_list():
    return jsonify({"count": svc.procedural.count(),
                    "tasks": svc.procedural.list(child_id=request.args.get("child_id"))})


@app.post("/memory/procedural/<int:pid>/fired")
def procedural_fired(pid):
    row = svc.procedural.mark_fired(pid)
    return (jsonify(row), 200) if row else err("task not found", 404)


@app.post("/memory/procedural/<int:pid>/enabled")
def procedural_enabled(pid):
    row = svc.procedural.set_enabled(pid, bool(body().get("on", True)))
    return (jsonify(row), 200) if row else err("task not found", 404)


# ================================================================ 白名单/显著性
@app.post("/memory/whitelist")
def whitelist_add():
    b = body()
    if not b.get("ref_id") or not b.get("reason"):
        return err("ref_id/reason 必填(白名单只增不删)")
    return jsonify(svc.whitelist_add(
        str(b["ref_id"]), str(b["reason"]), content=str(b.get("content", "")),
        child_id=str(b.get("child_id", "default")),
        actor=str(b.get("actor", "parent")),
        episode_id=b.get("episode_id"))), 201


@app.get("/memory/whitelist")
def whitelist_list():
    return jsonify({"count": len(svc.salience.whitelist_items(
        child_id=request.args.get("child_id"))),
        "items": svc.salience.whitelist_items(request.args.get("child_id"))})


@app.get("/memory/salience")
def salience_items():
    return jsonify({"count": svc.salience.count(),
                    "items": svc.salience.items(
                        child_id=request.args.get("child_id"),
                        limit=request.args.get("limit", default=50, type=int))})


# ================================================================ 冲突待审/巩固管理
@app.get("/memory/conflicts")
def conflicts_list():
    status = request.args.get("status", "open")
    return jsonify({"status": status, "count": len(svc.consolidator.conflicts(status)),
                    "conflicts": svc.consolidator.conflicts(status)})


@app.post("/memory/conflicts/<int:cid>/resolve")
def conflict_resolve(cid):
    b = body()
    if "accept" not in b:
        return err('accept 必填: {"accept": true|false}')
    out = svc.consolidator.resolve(cid, bool(b["accept"]))
    return (jsonify(out), 200) if "error" not in out else err(out["error"], 404)


@app.post("/memory/consolidate/flush")
def consolidate_flush():
    """outbox 重推(KG 恢复后)。"""
    return jsonify(svc.consolidator.flush(actor="system"))


# ================================================================ 快照/索引/审计/指标
@app.get("/memory/snapshots")
def snapshots_list():
    return jsonify({"count": len(svc.snapshots.list()), "snapshots": svc.snapshots.list()})


@app.post("/memory/index/rebuild")
def index_rebuild():
    n = svc.episodic.rebuild_index()
    svc.snapshots.persist_index()
    svc.audit.log("parent", "index_rebuild", "", f"reindexed={n}")
    return jsonify({"reindexed": n})


@app.get("/memory/audit")
def audit_query():
    return jsonify({"count": len(svc.audit.query(
        date=request.args.get("date"), action=request.args.get("action"),
        limit=request.args.get("limit", default=100, type=int))),
        "entries": svc.audit.query(date=request.args.get("date"),
                                   action=request.args.get("action"),
                                   limit=request.args.get("limit", default=100,
                                                          type=int))})


@app.get("/memory/metrics")
def metrics():
    return jsonify(svc.metrics.snapshot())


@app.post("/memory/jobs/run")
def jobs_run():
    """手动触发每日任务(快照/衰减剪枝/审计保留), FR-G07 对齐的可观测性。"""
    return jsonify(svc.run_daily_jobs())


# ================================================================ 合规删除
@app.post("/memory/erase")
def erase():
    b = body()
    child_id = str(b.get("child_id", "")).strip()
    if not child_id and not b.get("purge_all"):
        return err("child_id 必填(整设备清除用 purge_all=true)")
    return jsonify(svc.erase(child_id or "default",
                             requested_by=str(b.get("requested_by", "parent")),
                             purge_all=bool(b.get("purge_all", False))))


@app.get("/memory/erase/jobs")
def erase_jobs():
    return jsonify({"count": len(svc.erasure.jobs()), "jobs": svc.erasure.jobs()})


# ================================================================ 健康
@app.get("/healthz")
def healthz():
    return jsonify(svc.health())


def create_service(cfg: Config | None = None) -> MemoryService:
    global svc
    svc = cfg and MemoryService(cfg) or MemoryService()
    svc.start_jobs()
    return svc


if __name__ == "__main__":
    cfg = Config()
    service = create_service(cfg)
    log(f"memory store on http://127.0.0.1:{cfg.port}  data={cfg.data_dir} "
        f"kg={cfg.kg_url}")
    app.run(host="127.0.0.1", port=cfg.port, threaded=True, debug=False)
