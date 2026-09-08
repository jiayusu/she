"""FR-E04 · Recast 改写：吸收式纠错，不指出错误（盲评 100 条 ≤5 条打断式纠错的守门链）。"""

from she_engine.recast import (
    build_recast_directive,
    detect_error_pointing,
    template_recast,
)
from she_engine.types import AssessResult


def _assess(**kw):
    base = dict(has_error=True, original="I like apple", corrected="I like apples",
                error_type="plural", word="apple", score=78.0)
    base.update(kw)
    return AssessResult(**base)


def test_directive_absent_without_error():
    assert not build_recast_directive(None)
    assert not build_recast_directive(_assess(has_error=False))


def test_directive_contains_target_and_iron_rules():
    d = build_recast_directive(_assess())
    assert d.has_error
    assert "I like apples" in d.text
    assert "NEVER point out" in d.text
    assert "RECAST MODE" in d.text


def test_directive_without_corrected_form():
    d = build_recast_directive(_assess(corrected="", error_type="pronunciation"))
    assert d.has_error and "well-formed short sentence" in d.text


# ---------------------------------------------------------------- 打断式纠错检测
import pytest  # noqa: E402


@pytest.mark.parametrize("bad", [
    "你说错了，应该是 apples",
    "不对哦，是 apples",
    "You said it wrong. It is apples.",
    "You should say apples.",
    "注意哦，这个词要这样读",
    "不是 apple，而是 apples",
    "这是复数问题，要加 s",
])
def test_detects_error_pointing(bad):
    assert detect_error_pointing(bad), bad


@pytest.mark.parametrize("good", [
    "I like apples too! Apples are sweet.",
    "跟我念——apples。Apples are sweet.",
    "Nice! I like apples too.",
])
def test_accepts_recast(good):
    assert not detect_error_pointing(good), good


def test_template_recast_is_safe_for_all_ministers():
    for minister in ("xingxing", "xiaop", "laonie", "ahai", "wangguan"):
        text = template_recast(_assess(), minister)
        assert not detect_error_pointing(text)
        assert "apples" in text


def test_template_recast_without_correction():
    text = template_recast(_assess(corrected="", original="I want the boll"), "xingxing")
    assert not detect_error_pointing(text)
