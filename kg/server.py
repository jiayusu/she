#!/usr/bin/env python3
"""server.py — 万物模式 MVP + W4 热更新管线。

万物 MVP(W2 接入): kg.facts() 本地优先, query_conceptnet() 在线兜底(KG_ONLINE_FALLBACK=1 启用)。

W4 接口(READMD.md 冻结):
  POST /kg/edges:batch          批量加/删/改边
                                链: 规则过滤→矛盾检测→IncLoRA局部训练→FAISS局部重建→版本+1
  POST /kg/snapshot             快照
  POST /kg/rollback/{v}         回滚(坏知识不过夜)
  GET  /kg/packs/{level}        按 L0-L5 打包 diff, ?rollout=x% 灰度(需 device_id)
  POST /kg/runtime-consolidate  阿海情景记忆 → 批量提升为语义边
  GET  /kg/conflicts            矛盾边清单, 人工审入口
  POST /kg/retrieve             FAISS→PPR→LLM重排, 返回带边溯源

启动: python server.py  (环境变量 KG_DB, KG_PORT, KG_ONLINE_FALLBACK, OPENAI_API_KEY)
"""
import hashlib
import os
import shutil
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from flask import Flask, jsonify, request  # noqa: E402

import cleaning  # noqa: E402
import kg  # noqa: E402

ROOT = Path(__file__).resolve().parent
DB_PATH = Path(os.environ.get("KG_DB", ROOT / "data" / "kg.db"))
EMB_DIR = ROOT / "data" / "embeddings"
SNAP_DIR = ROOT / "data" / "snapshots"
PACK_LEVELS = {"L0", "L1", "L2", "L3", "L4", "L5"}

# HasProperty 方向的常见反义词对: 同时出现即矛盾(儿童 KG 不应既有 hot 又有 cold)
ANTONYM_PAIRS = [
    {"hot", "cold"}, {"big", "small"}, {"large", "small"}, {"day", "night"},
    {"fast", "slow"}, {"open", "closed"}, {"up", "down"}, {"empty", "full"},
    {"new", "old"}, {"young", "old"}, {"wet", "dry"}, {"clean", "dirty"},
    {"long", "short"}, {"tall", "short"}, {"loud", "quiet"}, {"happy", "sad"},
    {"light", "dark"}, {"light", "heavy"}, {"soft", "hard"}, {"warm", "cool"},
]

app = Flask(__name__)
_write_lock = threading.Lock()
_retriever = None
_retriever_lock = threading.Lock()


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def get_retriever():
    """惰性加载嵌入检索器(首次调用加载并预热 ~15s)。"""
    global _retriever
    with _retriever_lock:
        if _retriever is None:
            if not (EMB_DIR / "rotate.pt").exists():
                return None
            from kg_embed import KGRetriever
            log("加载 FAISS/PPR 检索器 ...")
            _retriever = KGRetriever(DB_PATH, EMB_DIR)
            _retriever.ppr("apple")  # 预热: 构建 PPR 邻接, 避免首个请求超时
            log(f"检索器就绪: {_retriever.n_entities:,} 实体")
        return _retriever


def set_retriever(r):
    global _retriever
    with _retriever_lock:
        _retriever = r


# ---------------------------------------------------------------- 矛盾检测
def detect_conflicts(conn, edge, new_version):
    """对新加边做矛盾检测。返回 (blocked: bool, conflict: dict|None)。"""
    head, rel, tail = edge["head"], edge["rel"], edge["tail"]
    prev = conn.execute(
        "SELECT status, removed_by, reason FROM edges WHERE head=? AND rel=? AND tail=?",
        (head, rel, tail)).fetchone()
    if prev and prev["status"] == "removed" and prev["removed_by"] in ("llm", "human", "rule"):
        return True, {"kind": "previously_removed", "head": head, "rel": rel, "tail": tail,
                      "detail": f"曾被 {prev['removed_by']} 删除({prev['reason']}), 需人工复核"}
    if rel == "HasProperty":
        for pair in ANTONYM_PAIRS:
            if tail in pair:
                other = (pair - {tail}).pop()
                row = conn.execute(
                    "SELECT 1 FROM edges WHERE head=? AND rel='HasProperty' AND tail=? "
                    "AND status='active'", (head, other)).fetchone()
                if row:
                    return True, {"kind": "contradiction", "head": head, "rel": rel,
                                  "tail": tail,
                                  "detail": f"已有 {head} HasProperty {other}, 与 {tail} 矛盾"}
    if rel == "IsA":
        row = conn.execute("SELECT 1 FROM edges WHERE head=? AND rel='IsA' AND tail=? "
                           "AND status='active'", (tail, head)).fetchone()
        if row:
            return True, {"kind": "contradiction", "head": head, "rel": rel, "tail": tail,
                          "detail": f"IsA 双向环: {head} IsA {tail} 与 {tail} IsA {head} 同时存在"}
    return False, None


