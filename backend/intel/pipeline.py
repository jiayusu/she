#!/usr/bin/env python3
"""pipeline.py — 问题池管线: 采集(FR-I01) → 质量排序+去重(FR-I02) → LLM结构化(FR-I03)。

用途 purpose=question_pool, 受 quota 治理; 单用途失败不影响其他用途 (§5):
配额耗尽→隔日补跑队列; LLM 不可用→条目挂起 pending_struct 下轮重试;
搜索接口故障→告警一条, 其他用途照常。
"""
import json
import math
import re
import time
from pathlib import Path

import archive
import config
import db
import llm_client
import quota
import zhihu_api

PROMPT_PATH = Path(config.ROOT) / "prompts" / "structure_v1.md"
PROMPT_VERSION = "structure_v1"

# kg_edges 校验: 对齐 kb/cleaning.py 的词表与形态 (英文 snake_case, ≤3 词)
_EDGE_RE = re.compile(r"^[a-z][a-z_]{0,39}$")


# ---------------------------------------------------------------- FR-I02 排序/去重
def rank_score(item):
    """互动量代理加权 (API 不返回回答数/浏览量): 赞同×1.0 + 评论×0.6 + 权威加成。"""
    a = {"1": 0.0, "2": 0.1, "3": 0.2, "4": 0.3}.get(str(item.get("authority")), 0.0)
    return (config.RANK_W_VOTE * math.log1p(max(0, item.get("vote_up") or 0))
            + config.RANK_W_COMMENT * math.log1p(max(0, item.get("comment_count") or 0))
            + config.RANK_W_AUTHORITY * a)


def title_similarity(a, b):
    """标题相似度: 归一化后 difflib 序列比。对"同款标题+尾巴"的灌水变体稳定。"""
    from difflib import SequenceMatcher
    def norm(s):
        return re.sub(r"[\s？?！!，,。.的了吗呢吧呀哦]", "", (s or "").lower())
    na, nb = norm(a), norm(b)
    if not na or not nb:
        return 0.0
    if na == nb:
        return 1.0
    return SequenceMatcher(None, na, nb).ratio()


def dedup(items, threshold=None, against=()):
    """标题相似度 > threshold 合并, 保留分高者。
    items: [{title, score, ...}]; against: 库内已有 [(id, title)] 跨周去重。
    返回 (kept_items, merged_ids, dup_count)。"""
    threshold = threshold or config.DEDUP_SIM_THRESHOLD
    ranked = sorted(items, key=lambda x: -x.get("score", 0))
    kept = []
    merged_ids = []
    dups = 0
    for it in ranked:
        hit = next((k for k in kept
                    if title_similarity(it["title"], k["title"]) > threshold), None)
        if hit is None:
            hit_id = next((cid for cid, t in against
                           if title_similarity(it["title"], t) > threshold), None)
            if hit_id is not None:
                it["merged_into"] = hit_id
                merged_ids.append(it)
                dups += 1
                continue
            kept.append(it)
        else:
            it["merged_into"] = hit.get("_rowid")  # 批内并入, 落库时回填
            merged_ids.append(it)
            dups += 1
    return kept, merged_ids, dups


# ---------------------------------------------------------------- §8 敏感词前置
def sensitive_hit(*texts):
    blob = " ".join(t or "" for t in texts)
    return next((w for w in config.SENSITIVE_WORDS if w and w in blob), None)


