"""FR-M09 容量管理: 工作记忆 LRU 溢出到情景库; 显著性缓冲满最低分降级(不清除)。"""
import time

from memstore import Config, MemoryService
from conftest import make_svc


def test_working_lru_overflow_to_episodic(svc):
    """工作记忆满 10 条 → 第 11 条起按 LRU(最旧)溢出到情景库, 不清除。"""
    now = time.time()
    for i in range(12):
        out = svc.working_push("s-cap", f"turn-{i}", ts=now + i)
    turns = svc.working.items("s-cap")
    assert len(turns) == 10
    assert turns[0]["text"] == "turn-2"          # 最旧两条已逐出
    assert turns[-1]["text"] == "turn-11"
    rows = [r for r in svc.episodic.all_rows() if r["kind"] == "overflow"]
    assert len(rows) == 2                        # 溢出两条进情景库
    assert {r["utterance"] for r in rows} == {"turn-0", "turn-1"}


def test_salience_buffer_demote_lowest_not_clear(tmp_path):
    """显著性缓冲满 → 最低分降入情景库(不清除), 缓冲维持容量。"""
    small: MemoryService = make_svc(tmp_path, salience_cap=3)
    try:
        for i in range(5):
            small.write_episode(utterance=f"sb-{i}", salience=0.9 - i * 0.1,
                                mirror_salience=True)
        assert small.salience.count() == 3                    # 容量受控
        sals = {round(it["salience"], 2) for it in small.salience.items(limit=10)}
        assert sals == {0.9, 0.8, 0.5}                        # 最低分 0.7/0.6 已降级
        contents = {r["utterance"] for r in small.episodic.all_rows()}
        for i in range(5):                                    # 全部内容仍在情景库(不清除)
            assert f"sb-{i}" in contents
    finally:
        small.close()


def test_salience_standalone_demote_writes_episode(tmp_path):
    """缓冲独立条目(无 episode 关联)降级时落情景库, 记忆不丢。"""
    small: MemoryService = make_svc(tmp_path, salience_cap=2)
    try:
        for i in range(4):  # 直接写缓冲(不经 episode)
            small.salience.add(content=f"alone-{i}", salience=1.0 - i * 0.1,
                               ref_id=f"mw-{i}")
        assert small.salience.count() == 2
        demoted = [r for r in small.episodic.all_rows() if r["kind"] == "demoted"]
        assert {r["utterance"] for r in demoted} == {"alone-1", "alone-2"}
    finally:
        small.close()


def test_working_push_then_recover_keeps_latest_10(svc):
    """恢复语义: 重启后工作记忆 = 情景库中该会话最近 10 轮。"""
    now = time.time()
    for i in range(15):
        svc.write_episode(utterance=f"round-{i}", session_id="s-rec",
                          ts=now + i, push_working=True)
    state = svc.session_recover("s-rec")
    assert state["rebuilt"] == 10
    assert state["turns"][0]["text"] == "round-5"   # 最近 10 轮的起点
    assert state["turns"][-1]["text"] == "round-14"


def test_overflow_unit_coverage_via_working_get(svc):
    """working_get 空会话自动触发恢复(崩溃恢复路径)。"""
    svc.write_episode(utterance="hello again", session_id="s-x")
    state = svc.working_get("s-x")
    assert state["recovered"] is True
    assert state["turns"][-1]["text"] == "hello again"
