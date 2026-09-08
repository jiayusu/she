#!/usr/bin/env python3
"""kg_bridge.py — FR-I04 人工审核 → KG 热更新。

硬闸门 (验收: 未经审核不得入 KG):
  - 只有 status='structured' 的条目可 approve; filtered/pending_struct 永不可入。
  - KG 写入只发生在 approve 之后, source 标记 zhihu_intel:<candidate_id> 可回滚溯源。
  - KG 不可达 → status='kg_pending', 调度器重试, 不丢不跳。
修改留痕: review_log 记 before/after 全量 JSON。
"""
import json

import config
import db

import requests


def _kg_payload(row):
    edges = json.loads(row["kg_edges"] or "[]")
    return {"source": f"{config.KG_SOURCE}:{row['id']}",
            "edges": [{"op": "add", **e} for e in edges]}


def push_kg(conn, candidate_id):
    """把已批准条目的 kg_edges 推到 KG /kg/edges:batch。"""
    row = conn.execute("SELECT * FROM candidates WHERE id=?", (candidate_id,)).fetchone()
    if not row:
        return {"ok": False, "error": "candidate not found"}
    if row["status"] not in ("approved", "kg_pending"):
        return {"ok": False, "error": f"status={row['status']} not pushable (硬闸门)"}
    payload = _kg_payload(row)
    if not payload["edges"]:
        conn.execute("UPDATE candidates SET status='kg_pushed', updated_at=? WHERE id=?",
                     (db.now(), candidate_id))
        return {"ok": True, "applied": 0, "note": "no edges"}
    try:
        r = requests.post(f"{config.KG_URL}/kg/edges:batch", json=payload, timeout=60)
        r.raise_for_status()
        out = r.json()
    except Exception as e:  # noqa: BLE001 — KG 暂不可达: 挂起待重试
        conn.execute("UPDATE candidates SET status='kg_pending', updated_at=? WHERE id=?",
                     (db.now(), candidate_id))
        conn.commit()
        return {"ok": False, "error": f"kg_unreachable: {e}"}
    applied = int(out.get("applied") or 0)
    status = "kg_pushed" if applied else "kg_pending"  # 全被 KG 规则拒绝时留人工处理
    with conn:
        conn.execute("UPDATE candidates SET status=?, updated_at=? WHERE id=?",
                     (status, db.now(), candidate_id))
        conn.execute("INSERT INTO review_log(candidate_id, action, reviewer, kg_result, "
                     "created_at) VALUES(?,?,?,?,?)",
                     (candidate_id, "kg_push", "system", json.dumps(
                         {"applied": applied, "version": out.get("version"),
                          "rejected": len(out.get("rejected") or []),
                          "conflicts": len(out.get("conflicts") or [])},
                         ensure_ascii=False), db.now()))
    return {"ok": bool(applied), "applied": applied, "kg_version": out.get("version"),
            "rejected": out.get("rejected") or [], "conflicts": out.get("conflicts") or []}


EDITABLE = {"phenomenon", "child_question", "fact", "difficulty", "related_objects",
            "kg_edges"}


def apply_edits(conn, row, edits):
    """审核人修改条目内容 (修改留痕), 返回规范化后的字段 dict。"""
    clean = {}
    if "phenomenon" in edits:
        clean["phenomenon"] = str(edits["phenomenon"] or "")[:200]
    if "child_question" in edits:
        clean["child_question"] = str(edits["child_question"] or "")[:120]
    if "fact" in edits:
        clean["fact"] = str(edits["fact"] or "")[:300]
    if "difficulty" in edits:
        try:
            clean["difficulty"] = min(5, max(1, int(edits["difficulty"])))
        except (TypeError, ValueError):
            pass
    if "related_objects" in edits:
        objs = edits["related_objects"]
        if isinstance(objs, str):
            objs = [s.strip() for s in objs.split(",") if s.strip()]
        clean["related_objects"] = json.dumps([str(x)[:60] for x in objs][:6],
                                              ensure_ascii=False)
    if "kg_edges" in edits:
        edges = []
        for e in edits["kg_edges"] or []:
            if not isinstance(e, dict):
                continue
            e = {"head": str(e.get("head", "")).strip().lower(),
                 "rel": str(e.get("rel", "")).strip(),
                 "tail": str(e.get("tail", "")).strip().lower(),
                 "weight": max(0.5, min(3.0, float(e.get("weight", 1.0))))}
            if e["rel"] in config.KG_EDGE_RELS and e["head"] and e["tail"] \
                    and e["head"] != e["tail"]:
                edges.append(e)
        clean["kg_edges"] = json.dumps(edges[:4], ensure_ascii=False)
    if clean:
        with conn:
            conn.execute(
                f"UPDATE candidates SET {', '.join(k + '=?' for k in clean)}, "
                f"updated_at=? WHERE id=?",
                (*clean.values(), db.now(), row["id"]))
    return clean


