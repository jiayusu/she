#!/usr/bin/env python3
"""sentiment.py — FR-I06 舆情监控。

品牌词+竞品词+品类词轮询 (默认 30min, 保证负面 2h 内送达):
  搜索 → 原始归档 → 新内容(未见过的 content_id) → LLM 倾向分类 →
  高置信负面即时推送企业微信, 全量入 sentiment 表供 /intel/sentiment 查询。
purpose=sentiment 受配额治理, 不足时降级隔日补跑 (FR-I07)。
"""
from pathlib import Path

import archive
import config
import db
import llm_client
import notify
import pipeline
import quota
import zhihu_api

PROMPT_PATH = Path(config.ROOT) / "prompts" / "sentiment_v1.md"
PROMPT_VERSION = "sentiment_v1"
PUSH_CONFIDENCE = 0.7  # 高置信才即时推送, 低置信入表人工看


def _classify(conn, items):
    """LLM 倾向分类。返回 {idx: {sentiment, issue_tag, confidence}}; LLM 不可用返回 {}。"""
    if not items or not llm_client.available():
        return {}
    lines = "\n\n".join(
        f"[{i}] 监控命中: {it['watchword']}\n标题: {it['title']}\n摘录: {it['excerpt'] or '(无)'}"
        for i, it in enumerate(items))
    try:
        raw = llm_client._chat([
            {"role": "system", "content": PROMPT_PATH.read_text(encoding="utf-8")},
            {"role": "user", "content": f"待分类 {len(items)} 条:\n{lines}\n只输出 JSON。"}])
    except llm_client.LLMUnavailable:
        return {}
    data = llm_client.extract_json(raw) or {}
    out = {}
    for d in data.get("items") or []:
        if isinstance(d, dict) and isinstance(d.get("idx"), int):
            sent = d.get("sentiment")
            out[d["idx"]] = {"sentiment": sent if sent in ("negative", "neutral", "positive")
                             else "unknown",
                             "issue_tag": str(d.get("issue_tag") or "")[:40],
                             "confidence": max(0.0, min(1.0, float(d.get("confidence") or 0)))}
    return out


def _store(conn, word, kind, items):
    """新内容入库 (content_id 去重, 跨轮不重复告警)。返回新条目列表。"""
    fresh = []
    with conn:
        for it in items:
            cur = conn.execute(
                "INSERT OR IGNORE INTO sentiment(watchword, watchword_kind, content_id, "
                "title, url, excerpt, vote_up, comment_count, edit_time, raw_path, "
                "created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (word, kind, it["content_id"], it["title"], it.get("url"),
                 (it.get("text") or "")[:200], it.get("vote_up", 0),
                 it.get("comment_count", 0), it.get("edit_time", 0),
                 it.get("raw_path"), db.now()))
            if cur.rowcount:
                fresh.append(it)
    return fresh


def _update_sentiment(conn, item, cls):
    with conn:
        conn.execute(
            "UPDATE sentiment SET sentiment=?, issue_tag=?, confidence=? WHERE content_id=?",
            (cls.get("sentiment", "unknown"), cls.get("issue_tag", ""),
             cls.get("confidence", 0), item["content_id"]))


def _push_negative(conn, item, cls):
    kind_cn = {"brand": "品牌", "competitor": "竞品", "category": "品类"}.get(
        item["_kind"], item["_kind"])
    text = (f"**🔴 负面舆情告警** ({kind_cn}词: {item['_watchword']})\n"
            f"> **{item['title']}**\n"
            f"> 问题域: {cls.get('issue_tag') or 'other'} | 置信度: "
            f"{cls.get('confidence', 0):.2f}\n"
            f"> [查看原文]({item.get('url')})\n"
            f"> SLA: 2小时内响应。详情: GET /intel/sentiment?sentiment=negative")
    out = notify.send_markdown(text, tag="sentiment")
    with conn:
        conn.execute("UPDATE sentiment SET pushed=1 WHERE content_id=?",
                     (item["content_id"],))
    return out


def poll(conn, force=False):
    """一轮监控。返回统计。供调度器与 POST /intel/sentiment/poll 使用。"""
    ok, why = quota.allow(conn, "sentiment")
    if not ok and not force:
        quota.defer(conn, "sentiment", {}, f"quota: {why}")
        quota.alert(conn, "sentiment", "warn", f"配额不足降级隔日补跑: {why}", "quota")
        return {"skipped": True, "reason": why}
    prov = zhihu_api.provider()
    stats = {"checked": 0, "fresh": 0, "negative": 0, "pushed": 0, "errors": []}
    for word, kind in config.WATCHWORDS:
        try:
            items = prov.search(word, count=config.SEARCH_COUNT)
        except zhihu_api.ZhihuAPIError as e:
            stats["errors"].append(f"{word}: code={e.code}")
            quota.alert(conn, "sentiment", "error", f"监控词 {word} 搜索失败 code={e.code}",
                        "api")
            continue
        if prov.name == "zhihu_api":
            quota.record(conn, "sentiment")
        stats["checked"] += 1
        raw_path = archive.write_raw("sentiment", {"watchword": word, "kind": kind,
                                                   "items": items})
        for it in items:
            it["_watchword"], it["_kind"], it["raw_path"] = word, kind, raw_path
        fresh = _store(conn, word, kind, items)
        stats["fresh"] += len(fresh)

    # 未分类的 (新 + 历史 unknown) 统一分类
    pending = [dict(r) for r in conn.execute(
        "SELECT * FROM sentiment WHERE sentiment='unknown' ORDER BY id DESC LIMIT 30")]
    cls = _classify(conn, pending)
    for i, item in enumerate(pending):
        c = cls.get(i)
        if not c:
            continue
        _update_sentiment(conn, item, c)
        if c["sentiment"] == "negative" and c["confidence"] >= PUSH_CONFIDENCE \
                and config.NEGATIVE_PUSH:
            item["_watchword"], item["_kind"] = item["watchword"], item["watchword_kind"]
            _push_negative(conn, item, c)
            stats["pushed"] += 1
        if c["sentiment"] == "negative":
            stats["negative"] += 1
    if stats["fresh"]:
        db.metric(conn, "intel_fetched", "sentiment", stats["fresh"],
                  f"watchwords={stats['checked']}")
    return stats


def recent(conn, sentiment=None, kind=None, limit=100, since_hours=None):
    conds, args = [], []
    if sentiment:
        conds.append("sentiment=?")
        args.append(sentiment)
    if kind:
        conds.append("watchword_kind=?")
        args.append(kind)
    if since_hours:
        import time as _t
        cut = _t.strftime("%Y-%m-%d %H:%M:%S", _t.localtime(_t.time() - since_hours * 3600))
        conds.append("created_at >= ?")
        args.append(cut)
    where = f"WHERE {' AND '.join(conds)}" if conds else ""
    rows = conn.execute(
        f"SELECT * FROM sentiment {where} ORDER BY id DESC LIMIT ?", (*args, limit)).fetchall()
    return [dict(r) for r in rows]
