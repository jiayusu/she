"""FR-E05 · 分级句式：L1≤5 / L2≤10 / L3+≤16（抽检达标）+ 词汇池/脚手架注入。"""

import pytest

from she_engine.levels import (
    MAX_SENTENCE_WORDS,
    check_level_fit,
    fit_text_to_level,
    get_level_rules,
    load_pools_from_cefrj,
    max_sentence_words,
)


@pytest.mark.parametrize("level,cap", [(0, 3), (1, 5), (2, 10), (3, 16), (4, 16), (5, 16)])
def test_level_caps_config(level, cap):
    assert MAX_SENTENCE_WORDS[level] == cap


def test_acceptance_l1_l2_l3():
    """验收样例：L1≤5 词 / L2≤10 词 / L3+≤16 词。"""
    assert check_level_fit("I like apples too! Apples are sweet.", 1)
    assert not check_level_fit("I like apples and bananas and pears and plums today.", 1)
    assert check_level_fit("The fridge is cold. What is cold too? Ice is cold!", 2)
    assert check_level_fit("The little snake went over the mountain and found a big shiny treasure.", 3)


def test_fit_trims_long_sentence():
    out, trimmed = fit_text_to_level(
        "The very very very long snake walked slowly over the hill and vanished. | 故事继续啦", 1)
    assert trimmed
    assert check_level_fit(out, 1)
    assert out.endswith("| 故事继续啦")  # 中文脚手架保留


def test_fit_drops_extra_sentences_at_l1():
    out, trimmed = fit_text_to_level("One. Two. Three. Four.", 1)  # L1 最多 2 句
    assert trimmed
    assert max_sentence_words(out) <= 5
    assert out.count(".") == 2


def test_fit_never_empty():
    out, _ = fit_text_to_level("supercalifragilistic", 0)
    assert out


def test_level_rules_prompt_contains_constraints():
    r1 = get_level_rules(1)
    assert r1.max_words == 5 and r1.scaffold_zh
    p1 = r1.to_prompt()
    assert "Max English sentence length: 5" in p1 and "Chinese scaffold" in p1
    p3 = get_level_rules(3).to_prompt()
    assert "Max English sentence length: 16" in p3 and "No Chinese scaffold" in p3
    # L2 词汇池注入
    assert "fridge" in get_level_rules(2).to_prompt()


def test_level_clamp():
    assert get_level_rules(-1).level == 0
    assert get_level_rules(9).level == 5


def test_load_pools_from_cefrj_missing_file(tmp_path):
    assert load_pools_from_cefrj(str(tmp_path / "nope.csv")) == {}


def test_load_pools_from_cefrj(tmp_path):
    p = tmp_path / "cefrj.csv"
    p.write_text(
        "headword,pos,CEFR\nfridge,noun,A2\nhappy,adj,A2\njourney,noun,B1\n"
        "invention,noun,B2\nuniverse,noun,C1\nrun,verb,A1\n",
        encoding="utf-8",
    )
    pools = load_pools_from_cefrj(str(p))
    assert "fridge" in pools[2] and "journey" in pools[3]
    assert "invention" in pools[4] and "universe" in pools[5]
    assert 0 not in pools and 1 not in pools  # A1 不收录