# ---------------------------------------------------------------- 热更核心链
def apply_batch(conn, ops, source, inc_epochs=10):
    """规则过滤→矛盾检测→落库; 返回 (result, affected_words)。调用方负责版本与审计。"""
    accepted, rejected, skipped, conflicts = [], [], [], []
    affected = set()
    for op in ops:
        e = {"head": str(op.get("head", "")).strip().lower(),
             "rel": str(op.get("rel", "")).strip(),
             "tail": str(op.get("tail", "")).strip().lower(),
             "weight": float(op.get("weight", 1.0)),
             "op": op.get("op", "add"),
             "version": int(op.get("version", 1)),
             "force": bool(op.get("force", False))}
        if e["op"] == "del":
            accepted.append(e)
            affected.update((e["head"], e["tail"]))
            continue
        ok, reason = cleaning.rule_check(e["head"], e["rel"], e["tail"], weight=e["weight"])
        if not ok:
            rejected.append({**e, "reason": reason})
            continue
        blocked, conflict = detect_conflicts(conn, e, 0)
        if blocked and not op.get("force"):
            conflicts.append(conflict)
            continue
        if blocked and op.get("force"):
            conflicts.append({**conflict, "detail": conflict["detail"] + "(已强制通过)"})
        accepted.append(e)
        affected.update((e["head"], e["tail"]))

    with conn:  # 单事务落库
        for e in accepted:
            if e["op"] == "del":
                cur = conn.execute(
                    "UPDATE edges SET status='removed', removed_by=?, version_removed=?, "
                    "reason=? WHERE head=? AND rel=? AND tail=? AND status='active'",
                    (source, e["version"], "api_delete", e["head"], e["rel"], e["tail"]))
                if cur.rowcount == 0:
                    skipped.append({**e, "reason": "not_found_or_inactive"})
                continue
            cur = conn.execute(
                "INSERT INTO edges(head, rel, tail, weight, source, status, version_added) "
                "VALUES(?,?,?,?,?,'active',?) "
                "ON CONFLICT(head, rel, tail) DO UPDATE SET "
                "status='active', weight=excluded.weight, source=excluded.source, "
                "version_added=excluded.version_added, version_removed=NULL, "
                "removed_by=NULL, reason=NULL",
                (e["head"], e["rel"], e["tail"], e["weight"], source, e["version"]))
            if cur.lastrowid and cur.rowcount == 0:
                skipped.append({**e, "reason": "noop"})
    return {"accepted": accepted, "rejected": rejected, "skipped": skipped,
            "conflicts": conflicts}, affected


def train_and_reindex(affected_words, epochs):
    """IncLoRA 局部训练 + FAISS 局部重建(嵌入未就绪时跳过)。"""
    ret = get_retriever()
    if ret is None:
        return {"skipped": True, "note": "embeddings not ready (run kg_embed.py train/index)"}
    t0 = time.perf_counter()
    new_entities = ret.ensure_entities([w for w in affected_words])
    n_trained = ret.incremental_train(set(affected_words), epochs=epochs)
    ret.persist_vectors()
    return {"skipped": False, "new_entities": len(new_entities),
            "trained_entities": n_trained,
            "seconds": round(time.perf_counter() - t0, 2)}


# ---------------------------------------------------------------- 接口
@app.get("/kg/health")
def health():
    conn = kg.connect(DB_PATH)
    s = kg.db_stats(conn)
    conn.close()
    s["status"] = "ok"
    s["embeddings"] = (EMB_DIR / "rotate.pt").exists()
    return jsonify(s)