# ---------------------------------------------------------------- FR-I01 采集
def fetch_and_store(conn, purpose="question_pool", queries=None, on_quota_deny="defer"):
    """多查询词采集 → 原始归档 → 排序 → 去重 → 落库。返回统计 dict。"""
    queries = queries or config.QUESTION_QUERIES
    prov = zhihu_api.provider()
    fetched_raw, items, errors = 0, [], []
    for q in queries:
        ok, why = quota.allow(conn, purpose)
        if not ok:
            if on_quota_deny == "defer":
                quota.defer(conn, purpose, {"queries_left": queries[queries.index(q):]},
                            f"quota: {why}")
                quota.alert(conn, purpose, "warn", f"配额不足降级隔日补跑: {why}", "quota")
            errors.append({"query": q, "error": why, "kind": "quota"})
            break
        try:
            got = prov.search(q, count=config.SEARCH_COUNT)
        except zhihu_api.ZhihuAPIError as e:
            quota.alert(conn, purpose, "error", f"{q} 搜索失败 code={e.code}", "api")
            errors.append({"query": q, "error": str(e), "kind": "api"})
            continue  # 单查询失败不中断整批 (§5)
        if prov.name == "zhihu_api":
            quota.record(conn, purpose)  # 台账只记真实平台调用 (FR-I07 实际调用口径)
        fetched_raw += len(got)
        raw_path = archive.write_raw(purpose, {"query": q, "fetched_at": db.now(),
                                               "provider": prov.name, "items": got})
        for it in got:
            it["score"] = rank_score(it)
            it["raw_path"] = raw_path
        items.extend(got)

    if not items:
        return {"fetched": 0, "inserted": 0, "dups": 0, "errors": errors}

    # FR-I02: 批内排序去重 + 对库内本周已有标题去重
    week = db.iso_week()
    against = [(r["id"], r["title"]) for r in conn.execute(
        "SELECT id, title FROM candidates WHERE week=? AND merged_into IS NULL", (week,))]
    kept, merged, dup_count = dedup(items, against=against)
    batch_id = f"{purpose}-{time.strftime('%Y%m%d%H%M%S')}"
    inserted = 0
    rowids = {}
    with conn:
        for it in kept:
            hit = sensitive_hit(it.get("title"), (it.get("text") or "")[:300])
            cur = conn.execute(
                "INSERT OR IGNORE INTO candidates(batch_id, content_id, content_type, title, "
                "url, excerpt, vote_up, comment_count, authority, score, week, status, "
                "raw_path, created_at, updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (batch_id, it["content_id"], it.get("content_type"), it["title"],
                 it.get("url"), (it.get("text") or "")[:200], it.get("vote_up", 0),
                 it.get("comment_count", 0), it.get("authority"), it.get("score", 0),
                 week, "pending_struct", it.get("raw_path"), db.now(), db.now()))
            if cur.rowcount:
                inserted += 1
                rowids[it["content_id"]] = cur.lastrowid
    db.metric(conn, "intel_fetched", purpose, fetched_raw,
              f"inserted={inserted} dups={dup_count} queries={len(queries)}")
    return {"fetched": fetched_raw, "inserted": inserted, "dups": dup_count,
            "dup_rate": round(dup_count / max(1, fetched_raw), 3),
            "batch_id": batch_id, "errors": errors}


# ---------------------------------------------------------------- FR-I03 结构化
def _prompt():
    return PROMPT_PATH.read_text(encoding="utf-8")


def _fmt_item(i, r):
    return (f"[{i}] 标题: {r['title']}\n"
            f"摘要: {r['excerpt'] or '(无)'}\n"
            f"互动: 赞同{r['vote_up']} 评论{r['comment_count']}")


def _clamp_edges(edges):
    out = []
    for e in edges or []:
        if not isinstance(e, dict):
            continue
        head, rel, tail = str(e.get("head", "")).strip(), str(e.get("rel", "")).strip(), \
            str(e.get("tail", "")).strip()
        if rel not in config.KG_EDGE_RELS:
            continue
        if not (_EDGE_RE.match(head) and _EDGE_RE.match(tail)) or head == tail:
            continue
        out.append({"head": head, "rel": rel, "tail": tail})
    return out[:4]