def approve(conn, candidate_id, reviewer, edits=None):
    """通过并推 KG。返回 (ok, detail)。硬闸门: 只有 structured 可通过。"""
    row = conn.execute("SELECT * FROM candidates WHERE id=?", (candidate_id,)).fetchone()
    if not row:
        return False, {"error": "candidate not found"}
    if row["status"] == "filtered":
        return False, {"error": "filtered item 不可入 KG (敏感前置过滤)"}
    if row["status"] not in ("structured", "kg_pending", "approved"):
        return False, {"error": f"status={row['status']} 未经结构化/已处理, 不得入 KG"}

    before = {k: row[k] for k in EDITABLE}
    edited = apply_edits(conn, row, edits or {}) if edits else {}
    if edited:
        row = conn.execute("SELECT * FROM candidates WHERE id=?",
                           (candidate_id,)).fetchone()
        with conn:
            conn.execute("INSERT INTO review_log(candidate_id, action, reviewer, "
                         "before_json, after_json, created_at) VALUES(?,?,?,?,?,?)",
                         (candidate_id, "modify", reviewer,
                          json.dumps({k: before[k] for k in edited}, ensure_ascii=False,
                                     default=str),
                          json.dumps({k: row[k] for k in edited}, ensure_ascii=False,
                                     default=str), db.now()))
        row = conn.execute("SELECT * FROM candidates WHERE id=?",
                           (candidate_id,)).fetchone()

    if row["status"] == "structured":
        with conn:
            conn.execute("UPDATE candidates SET status='approved', updated_at=? "
                         "WHERE id=?", (db.now(), candidate_id))
            conn.execute("INSERT INTO review_log(candidate_id, action, reviewer, note, "
                         "created_at) VALUES(?,?,?,?,?)",
                         (candidate_id, "approve", reviewer, "", db.now()))
            db.metric(conn, "intel_approved", "question_pool", 1, f"reviewer={reviewer}")

    out = push_kg(conn, candidate_id)
    return out["ok"], {"kg": out, "edited": list(edited)}


def discard(conn, candidate_id, reviewer, note=""):
    row = conn.execute("SELECT status FROM candidates WHERE id=?", (candidate_id,)).fetchone()
    if not row:
        return False, {"error": "candidate not found"}
    if row["status"] in ("kg_pushed",):
        return False, {"error": "已入 KG, 请走 KG 回滚流程 (/kg/rollback)"}
    with conn:
        conn.execute("UPDATE candidates SET status='discarded', updated_at=? WHERE id=?",
                     (db.now(), candidate_id))
        conn.execute("INSERT INTO review_log(candidate_id, action, reviewer, note, "
                     "created_at) VALUES(?,?,?,?,?)",
                     (candidate_id, "discard", reviewer, note[:200], db.now()))
    return True, {"discarded": candidate_id}


def retry_kg_pending(conn, limit=20):
    """调度器: 重试 kg_pending (KG 刚才不可达/全拒的条目)。"""
    rows = conn.execute("SELECT id FROM candidates WHERE status='kg_pending' "
                        "ORDER BY updated_at LIMIT ?", (limit,)).fetchall()
    return [push_kg(conn, r["id"]) for r in rows]