@app.get("/kg/facts/<word>")
def facts(word):
    """万物模式 MVP: 本地 kg.facts() 优先, 在线 query_conceptnet() 兜底。"""
    t0 = time.perf_counter()
    word = word.strip().lower()
    conn = kg.connect(DB_PATH)
    rows = kg.facts(conn, word, 50)
    conn.close()
    online_fallback = False
    if not rows and os.environ.get("KG_ONLINE_FALLBACK") == "1":
        try:
            rows = kg.query_conceptnet(word.replace("_", " "), 50)
            online_fallback = True
        except Exception as e:  # noqa: BLE001
            rows, online_fallback = [], f"online_error:{e}"
    return jsonify({"word": word, "facts": rows, "online_fallback": online_fallback,
                    "latency_ms": round((time.perf_counter() - t0) * 1000, 1)})


@app.post("/kg/edges:batch")
def edges_batch():
    body = request.get_json(force=True, silent=True) or {}
    ops = body.get("edges") or []
    source = str(body.get("source", "api"))[:32]
    if not ops:
        return jsonify({"error": "edges required, e.g. "
                        "{\"edges\":[{\"op\":\"add\",\"head\":\"apple\",\"rel\":\"IsA\","
                        "\"tail\":\"fruit\",\"weight\":2.0}]}"}), 400
    inc_epochs = int(body.get("inc_epochs", 10))
    t0 = time.perf_counter()
    version_out = 0
    with _write_lock:
        conn = kg.connect(DB_PATH)
        new_version = kg.get_version(conn) + 1
        for e in ops:
            e["version"] = new_version
        result, affected = apply_batch(conn, ops, source, inc_epochs)
        applied = len(result["accepted"])
        with conn:  # 版本/审计/冲突记录必须落在事务内(否则关闭连接时回滚)
            for c in result["conflicts"]:
                conn.execute("INSERT INTO conflicts(head, rel, tail, kind, detail) "
                             "VALUES(?,?,?,?,?)",
                             (c["head"], c["rel"], c["tail"], c["kind"], c["detail"]))
            if applied:
                kg.bump_version(conn)
                kg.log_audit(conn, "edges:batch",
                             f"applied={applied} rejected={len(result['rejected'])} "
                             f"conflicts={len(result['conflicts'])} source={source}")
        version_out = kg.get_version(conn)
        conn.close()
        inc = train_and_reindex(affected, inc_epochs) if applied else {"skipped": True}
    return jsonify({"version": version_out,
                    "applied": applied, "rejected": result["rejected"][:50],
                    "skipped": result["skipped"][:50],
                    "conflicts": result["conflicts"][:50],
                    "inc_train": inc,
                    "duration_ms": round((time.perf_counter() - t0) * 1000, 1)})


@app.post("/kg/snapshot")
def snapshot():
    t0 = time.perf_counter()
    with _write_lock:
        conn = kg.connect(DB_PATH)
        version = kg.get_version(conn)
        edge_count = conn.execute("SELECT COUNT(*) c FROM edges WHERE status='active' "
                                  "").fetchone()["c"]
        conn.close()
        out = SNAP_DIR / f"v{version}"
        if out.exists():
            shutil.rmtree(out)
        out.mkdir(parents=True)
        src = kg.connect(DB_PATH)
        dst = kg.connect(out / "kg.db")
        src.backup(dst)  # 一致性备份(含 WAL 合并)
        dst.close()
        src.close()
        for f in ("rotate.pt", "faiss.idx", "vectors.npy", "ent_ids.json"):
            if (EMB_DIR / f).exists():
                shutil.copy2(EMB_DIR / f, out / f)
        conn = kg.connect(DB_PATH)
        with conn:
            conn.execute("INSERT OR REPLACE INTO snapshots(version, path, note, edge_count) "
                         "VALUES(?,?,?,?)", (version, str(out), "manual/OTA snapshot",
                                             edge_count))
            kg.log_audit(conn, "snapshot", f"v{version}")
        conn.close()
    return jsonify({"version": version, "path": str(out), "edge_count": edge_count,
                    "duration_ms": round((time.perf_counter() - t0) * 1000, 1)})


