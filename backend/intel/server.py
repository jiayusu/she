#!/usr/bin/env python3
"""server.py — 数据情报服务 (06 PRD V1.0)。

PRD §6 接口:
  GET  /intel/question-pool              本周候选条目 (审核工作台数据源)
  POST /intel/question-pool/{id}/approve → 触发 KG /kg/edges:batch (硬闸门: 仅 structured)
  POST /intel/weekly-report/run          手动触发周报
  GET  /intel/sentiment                  舆情列表
运维接口:
  GET  /intel/health | /intel/metrics (§9 埋点) | /intel/archive (FR-I08 检索)
  POST /intel/question-pool/{id}/discard | /intel/sentiment/poll | /intel/jobs/run
  POST /intel/import (manual provider 人工导入降级入口)
启动: python server.py   (INTEL_PORT 默认 8791)

架构红线 (§7): zhihu_search 不注册为任何 Agent/MCP 工具; 唯一入产品路径
人工审核 → KG 热更新 → 王冠本地检索; 本服务只产出结构化提炼结果。
"""
import json
import sqlite3
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory

import archive
import config
import db
import kg_bridge
import llm_client
import notify
import pipeline
import quota
import radar
import sentiment
import zhihu_api

config.ensure_dirs()
app = Flask(__name__, static_folder=None)
WEB_DIR = Path(__file__).resolve().parent / "web"


def conn():
    return db.connect()


def check_token():
    """可选运维口令: 设 INTEL_TOKEN 后, 变更类接口需 X-Intel-Token。"""
    want = getattr(config, "INTEL_TOKEN", "")
    return (not want) or request.headers.get("X-Intel-Token") == want


def body():
    return request.get_json(force=True, silent=True) or {}


@app.get("/")
def index():
    return send_from_directory(WEB_DIR, "index.html")


@app.get("/web/<path:p>")
def web_assets(p):
    return send_from_directory(WEB_DIR, p)


@app.get("/intel/health")
def health():
    c = conn()
    s = {
        "status": "ok", "provider": zhihu_api.provider().name,
        "llm": llm_client.available(), "kg_url": config.KG_URL,
        "wecom": bool(config.WECOM_WEBHOOK),
        "quota_used_today": quota.used_today(c),
        "quota_limit": config.ZHIHU_DAILY_LIMIT,
        # §7 红线自证: 本服务未注册任何 MCP 工具, 搜索能力不出服务端
        "mcp_exposed": False,
        "child_output_path": "manual_review -> kg_edges:batch -> 王冠 local retrieval",
    }
    row = c.execute("SELECT COUNT(*) c FROM candidates WHERE status='pending_struct' "
                    "AND week=?", (db.iso_week(),)).fetchone()
    s["pending_struct_this_week"] = row["c"]
    c.close()
    return jsonify(s)


# ---------------------------------------------------------------- FR-I04 工作台
@app.get("/intel/question-pool")
def question_pool():
    c = conn()
    week = request.args.get("week") or db.iso_week()
    status = request.args.get("status") or None
    include_filtered = request.args.get("include_filtered") == "1"
    rows = pipeline.weekly_candidates(c, week=week, status=status,
                                      include_filtered=include_filtered)
    counts = {r["status"]: r["c"] for r in c.execute(
        "SELECT status, COUNT(*) c FROM candidates WHERE week=? AND merged_into IS NULL "
        "GROUP BY status", (week,))}
    c.close()
    return jsonify({"week": week, "counts": counts, "items": rows})


@app.get("/intel/question-pool/<int:cid>")
def candidate_detail(cid):
    c = conn()
    row = c.execute("SELECT * FROM candidates WHERE id=?", (cid,)).fetchone()
    if not row:
        c.close()
        return jsonify({"error": "not found"}), 404
    logs = [dict(r) for r in c.execute(
        "SELECT * FROM review_log WHERE candidate_id=? ORDER BY id", (cid,))]
    c.close()
    out = dict(row)
    out["review_log"] = logs
    return jsonify(out)


@app.post("/intel/question-pool/<int:cid>/approve")
def approve(cid):
    if not check_token():
        return jsonify({"error": "forbidden"}), 403
    b = body()
    reviewer = str(b.get("reviewer") or "anonymous")[:40]
    c = conn()
    try:
        ok, detail = kg_bridge.approve(c, cid, reviewer, edits=b.get("edits"))
    finally:
        c.close()
    return jsonify({"ok": ok, **detail}), (200 if ok else 400)


