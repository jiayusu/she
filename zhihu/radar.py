#!/usr/bin/env python3
"""radar.py — FR-I05 家长语言雷达周报。

每周一 9:00 (RADAR_WEEKLY_CRON): 抓英语启蒙话题新问题 → LLM 聚类
焦虑 TOP5 + 新兴方法论词 → 企业微信机器人推送 (每周报附原始样本链接, §8 灌水对策)。
purpose=radar 配额优先级最低: 问题池/舆情不足时自动让路并隔日补跑。
"""
import json
import time
from pathlib import Path

import archive
import config
import db
import llm_client
import notify
import pipeline
import quota
import zhihu_api

PROMPT_PATH = Path(config.ROOT) / "prompts" / "radar_v1.md"
PROMPT_VERSION = "radar_v1"


def _collect(conn, force=False):
    """抓取雷达语料。返回 (items, hot, errors)。"""
    prov = zhihu_api.provider()
    items, hot, errors = [], [], []
    for q in config.RADAR_QUERIES:
        ok, why = quota.allow(conn, "radar")
        if not ok and not force:
            quota.defer(conn, "radar", {"queries_left": config.RADAR_QUERIES}, f"quota: {why}")
            quota.alert(conn, "radar", "warn", f"雷达配额不足降级隔日补跑: {why}", "quota")
            errors.append({"query": q, "error": why, "kind": "quota"})
            break
        try:
            got = prov.search(q, count=config.SEARCH_COUNT)
        except zhihu_api.ZhihuAPIError as e:
            errors.append({"query": q, "error": str(e), "kind": "api"})
            continue
        if prov.name == "zhihu_api":
            quota.record(conn, "radar")
        items.extend(got)
        time.sleep(1)  # 平台限频友好
    try:
        ok, why = quota.allow(conn, "radar")
        if ok or force:
            hot = prov.hot_list(limit=30)
            if prov.name == "zhihu_api":
                quota.record(conn, "radar")
    except zhihu_api.ZhihuAPIError as e:
        errors.append({"query": "hot_list", "error": str(e), "kind": "api"})
    return items, hot, errors


def _cluster(items, hot):
    """LLM 聚类周报。返回 (payload, error)。"""
    if not llm_client.available():
        return None, "LLM 未配置, 周报生成跳过"
    lines = []
    for i, it in enumerate(items[:60]):
        lines.append(f"[{i}] {it['title']}\n    {((it.get('text') or '')[:120]).strip()}")
    hot_titles = "\n".join(f"    热榜: {h['title']}" for h in hot[:15] if h.get("title"))
    try:
        raw = llm_client._chat([
            {"role": "system", "content": PROMPT_PATH.read_text(encoding="utf-8")},
            {"role": "user",
             "content": f"本周语料 {len(items)} 条 (标题+摘录):\n" + "\n".join(lines)
             + (f"\n\n知乎热榜参考:\n{hot_titles}" if hot_titles else "")
             + "\n按提示词契约输出 JSON。"}], max_tokens=4000)
    except llm_client.LLMUnavailable as e:
        return None, str(e)
    payload = llm_client.extract_json(raw)
    if not isinstance(payload, dict) or not payload.get("anxiety_top5"):
        return None, "radar_output_unparseable"
    top5 = payload["anxiety_top5"][:5]
    for t in top5:
        t["sample_titles"] = [str(x)[:80] for x in (t.get("sample_titles") or [])[:3]]
        t["sample_links"] = [str(x)[:200] for x in (t.get("sample_links") or [])[:3]]
        try:
            t["heat"] = min(100, max(0, int(t.get("heat") or 0)))
        except (TypeError, ValueError):
            t["heat"] = 0
    payload["anxiety_top5"] = top5
    payload["emerging_methods"] = (payload.get("emerging_methods") or [])[:5]
    payload["suggested_actions"] = [str(x)[:80] for x in
                                    (payload.get("suggested_actions") or [])[:3]]
    return payload, None


def _markdown(week, payload, n_samples):
    lines = [f"**🧭 家长语言雷达周报 {week}**",
             f"> 语料样本 {n_samples} 条 | 原始样本链接已附, 供人工复核 (防热榜灌水失真)"]
    for i, t in enumerate(payload.get("anxiety_top5", []), 1):
        links = " ".join(f"[{j + 1}]({u})" for j, u in enumerate(t.get("sample_links", [])))
        lines.append(f"\n**TOP{i} {t.get('theme', '')}** (热度 {t.get('heat', 0)})")
        lines.append(f"> {t.get('summary', '')}")
        if links:
            lines.append(f"> 样本: {links}")
    methods = payload.get("emerging_methods") or []
    if methods:
        lines.append("\n**新兴方法论词**")
        for m in methods:
            lines.append(f"> `{m.get('word', '')}` — {m.get('why', '')}")
    acts = payload.get("suggested_actions") or []
    if acts:
        lines.append("\n**建议动作**")
        lines.extend(f"> {a}" for a in acts)
    return "\n".join(lines)


def run(conn, force=False):
    """生成并推送本周雷达周报。返回 {ok, ...}。"""
    week = db.iso_week()
    items, hot, errors = _collect(conn, force=force)
    if items:
        archive.write_raw("radar", {"week": week, "fetched_at": db.now(),
                                    "items": items, "hot": hot})
    if not items:
        msg = f"雷达语料为空, 本周周报未生成 errors={errors}"
        quota.alert(conn, "radar", "error", msg, "empty")
        return {"ok": False, "error": msg, "errors": errors}

    payload, err = _cluster(items, hot)
    if payload is None:
        quota.alert(conn, "radar", "error", f"周报生成失败: {err}", "llm")
        return {"ok": False, "error": err, "errors": errors}

    md = _markdown(week, payload, len(items))
    with conn:
        cur = conn.execute(
            "INSERT INTO reports(week, kind, payload, markdown, status, sample_count, "
            "created_at) VALUES(?,?,?,?,?,?,?)",
            (week, "radar", json.dumps(payload, ensure_ascii=False), md, "pending",
             len(items), db.now()))
        report_id = cur.lastrowid
    out = notify.send_markdown(md, tag="radar")
    # outbox 落盘是可接受的降级送达 (企微未配置), 不算失败
    delivered = out["ok"] or out.get("via") in ("outbox", "outbox_fallback")
    with conn:
        conn.execute("UPDATE reports SET status=?, sent_at=? WHERE id=?",
                     ("sent" if delivered else "failed",
                      db.now() if delivered else None, report_id))
        db.metric(conn, "intel_report_sent", "radar", 1 if delivered else 0,
                  f"report_id={report_id} week={week}")
    return {"ok": delivered, "report_id": report_id, "week": week,
            "samples": len(items), "notify": out, "errors": errors,
            "payload": payload}


def latest(conn):
    row = conn.execute("SELECT * FROM reports ORDER BY id DESC LIMIT 1").fetchone()
    return dict(row) if row else None
