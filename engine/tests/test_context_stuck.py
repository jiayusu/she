"""FR-E08 · 上下文注入 ≤1500 token；FR-E09 · 连续 2 次卡壳自动降 L。"""

from she_engine.context import MAX_CTX_TOKENS, build_ctx_block, est_tokens
from she_engine.stuck import StuckTracker


# ---------------------------------------------------------------- FR-E08
def test_small_context_untouched():
    cb = build_ctx_block(
        [{"speaker": "child", "text": "hi"}, {"speaker": "xiaop", "text": "hello!"}],
        ["apple"], "SCRIPT STATE: morning court",
    )
    assert not cb.stats.truncated
    assert cb.stats.turns_kept == 2
    assert "apple" in cb.text and "morning court" in cb.text


def test_budget_respected_with_huge_history():
    turns = [{"speaker": f"spk{i}", "text": ("long sentence about apples and bananas " * 60)} for i in range(200)]
    cb = build_ctx_block(turns, [f"word{i}" for i in range(100)], "state line")
    assert cb.stats.tokens <= MAX_CTX_TOKENS
    assert cb.stats.turns_kept < 10  # 预算内装不下 10 轮 → 最旧的被裁掉
    assert cb.stats.turns_dropped > 0
    assert cb.stats.truncated


def test_max_ten_turns_cap():
    turns = [{"speaker": "c", "text": f"word{i} " * 3} for i in range(30)]
    cb = build_ctx_block(turns, [], "state")
    assert cb.stats.turns_kept <= 10


def test_state_and_words_never_dropped():
    """截断按优先级：剧本状态 + 已学词必保。"""
    turns = [{"speaker": "c", "text": "filler " * 100} for _ in range(50)]
    cb = build_ctx_block(turns, ["apple", "banana"], "MUST KEEP STATE")
    assert "MUST KEEP STATE" in cb.text
    assert "apple, banana" in cb.text


def test_token_estimator_mixed_zh_en():
    t_zh = est_tokens("这是一句中文剧本状态" * 10)
    t_en = est_tokens("plain english sentence about apples " * 10)
    assert t_zh > 0 and t_en > 0


# ---------------------------------------------------------------- FR-E09
def test_two_stuck_turns_downgrade_level():
    """验收：卡壳检测→降级的链路可观测。"""
    tracker = StuckTracker(level=2)
    v1 = tracker.observe("")           # 第 1 次卡壳
    assert v1.stuck and v1.streak == 1 and not v1.downgraded
    v2 = tracker.observe("…")          # 第 2 次卡壳 → 降级
    assert v2.stuck and v2.downgraded and v2.new_level == 1


def test_substantive_speech_resets_streak():
    tracker = StuckTracker(level=3)
    tracker.observe("")
    v = tracker.observe("I like apples", asr_confidence=0.9)
    assert not v.stuck and tracker.streak == 0


def test_low_asr_confidence_counts_as_stuck():
    tracker = StuckTracker(level=1)
    v1 = tracker.observe("mmm", asr_confidence=0.1)
    v2 = tracker.observe("er", asr_confidence=0.15)
    assert v1.stuck and v2.downgraded


def test_level_floors_at_zero():
    tracker = StuckTracker(level=0)
    tracker.observe("")
    v = tracker.observe("")
    assert v.stuck and not v.downgraded and v.new_level == 0


def test_parent_note_generated_on_downgrade():
    tracker = StuckTracker(level=2)
    tracker.observe("")
    v = tracker.observe("")
    note = tracker.parent_note(v)
    assert note and note[0] == "parent_note" and note[1] == "level_down"
    assert "L1" in note[2]


def test_various_silence_tokens():
    tracker = StuckTracker(level=5)
    for tok in ("", "…", "嗯", "呃", "(silence)", "."):
        v = tracker.observe(tok)
        assert v.stuck
    assert tracker.level == 4  # L5 降到 L4
