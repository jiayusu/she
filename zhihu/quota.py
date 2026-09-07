#!/usr/bin/env python3
"""quota.py — FR-I07 额度治理。

三用途共用日配额 (默认 1000/天, 保守值, 可配 ZHIHU_DAILY_LIMIT):
  优先级 问题池 > 舆情 > 雷达 (由调度顺序天然实现: 问题池 02:00 先行,
  舆情全天轮询, 雷达每周一次; 配额紧张时 allow() 按用途预留高位额度)。

超额: 自动降级为隔日补跑 (jobs 队列) + 告警 (每用途每天同类最多 1 条, §5 不风暴)。
"""
import json
import time

import db

# 调度上各用途的日预算占比下限: 雷达不得挤占问题池/舆情的保底空间
RESERVE = {"question_pool": 0.45, "sentiment": 0.25, "radar": 0.0}


def used_today(conn, purpose=None):
    if purpose:
        row = conn.execute("SELECT n FROM quota_ledger WHERE day=? AND purpose=?",
                           (db.today(), purpose)).fetchone()
        return row["n"] if row else 0
    row = conn.execute("SELECT COALESCE(SUM(n),0) n FROM quota_ledger WHERE day=?",
                       (db.today(),)).fetchone()
    return row["n"]


def allow(conn, purpose, n=1, limit=None):
    """本用途今日还允许调用 n 次吗? 高优先级用途只受总限额约束,
    低优先级用途需给高优先级留出当日保底空间。"""
    import config
    limit = limit or config.ZHIHU_DAILY_LIMIT
    total = used_today(conn)
    if total + n > limit:
        return False, f"daily_limit_exhausted used={total}/{limit}"
    for higher, share in RESERVE.items():
        if config.PURPOSE_PRIORITY.get(purpose, 9) > config.PURPOSE_PRIORITY[higher]:
            floor = int(limit * share)
            need = floor - used_today(conn, higher)  # 高优先级今日还差的保底量
            if need > 0 and limit - total - n < need:
                return False, (f"reserved_for_{higher} total={total}/{limit} "
                               f"need={need}")
    return True, ""


def record(conn, purpose, n=1):
    """登记一次调用台账 + 埋点。"""
    import config
    with conn:
        conn.execute("INSERT INTO quota_ledger(day, purpose, n) VALUES(?,?,?) "
                     "ON CONFLICT(day, purpose) DO UPDATE SET n = n + excluded.n",
                     (db.today(), purpose, n))
        db.metric(conn, "intel_quota_used", purpose, n,
                  f"used_today={used_today(conn)}/{config.ZHIHU_DAILY_LIMIT}")


def alert(conn, purpose, level, message, dedup="default"):
    """告警入库 (每天每用途同类去重)。返回 True=首次(应通知), False=已静默。"""
    with conn:
        cur = conn.execute(
            "INSERT OR IGNORE INTO alerts(day, purpose, level, message, dedup) "
            "VALUES(?,?,?,?,?)", (db.today(), purpose, level, message[:500], dedup))
    return cur.rowcount > 0


def defer(conn, kind, payload, reason, run_after=None):
    """超额/失败 → 隔日补跑队列。"""
    with conn:
        conn.execute("INSERT INTO jobs(kind, payload, run_after, reason, created_at) "
                     "VALUES(?,?,?,?,?)",
                     (kind, json.dumps(payload, ensure_ascii=False),
                      run_after or db.today(), reason[:200], db.now()))


def due_jobs(conn, kinds):
    ph = ",".join("?" * len(kinds))
    return conn.execute(
        f"SELECT * FROM jobs WHERE status='pending' AND run_after<=? AND kind IN ({ph}) "
        f"ORDER BY id", (db.today(), *kinds)).fetchall()


def finish_job(conn, job_id, ok=True):
    with conn:
        conn.execute("UPDATE jobs SET status=? WHERE id=?",
                     ("done" if ok else "pending", job_id))


def todays_alerts(conn):
    return [dict(r) for r in conn.execute(
        "SELECT * FROM alerts WHERE day=? ORDER BY id", (db.today(),))]
