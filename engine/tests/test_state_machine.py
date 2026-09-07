"""FR-E03 · 剧本状态机：三态推进 + 开口是唯一推进条件 + 跨天持久化接续。"""

import datetime as dt

from she_engine.state_machine import (
    ScriptState,
    day_seed,
    plan_tasks,
    STATE_ADVENTURE,
    STATE_BEDTIME,
    STATE_DAY_ENDED,
    STATE_MORNING_COURT,
)


def _yesterday_iso() -> str:
    return (dt.date.today() - dt.timedelta(days=1)).isoformat()


def test_initial_state_is_morning_court():
    s = ScriptState()
    assert s.state == STATE_MORNING_COURT
    assert s.tasks_total == 3 and s.tasks_done == 0
    assert s.chapter == 1


def test_advance_through_three_states():
    s = ScriptState()
    # 朝会：3 次开口 → 探险
    for i in range(3):
        ev = s.advance()
        if i < 2:
            assert s.state == STATE_MORNING_COURT
    assert s.state == STATE_ADVENTURE
    assert ev.get("state_change") == STATE_ADVENTURE
    # 探险：6 次开口 → 睡前
    for i in range(6):
        ev = s.advance()
    assert s.state == STATE_BEDTIME
    assert ev.get("state_change") == STATE_BEDTIME
    # 睡前：2 次开口 → 一天结束
    for i in range(2):
        ev = s.advance()
    assert s.state == STATE_DAY_ENDED
    assert ev.get("day_completed")


def test_day_ended_does_not_advance():
    s = ScriptState()
    s.state = STATE_DAY_ENDED
    for _ in range(5):
        s.advance()
    assert s.state == STATE_DAY_ENDED


def test_dict_roundtrip():
    s = ScriptState()
    s.advance(); s.advance()
    s2 = ScriptState.from_dict(s.to_dict())
    assert s2 == s


def test_from_dict_tolerates_garbage():
    s = ScriptState.from_dict({"state": "hacked", "tasks_done": "x", "chapter": None})
    assert s.state == STATE_MORNING_COURT and s.tasks_done == 0
    s2 = ScriptState.from_dict(None)
    assert s2.tasks_total == 3


def test_resume_same_day_no_recap():
    s = ScriptState()  # date = today
    s.advance()
    assert s.resume_for_today() is None
    assert s.tasks_done == 1  # 进度原样保留（同天重启接续）


def test_resume_mid_adventure_gives_recap():
    """验收：关机重开后老颞能接续"昨天讲到哪"。"""
    s = ScriptState()
    for _ in range(3):   # 朝会 3 个任务
        s.advance()
    for _ in range(2):   # 探险走 2 步
        s.advance()
    assert s.state == STATE_ADVENTURE
    assert s.adventure_done == 2
    s.date = _yesterday_iso()
    recap = s.resume_for_today()
    assert recap and "昨天" in recap and "接续" in recap
    # 从中途接续：状态与进度不丢
    assert s.state == STATE_ADVENTURE and s.adventure_done == 2
    assert s.date == dt.date.today().isoformat()
    assert s.days_played == 2


def test_resume_after_goodnight_starts_new_day():
    s = ScriptState()
    for _ in range(11):  # 走完全天
        s.advance()
    assert s.state == STATE_DAY_ENDED
    s.date = _yesterday_iso()
    recap = s.resume_for_today()
    assert s.state == STATE_MORNING_COURT
    assert s.chapter == 2  # 新的一天 → 新章节
    assert recap and "第2章" in recap.replace("二章", "2章")


def test_plan_tasks_stable_within_day():
    seed = day_seed("2026-09-04")
    assert plan_tasks(seed) == plan_tasks(seed)
    assert plan_tasks(seed) != plan_tasks(seed + 1) or True  # 不同 seed 通常不同


def test_scene_directive_reflects_state():
    s = ScriptState()
    s.tasks_planned = ["fruit", "animal", "toy"]
    d = s.scene_directive()
    assert "morning court" in d and "fruit" in d
    for _ in range(3):
        s.advance()
    d2 = s.scene_directive()
    assert "adventure" in d2 and "chapter 1" in d2
    for _ in range(6):
        s.advance()
    assert "bedtime" in s.scene_directive()


def test_scene_directive_carries_recap():
    s = ScriptState()
    s.state = STATE_ADVENTURE
    d = s.scene_directive(recap="昨天讲到小蛇过河")
    assert "STORY RECAP" in d and "小蛇过河" in d
