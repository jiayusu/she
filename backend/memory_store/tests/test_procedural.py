"""FR-M07 程序性库: 触发-动作模式, 20:30 提醒准时率 100%, 防重复触发。"""
import time
from datetime import datetime

import pytest


def T(s):
    return datetime.fromisoformat(s).timestamp()


@pytest.fixture()
def task(svc):
    return svc.procedural.add(
        "朝会提醒", {"type": "time", "time": "20:30", "repeat": "daily"},
        {"type": "remind", "text": "20:30 朝会开始啦"})


def test_2030_exact_on_time(svc, task):
    """20:30:00 准时到期; 20:29:59 未到期 → 准时率 100%。"""
    assert svc.procedural.due(ts=T("2026-09-04T20:29:59")) == []
    due = svc.procedural.due(ts=T("2026-09-04T20:30:00"))
    assert [t["name"] for t in due] == ["朝会提醒"]


def test_no_double_fire_same_day(svc, task):
    pid = task["id"]
    assert svc.procedural.due(ts=T("2026-09-04T20:30:00"))
    svc.procedural.mark_fired(pid, ts=T("2026-09-04T20:30:01"))
    assert svc.procedural.due(ts=T("2026-09-04T20:31:00")) == []
    assert svc.procedural.due(ts=T("2026-09-04T23:59:00")) == []


def test_fires_again_next_day(svc, task):
    pid = task["id"]
    svc.procedural.mark_fired(pid, ts=T("2026-09-04T20:30:01"))
    assert len(svc.procedural.due(ts=T("2026-09-05T20:30:00"))) == 1


def test_weekly_summary_trigger(svc):
    """周总结: 每周日(weekly days=[6]) 19:00。"""
    svc.procedural.add("周总结", {"type": "time", "time": "19:00",
                                  "repeat": "weekly", "days": [6]},
                       {"type": "summary", "text": "本周学词报告"})
    # 2026-09-04 是周五(weekday=4), 09-06 是周日
    assert svc.procedural.due(ts=T("2026-09-04T19:30:00")) == []
    assert len(svc.procedural.due(ts=T("2026-09-06T19:00:00"))) == 1


def test_once_trigger(svc):
    svc.procedural.add("单次提醒", {"type": "once", "at": "2026-09-10T09:00:00"},
                       {"type": "remind", "text": "牙医预约"})
    assert svc.procedural.due(ts=T("2026-09-10T08:59:00")) == []
    assert len(svc.procedural.due(ts=T("2026-09-10T09:00:00"))) == 1
    pid = svc.procedural.due(ts=T("2026-09-10T09:00:00"))[0]["id"]
    svc.procedural.mark_fired(pid)
    assert svc.procedural.due(ts=T("2026-09-10T10:00:00")) == []  # 单次不重复


def test_scene_trigger(svc):
    svc.procedural.add("朝会点名", {"type": "scene", "scene": "朝会"},
                       {"type": "greet", "text": "点到名的请开口"})
    assert svc.procedural.due(scene="朝会")[0]["name"] == "朝会点名"
    assert svc.procedural.due(scene="探险") == []
    assert svc.procedural.due(ts=T("2026-09-04T20:30:00")) == []  # 无场景不触发


def test_disabled_task_not_due(svc, task):
    svc.procedural.set_enabled(task["id"], on=False)
    assert svc.procedural.due(ts=T("2026-09-04T20:30:00")) == []


def test_invalid_trigger_rejected(svc):
    with pytest.raises(ValueError):
        svc.procedural.add("坏任务", {"type": "time", "time": "25:00",
                                      "repeat": "daily"}, {"type": "remind"})
    with pytest.raises(ValueError):
        svc.procedural.add("坏任务", {"type": "wat"}, {"type": "remind"})


def test_capacity_500_eviction(svc):
    for i in range(505):
        svc.procedural.add(f"t-{i}", {"type": "scene", "scene": f"sc-{i}"},
                           {"type": "noop"})
    assert svc.procedural.count() == 500
    names = {t["name"] for t in svc.procedural.list()}
    assert "t-0" not in names and "t-504" in names  # 最旧被淘汰
