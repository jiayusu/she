"""FR-I07: 额度治理 — 共用日配额/优先级/超额降级隔日补跑/告警去重。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import quota


def test_allow_within_limit(conn):
    ok, why = quota.allow(conn, "question_pool", n=5)
    assert ok, why
    quota.record(conn, "question_pool", 5)
    assert quota.used_today(conn) == 5


def test_deny_when_exhausted_and_defer_job(conn, env):
    ok, why = quota.allow(conn, "question_pool", n=100, limit=10)
    assert not ok and "daily_limit" in why
    quota.defer(conn, "question_pool", {"queries_left": ["x"]}, why)
    jobs = quota.due_jobs(conn, ("question_pool", "sentiment", "radar"))
    assert len(jobs) == 1 and jobs[0]["kind"] == "question_pool"
    quota.finish_job(conn, jobs[0]["id"])
    assert quota.due_jobs(conn, ("question_pool",)) == []


def test_priority_reserve_protects_question_pool(conn, env):
    """雷达(低优)不得吃掉问题池(高优)的保底空间。"""
    limit = 100
    quota.record(conn, "question_pool", 30)   # 问题池已用 30, 保底 45 → 还需 15
    quota.record(conn, "sentiment", 30)
    quota.record(conn, "radar", 30)           # 已用 90/100
    ok, why = quota.allow(conn, "radar", n=1, limit=limit)
    assert not ok and "reserved_for_question_pool" in why
    ok, _ = quota.allow(conn, "question_pool", n=1, limit=limit)  # 高优仍可走
    assert ok


def test_alert_dedup_per_day_purpose(conn):
    assert quota.alert(conn, "sentiment", "warn", "a", "quota") is True
    assert quota.alert(conn, "sentiment", "warn", "a again", "quota") is False
    assert quota.alert(conn, "radar", "warn", "a", "quota") is True  # 不同用途不互相吞
    assert len(quota.todays_alerts(conn)) == 2