@app.post("/kg/rollback/<int:v>")
def rollback(v):
    snap = SNAP_DIR / f"v{v}"
    if not (snap / "kg.db").exists():
        return jsonify({"error": f"snapshot v{v} not found"}), 404
    t0 = time.perf_counter()
    with _write_lock:
        conn = kg.connect(DB_PATH)
        current = kg.get_version(conn)
        conn.close()
        # Windows 下 db 文件被服务端连接占用, 不能 unlink——用 backup API 原地覆盖
        src = kg.connect(snap / "kg.db")
        dst = kg.connect(DB_PATH)
        src.backup(dst)
        src.close()
        dst.close()
        for f in ("rotate.pt", "faiss.idx", "vectors.npy", "ent_ids.json"):
            if (snap / f).exists():
                shutil.copy2(snap / f, EMB_DIR / f)
        conn = kg.connect(DB_PATH)
        with conn:
            restore_version = max(current, v) + 1  # 版本单调递增
            kg.set_meta(conn, "kg_version", restore_version)
            kg.log_audit(conn, "rollback", f"from v{current} to snapshot v{v}")
        conn.close()
        set_retriever(None)  # 下次请求时从恢复后的文件重载内存态
    return jsonify({"rolled_back_to": v, "version": restore_version,
                    "duration_ms": round((time.perf_counter() - t0) * 1000, 1)})


@app.get("/kg/packs/<level>")
def packs(level):
    """按 L0-L5 打包 diff: /kg/packs/L1?since=3&rollout=10&device_id=dev42"""
    level = level.upper()
    if level not in PACK_LEVELS:
        return jsonify({"error": f"level must be one of {sorted(PACK_LEVELS)}"}), 400
    since = request.args.get("since", default=0, type=int)
    rollout = request.args.get("rollout", default=100, type=float)
    device_id = request.args.get("device_id", default="", type=str)
    conn = kg.connect(DB_PATH)
    version = kg.get_version(conn)
    lv_of = {r["word"]: kg.LEVEL_TO_PACK.get(r["level"], "L5") for r in conn.execute(
        "SELECT word, level FROM words")}
    words = [w for w in lv_of if lv_of[w] == level]
    wset = set(words)
    ph = ",".join("?" * len(words))
    rows = conn.execute(
        f"SELECT head, rel, tail, weight, version_added, version_removed, status "
        f"FROM edges WHERE version_added > ? OR (version_removed IS NOT NULL "
        f"AND version_removed > ?)", (since, since)).fetchall()
    conn.close()
    edges = []
    for r in rows:
        if r["head"] not in wset and r["tail"] not in wset:
            continue
        item = {"head": r["head"], "rel": r["rel"], "tail": r["tail"],
                "weight": r["weight"]}
        if r["status"] == "removed" and r["version_added"] <= since:
            item["removed"] = True  # 墓碑: 设备需删除本地边
        elif r["status"] == "removed":
            continue  # 本包周期内加又删, 设备从未见过
        edges.append(item)
    gated = False
    if rollout < 100:  # 灰度: 新词包先推 x% 设备
        if not device_id:
            return jsonify({"level": level, "version": version, "rollout": rollout,
                            "gated": True, "pack": None,
                            "note": "device_id required for rollout gating"}), 200
        h = int(hashlib.md5(f"{device_id}:{level}:{version}".encode()).hexdigest(), 16) % 100
        gated = True
        if h >= rollout:
            return jsonify({"level": level, "version": version, "rollout": rollout,
                            "gated": True, "bucket": h, "pack": None})
    return jsonify({"level": level, "since": since, "version": version,
                    "rollout": rollout, "gated": gated,
                    "word_count": len(wset), "edges": edges, "count": len(edges)})