@app.post("/intel/question-pool/<int:cid>/discard")
def discard(cid):
    if not check_token():
        return jsonify({"error": "forbidden"}), 403
    b = body()
    c = conn()
    try:
        ok, detail = kg_bridge.discard(c, cid, str(b.get("reviewer") or "anonymous")[:40],
                                       str(b.get("note") or ""))
    finally:
        c.close()
    return jsonify({"ok": ok, **detail}), (200 if ok else 400)


@app.post("/intel/question-pool/<int:cid>/modify")
def modify(cid):
    """Apply an auditable edit without bypassing the approval gate."""
    if not check_token():
        return jsonify({"error": "forbidden"}), 403
    b = body()
    c = conn()
    try:
        row = c.execute("SELECT * FROM candidates WHERE id=?", (cid,)).fetchone()
        if not row:
            return jsonify({"error": "candidate not found"}), 404
        edited = kg_bridge.apply_edits(c, row, b.get("edits") or {})
        c.execute("INSERT INTO review_log(candidate_id, action, reviewer, after_json, created_at) VALUES(?,?,?,?,?)",
                  (cid, "modify", str(b.get("reviewer") or "anonymous")[:40], json.dumps(edited, ensure_ascii=False), db.now()))
        c.commit()
        return jsonify({"ok": True, "edited": list(edited)})
    finally:
        c.close()


# ---------------------------------------------------------------- FR-I05 周报
@app.post("/intel/weekly-report/run")
def weekly_report_run():
    if not check_token():
        return jsonify({"error": "forbidden"}), 403
    c = conn()
    out = radar.run(c, force=bool(body().get("force")))
    c.close()
    return jsonify(out), (200 if out.get("ok") else 500)


@app.get("/intel/reports/latest")
def report_latest():
    c = conn()
    out = radar.latest(c)
    c.close()
    return jsonify(out or {"error": "no reports yet"})


@app.get("/intel/radar/latest")
def radar_latest():
    return report_latest()


# ---------------------------------------------------------------- FR-I06 舆情
@app.get("/intel/sentiment")
def sentiment_list():
    c = conn()
    rows = sentiment.recent(
        c, sentiment=request.args.get("sentiment") or None,
        kind=request.args.get("kind") or None,
        limit=min(500, request.args.get("limit", 100, type=int)),
        since_hours=request.args.get("since_hours", type=int))
    c.close()
    return jsonify({"count": len(rows), "items": rows})


@app.post("/intel/sentiment/poll")
def sentiment_poll():
    if not check_token():
        return jsonify({"error": "forbidden"}), 403
    c = conn()
    out = sentiment.poll(c, force=bool(body().get("force")))
    c.close()
    return jsonify(out)


# ---------------------------------------------------------------- FR-I01/02/03 管线
@app.post("/intel/pipeline/run")
def pipeline_run():
    """手动跑一轮问题池管线: 采集→排序→落库→结构化。"""
    if not check_token():
        return jsonify({"error": "forbidden"}), 403
    c = conn()
    fetch = pipeline.fetch_and_store(c)
    struct = pipeline.structure_pending(c) if not fetch.get("errors") or fetch["inserted"] \
        else {"skipped": True}
    c.close()
    return jsonify({"fetch": fetch, "structure": struct})


@app.post("/intel/import")
def manual_import():
    """§8 降级入口: 处理 inbox/ 人工导入 JSON, 等价于一轮 manual 管线。"""
    c = conn()
    fetch = pipeline.fetch_and_store(c, queries=None)
    struct = pipeline.structure_pending(c) if fetch.get("inserted") else {"skipped": True}
    c.close()
    return jsonify({"fetch": fetch, "structure": struct})


@app.post("/intel/jobs/run")
def jobs_run():
    """跑到期补跑任务 (调度器每日/手动调用)。"""
    c = conn()
    ran = []
    for job in quota.due_jobs(c, ("question_pool", "sentiment", "radar")):
        payload = json.loads(job["payload"] or "{}")
        if job["kind"] == "question_pool":
            out = pipeline.fetch_and_store(c, queries=payload.get("queries_left"))
            struct = pipeline.structure_pending(c) if out.get("inserted") else None
            out = {"fetch": out, "structure": struct}
        elif job["kind"] == "sentiment":
            out = sentiment.poll(c, force=True)
        elif job["kind"] == "radar":
            out = radar.run(c, force=True)
        else:
            out = {"skipped": True}
        quota.finish_job(c, job["id"], ok=not out.get("skipped"))
        ran.append({"job": job["kind"], "id": job["id"], "result_summary": str(out)[:300]})
    kg = kg_bridge.retry_kg_pending(c)
    c.close()
    return jsonify({"jobs": ran, "kg_retries": kg})


