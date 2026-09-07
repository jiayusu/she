"""scheduler: cron 解析与到期判定。"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scheduler import due, parse_cron


def test_parse_cron():
    assert parse_cron("daily 02:00") == ("daily", "02:00")
    assert parse_cron("mon 09:00") == ("mon", "09:00")
    assert parse_cron("every 30 min") == ("interval", 30)


def test_daily_due_once_per_day(conn):
    now = time.strptime("2026-09-04 08:00:00", "%Y-%m-%d %H:%M:%S")
    is_due, slot = due(conn, "fetch", "daily 02:00", now=now)
    assert is_due and slot == "2026-09-04 02:00"
    from db import set_meta
    set_meta(conn, "scheduler.fetch", slot)
    is_due, _ = due(conn, "fetch", "daily 02:00", now=now)
    assert not is_due  # 当天已跑过, 重启不重复


def test_not_yet_time(conn):
    now = time.strptime("2026-09-04 01:00:00", "%Y-%m-%d %H:%M:%S")
    is_due, _ = due(conn, "fetch", "daily 02:00", now=now)
    assert not is_due


def test_weekly_only_on_monday(conn):
    mon = time.strptime("2026-09-07 09:00:00", "%Y-%m-%d %H:%M:%S")  # 周一
    tue = time.strptime("2026-09-08 09:00:00", "%Y-%m-%d %H:%M:%S")
    assert due(conn, "radar", "mon 09:00", now=mon)[0] is True
    assert due(conn, "radar", "mon 09:00", now=tue)[0] is False
