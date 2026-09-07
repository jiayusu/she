"""FR-E06 · 输出 JSON Schema 强约束。

验收：解析失败自动重试 1 次，再失败走模板；无效 JSON 率 <2%（由 e2e 的
GarbledProvider 链路 + 修复归一共同保障，这里验证解析/修复/拒收单元）。
"""

import json

from she_engine.schema import (
    extract_json_blob,
    parse_llm_output,
    repair_user_prompt,
    MAX_TEXT_CHARS,
)


def _ok_json(text="Hello!", speaker="xiaop", emotion="happy", writes=None):
    return json.dumps({"speaker": speaker, "text": text, "emotion_tag": emotion,
                       "memory_write": writes or []}, ensure_ascii=False)


# ---------------------------------------------------------------- 提取
def test_extract_plain():
    assert extract_json_blob('{"a":1}') == '{"a":1}'


def test_extract_with_fence_and_prose():
    raw = '好的，这是结果：\n```json\n{"a": 1, "b": {"c": "}"}}\n```\n以上。'
    assert extract_json_blob(raw) == '{"a": 1, "b": {"c": "}"}}'


def test_extract_nested_braces_in_strings():
    raw = '{"t": "greeting {oops}", "n": 2}'
    assert extract_json_blob(raw) == raw


def test_extract_none_when_no_json():
    assert extract_json_blob("没有任何结构化内容") is None


# ---------------------------------------------------------------- 解析
def test_parse_valid_minimal():
    out = parse_llm_output(_ok_json(), expected_speaker="xiaop")
    assert out.ok
    assert out.response.text == "Hello!"
    assert out.response.speaker == "xiaop"
    assert out.response.emotion_tag == "happy"
    assert out.response.memory_write == []


def test_parse_full_memory_write():
    writes = [{"type": "learned_word", "key": "word", "value": "apple"}]
    out = parse_llm_output(_ok_json(writes=writes), expected_speaker="xiaop")
    assert out.ok and not out.repaired
    assert out.response.memory_write[0].type == "learned_word"


def test_parse_repairs_unknown_emotion():
    out = parse_llm_output(_ok_json(emotion="super-duper-joy"), expected_speaker="xiaop")
    assert out.ok and out.repaired
    assert out.response.emotion_tag == "happy"


def test_parse_repairs_wrong_speaker():
    out = parse_llm_output(_ok_json(speaker="ahai"), expected_speaker="xiaop")
    assert out.ok and out.repaired
    assert out.response.speaker == "xiaop"  # 拉回本次路由的大臣


def test_parse_drops_bad_memory_writes():
    writes = [
        {"type": "learned_word", "key": "word", "value": "apple"},
        {"type": "nonsense_type", "key": "x", "value": "y"},  # 非法 type → 丢弃
        {"type": "fact", "value": "no key"},                  # 缺 key → 丢弃
        "not a dict",                                          # 非对象 → 丢弃
    ]
    out = parse_llm_output(_ok_json(writes=writes), expected_speaker="xiaop")
    assert out.ok and out.repaired
    assert len(out.response.memory_write) == 1


def test_parse_failures():
    for raw in ("", "plain text", "{broken json", '{"text": ""}', '{"text": "  "}'):
        out = parse_llm_output(raw, expected_speaker="xiaop")
        assert not out.ok, raw


def test_parse_truncates_overlong_text():
    out = parse_llm_output(_ok_json(text="word " * 300), expected_speaker="xiaop")
    assert out.ok and out.repaired
    assert len(out.response.text) <= MAX_TEXT_CHARS + 1


def test_repair_prompt_mentions_previous():
    p = repair_user_prompt("ORIG", '{"bad":')
    assert "ORIG" in p and "NOT valid JSON" in p
