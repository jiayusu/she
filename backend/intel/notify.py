#!/usr/bin/env python3
"""notify.py — 推送层: 企业微信机器人 (FR-I05/06) + 日报汇总 (§5 不告警风暴)。

WECOM_WEBHOOK 未配置时: 消息落 outbox/ 待人工转发, 不算失败。
"""
import json
import time
from pathlib import Path

import config
import db
import quota

ROOT = Path(__file__).resolve().parent


def _outbox(text):
    config.OUTBOX_DIR.mkdir(parents=True, exist_ok=True)
    p = config.OUTBOX_DIR / f"{time.strftime('%Y%m%d_%H%M%S')}.md"
    p.write_text(text, encoding="utf-8")
    return str(p.relative_to(config.ROOT))


def send_markdown(text, tag="notify"):
    """企业微信 markdown 消息。webhook 未配置→outbox。返回 {ok, via, path?}"""
    if not config.WECOM_WEBHOOK:
        return {"ok": False, "via": "outbox", "path": _outbox(text),
                "note": "WECOM_WEBHOOK 未配置, 消息已落盘 outbox"}
    import requests
    try:
        r = requests.post(config.WECOM_WEBHOOK, timeout=15, json={
            "msgtype": "markdown",
            "markdown": {"content": text[:4000]}})
        r.raise_for_status()
        body = r.json()
        ok = body.get("errcode") == 0
        if not ok:
            return {"ok": False, "via": "wecom", "error": str(body)}
        return {"ok": True, "via": "wecom"}
    except Exception as e:  # noqa: BLE001 — 推送失败不抛, 落盘兜底
        p = _outbox(text)
        return {"ok": False, "via": "outbox_fallback", "path": p, "error": str(e)}


def daily_digest(conn):
    """日报汇总 (§5): 单用途故障不单独轰炸, 每日一条汇总到群。"""
    day = db.today()
    alerts = quota.todays_alerts(conn)
    m = dict(conn.execute(
        "SELECT event, COALESCE(SUM(value),0) v FROM metrics WHERE ts LIKE ? "
        "GROUP BY event", (day + "%",)).fetchall())
    neg = conn.execute("SELECT COUNT(*) c FROM sentiment WHERE sentiment='negative' "
                       "AND created_at LIKE ?", (day + "%",)).fetchone()["c"]
    lines = [f"**数据情报日报 {day}**",
             f"> 抓取 intel_fetched: {m.get('intel_fetched', 0):.0f} 条 | "
             f"结构化成功: {m.get('intel_structured', 0):.0f} 条 | "
             f"审核通过: {m.get('intel_approved', 0):.0f} 条 | "
             f"负面舆情: {neg} 条",
             f"> 额度: {quota.used_today(conn)}/{config.ZHIHU_DAILY_LIMIT}"]
    if alerts:
        lines.append("**告警汇总** (已按天/用途去重):")
        for a in alerts:
            lines.append(f"> [{a['level']}] {a['purpose']}: {a['message']}")
    else:
        lines.append("> 告警: 无")
    jobs = conn.execute("SELECT COUNT(*) c FROM jobs WHERE status='pending'").fetchone()["c"]
    if jobs:
        lines.append(f"> 待补跑任务: {jobs} 个 (隔日自动执行)")
    return send_markdown("\n".join(lines), tag="digest")