@app.post("/kg/runtime-consolidate")
def runtime_consolidate():
    """阿海情景记忆周批量 → 语义边。共现 ≥threshold 次的词对提升为 RelatedTo 边。"""
    body = request.get_json(force=True, silent=True) or {}
    memories = body.get("memories") or []
    threshold = int(body.get("threshold", 3))
    if not memories:
        return jsonify({"error": "memories required, e.g. {\"memories\":"
                        "[{\"scene\":\"breakfast\",\"words\":[\"milk\",\"cup\",\"table\"]}]}"}), 400
    from collections import Counter
    co = Counter()
    for m in memories:
        words = sorted({str(w).strip().lower() for w in m.get("words", [])})
        for i in range(len(words)):
            for j in range(i + 1, len(words)):
                co[(words[i], words[j])] += 1
    promoted = [{"op": "add", "head": a, "rel": "RelatedTo", "tail": b,
                 "weight": min(3.0, 1.0 + __import__("math").log2(n)),
                 "source_flag": "consolidated"}
                for (a, b), n in co.items() if n >= threshold]
    if not promoted:
        return jsonify({"promoted": 0, "pairs_considered": len(co),
                        "threshold": threshold})
    t0 = time.perf_counter()
    with _write_lock:
        conn = kg.connect(DB_PATH)
        new_version = kg.get_version(conn) + 1
        for e in promoted:
            e["version"] = new_version
        result, affected = apply_batch(conn, promoted, "consolidated")
        applied = len(result["accepted"])
        with conn:
            for c in result["conflicts"]:
                conn.execute("INSERT INTO conflicts(head, rel, tail, kind, detail) "
                             "VALUES(?,?,?,?,?)",
                             (c["head"], c["rel"], c["tail"], c["kind"], c["detail"]))
            if applied:
                kg.bump_version(conn)
                kg.log_audit(conn, "runtime-consolidate",
                             f"memories={len(memories)} promoted={applied}")
        version_out = kg.get_version(conn)
        conn.close()
        inc = train_and_reindex(affected, 8) if applied else {"skipped": True}
    return jsonify({"promoted": applied, "rejected": result["rejected"][:20],
                    "conflicts": result["conflicts"][:20], "inc_train": inc,
                    "threshold": threshold, "version": version_out,
                    "duration_ms": round((time.perf_counter() - t0) * 1000, 1)})


@app.get("/kg/conflicts")
def conflicts():
    limit = request.args.get("limit", default=100, type=int)
    status = request.args.get("status", default="open", type=str)
    conn = kg.connect(DB_PATH)
    rows = [dict(r) for r in conn.execute(
        "SELECT * FROM conflicts WHERE status=? ORDER BY id DESC LIMIT ?",
        (status, limit))]
    conn.close()
    return jsonify({"status": status, "count": len(rows), "conflicts": rows})


@app.post("/kg/conflicts/<int:cid>/resolve")
def resolve_conflict(cid):
    """人工审入口: {"action": "allow"|"delete"} — allow 则放行该边, delete 则删除。"""
    body = request.get_json(force=True, silent=True) or {}
    action = body.get("action")
    if action not in ("allow", "delete"):
        return jsonify({"error": "action must be allow|delete"}), 400
    with _write_lock:
        conn = kg.connect(DB_PATH)
        row = conn.execute("SELECT * FROM conflicts WHERE id=? AND status='open'",
                           (cid,)).fetchone()
        if not row:
            conn.close()
            return jsonify({"error": "conflict not found or already resolved"}), 404
        new_version = kg.get_version(conn) + 1
        ops = [{"op": "add" if action == "allow" else "del",
                "head": row["head"], "rel": row["rel"], "tail": row["tail"],
                "weight": 1.5, "force": True, "version": new_version}]
        result, affected = apply_batch(conn, ops, "human_review")
        with conn:
            conn.execute("UPDATE conflicts SET status='resolved' WHERE id=?", (cid,))
            kg.bump_version(conn)
            kg.log_audit(conn, "conflict_resolve", f"id={cid} action={action}")
            new_version = kg.get_version(conn)
        conn.close()
        inc = train_and_reindex(affected, 8)
    return jsonify({"resolved": cid, "action": action,
                    "version": new_version, "inc_train": inc})


@app.post("/kg/retrieve")
def retrieve():
    """FAISS 近邻 → PPR 图扩散(多跳) → LLM 重排(可选), 返回带边溯源。"""
    body = request.get_json(force=True, silent=True) or {}
    query = str(body.get("query", "")).strip()
    top = int(body.get("top", 8))
    use_llm = bool(body.get("rerank", False))
    if not query:
        return jsonify({"error": "query required"}), 400
    ret = get_retriever()
    if ret is None:
        return jsonify({"error": "embeddings not ready, run: python kg_embed.py train "
                        "&& python kg_embed.py index"}), 409
    out = ret.retrieve(query, top_k=top, use_llm=use_llm)
    out["e2e_latency_ms"] = out["latency_ms"]
    return jsonify(out)


if __name__ == "__main__":
    port = int(os.environ.get("KG_PORT", 8787))
    log(f"KG server on http://127.0.0.1:{port}  db={DB_PATH}")
    app.run(host="127.0.0.1", port=port, threaded=True, debug=False)