def structure_batch(conn, rows, model=None, fake=None):
    """一批候选 → LLM 结构化 → 校验落库。fake: 测试桩, 签名同内部 _chat。
    返回 {ok, failed, filtered}。"""
    items = "\n\n".join(_fmt_item(i, r) for i, r in enumerate(rows))
    user = (f"待结构化条目 {len(rows)} 条:\n{items}\n"
            f"按提示词契约输出 JSON 数组, 每条输入一个元素。")
    try:
        if fake is not None:
            raw = fake([{"role": "system", "content": _prompt()},
                        {"role": "user", "content": user}])
        else:
            raw = llm_client._chat([{"role": "system", "content": _prompt()},
                                    {"role": "user", "content": user}])
    except llm_client.LLMUnavailable as e:
        return {"ok": 0, "failed": len(rows), "filtered": 0, "error": str(e)}

    data = llm_client.extract_json(raw, container="array")
    if not isinstance(data, list):
        data = (llm_client.extract_json(raw) or {}).get("items")
    if not isinstance(data, list):
        return {"ok": 0, "failed": len(rows), "filtered": 0, "error": "unparseable_output"}

    ok = failed = filtered = 0
    by_idx = {}
    for d in data:
        if isinstance(d, dict) and isinstance(d.get("idx"), int):
            by_idx[d["idx"]] = d
    weight_by_diff = lambda diff: round(max(1.0, 3.5 - 0.5 * int(diff or 3)), 2)  # noqa: E731
    with conn:
        for i, r in enumerate(rows):
            d = by_idx.get(i)
            if not d:
                failed += 1
                continue
            if d.get("sensitive") or sensitive_hit(r["title"], d.get("fact", "")):
                conn.execute("UPDATE candidates SET status='filtered', updated_at=? "
                             "WHERE id=?", (db.now(), r["id"]))
                filtered += 1
                continue
            try:
                difficulty = min(5, max(1, int(d.get("difficulty") or 3)))
            except (TypeError, ValueError):
                difficulty = 3
            edges = _clamp_edges(d.get("kg_edges"))
            for e in edges:
                e["weight"] = weight_by_diff(difficulty)
            conn.execute(
                "UPDATE candidates SET status='structured', phenomenon=?, child_question=?, "
                "fact=?, difficulty=?, related_objects=?, kg_edges=?, structure_model=?, "
                "prompt_version=?, updated_at=? WHERE id=?",
                (str(d.get("phenomenon") or "")[:200], str(d.get("child_question") or "")[:120],
                 str(d.get("fact") or "")[:300], difficulty,
                 json.dumps([str(x)[:60] for x in (d.get("related_objects") or [])[:6]],
                            ensure_ascii=False),
                 json.dumps(edges, ensure_ascii=False),
                 model or config.LLM_MODEL, PROMPT_VERSION, db.now(), r["id"]))
            ok += 1
    db.metric(conn, "intel_structured", "question_pool", ok,
              f"failed={failed} filtered={filtered} ok_rate={ok / max(1, ok + failed):.2f}")
    return {"ok": ok, "failed": failed, "filtered": filtered}


def structure_pending(conn, limit=None, fake=None):
    """对 pending_struct 按分数取前 limit 条结构化 (PRD: 每周 top-20)。"""
    limit = limit or config.FETCH_TOP_N
    rows = conn.execute(
        "SELECT * FROM candidates WHERE status='pending_struct' "
        "ORDER BY score DESC, id LIMIT ?", (limit,)).fetchall()
    if not rows:
        return {"ok": 0, "failed": 0, "filtered": 0, "note": "nothing pending"}
    total = {"ok": 0, "failed": 0, "filtered": 0}
    for i in range(0, len(rows), config.STRUCT_BATCH):
        out = structure_batch(conn, rows[i:i + config.STRUCT_BATCH], fake=fake)
        for k in ("ok", "failed", "filtered"):
            total[k] += out.get(k, 0)
        if out.get("error"):
            total["error"] = out["error"]
            break  # LLM 不可用: 剩余条目保持 pending 下轮重试
    return total


def weekly_candidates(conn, week=None, status=None, include_filtered=False):
    """审核工作台数据源: 本周候选 (merged 过滤后)。"""
    week = week or db.iso_week()
    conds, args = ["week=?", "merged_into IS NULL"], [week]
    if status:
        conds.append("status=?")
        args.append(status)
    elif not include_filtered:
        conds.append("status != 'filtered'")
    rows = conn.execute(
        f"SELECT * FROM candidates WHERE {' AND '.join(conds)} "
        f"ORDER BY score DESC, id", args).fetchall()
    return [dict(r) for r in rows]