@app.post("/intel/kg/flush")
def kg_flush():
    if not check_token():
        return jsonify({"error": "forbidden"}), 403
    c = conn()
    try:
        return jsonify({"ok": True, "results": kg_bridge.retry_kg_pending(c)})
    finally:
        c.close()


# ---------------------------------------------------------------- §9 埋点 + 额度
@app.get("/intel/metrics")
def metrics():
    c = conn()
    day = db.today()
    today = {r["event"]: r["v"] for r in c.execute(
        "SELECT event, COALESCE(SUM(value),0) v FROM metrics WHERE ts LIKE ? "
        "GROUP BY event", (day + "%",))}
    total = {r["event"]: r["v"] for r in c.execute(
        "SELECT event, COALESCE(SUM(value),0) v FROM metrics GROUP BY event")}
    struct = c.execute(
        "SELECT COALESCE(SUM(CASE WHEN value>0 THEN 1 ELSE 0 END),0) ok, COUNT(*) n "
        "FROM metrics WHERE event='intel_structured'").fetchone()
    quota_rows = [dict(r) for r in c.execute(
        "SELECT * FROM quota_ledger WHERE day=?", (day,))]
    remote = {}
    try:
        remote = zhihu_api.provider().quota()  # manual/fake provider 返回 {}, 不出网
    except Exception as e:  # noqa: BLE001 — 平台侧额度查询失败不影响本地指标
        remote = {"error": str(e)}
    c.close()
    return jsonify({
        "today": today, "total": total,
        "structured_ok_rate": round(struct["ok"] / struct["n"], 3) if struct["n"] else None,
        "quota": {"day": day, "used": sum(r["n"] for r in quota_rows),
                  "limit": config.ZHIHU_DAILY_LIMIT,
                  "by_purpose": quota_rows, "platform": remote},
        "events_schema": sorted(config.METRIC_EVENTS)})


# ---------------------------------------------------------------- FR-I08 存档
@app.get("/intel/archive")
def archive_search():
    """结构化结果永久存档检索 (q 匹配标题/child_question/fact)。"""
    c = conn()
    q = request.args.get("q", "").strip()
    days = request.args.get("days", type=int)
    week = request.args.get("week") or None
    conds, args = ["merged_into IS NULL"], []
    if q:
        conds.append("(title LIKE ? OR child_question LIKE ? OR fact LIKE ? "
                     "OR related_objects LIKE ?)")
        args += [f"%{q}%"] * 4
    if week:
        conds.append("week=?")
        args.append(week)
    if days:
        import time
        cut = time.strftime("%Y-%m-%d %H:%M:%S",
                            time.localtime(time.time() - days * 86400))
        conds.append("created_at >= ?")
        args.append(cut)
    rows = [dict(r) for r in c.execute(
        f"SELECT id, week, title, url, child_question, fact, difficulty, related_objects, "
        f"status, raw_path, created_at FROM candidates WHERE {' AND '.join(conds)} "
        f"ORDER BY id DESC LIMIT 200", args)]
    c.close()
    return jsonify({"count": len(rows), "items": rows})


@app.get("/intel/archive/raw")
def archive_raw():
    """争议溯源: 按归档路径取回原始 JSON (路径来自 candidates.raw_path)。"""
    rel = request.args.get("path", "")
    data = archive.find_raw(rel)
    if data is None:
        return jsonify({"error": "not found or expired (90 天保留期)"}), 404
    return jsonify({"path": rel, "data": data})


@app.errorhandler(sqlite3.OperationalError)
def db_error(e):
    return jsonify({"error": f"db: {e}"}), 500


@app.errorhandler(Exception)
def unexpected(e):  # noqa: BLE001 — 任何单接口异常不拖垮整个服务 (§5)
    from werkzeug.exceptions import HTTPException
    if isinstance(e, HTTPException):
        return e
    return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    config.ensure_dirs()
    print(f"[intel] server on http://127.0.0.1:{config.INTEL_PORT}  db={config.DB_PATH}")
    app.run(host="127.0.0.1", port=config.INTEL_PORT, threaded=True, debug=False)
