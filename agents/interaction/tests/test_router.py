"""FR-E02 · 查询路由：映射表覆盖六类意图，错误率 ≤10%。"""

import pytest

from she_engine.router import (
    EVAL_SET,
    HybridClassifier,
    INTENT_CHITCHAT,
    INTENT_COURT_TASK,
    INTENT_EMOTION_COMFORT,
    INTENT_MEMORY_QUERY,
    INTENT_THINGS,
    INTENT_WORD_LEARNING,
    MINISTER_AHAI,
    MINISTER_LAONIE,
    MINISTER_WANGGUAN,
    MINISTER_XIAOP,
    MINISTER_XINGXING,
    Router,
    eval_router_accuracy,
)


def test_eval_set_accuracy_ge_90pct():
    """验收红线：路由错误率 ≤10%。"""
    acc = eval_router_accuracy()
    assert acc >= 0.90, f"router accuracy {acc:.3f} < 0.90"


def test_mapping_table_covers_six_intents():
    """验收：映射表覆盖朝会任务/记忆询问/学词/情绪安抚/万物/闲聊六类。"""
    router = Router()
    samples = {
        INTENT_COURT_TASK: "今天的任务是什么",
        INTENT_MEMORY_QUERY: "昨天我们讲到哪了",
        INTENT_WORD_LEARNING: "apple 怎么说",
        INTENT_EMOTION_COMFORT: "我有点害怕",
        INTENT_THINGS: "这是什么呀",
        INTENT_CHITCHAT: "你好呀",
    }
    for intent, text in samples.items():
        d = router.route(text)
        assert d.intent == intent, f"{text!r} -> {d.intent} (want {intent})"


def test_static_intent_to_minister():
    router = Router()
    assert router.route("今天的任务是什么").minister == MINISTER_XIAOP
    assert router.route("昨天学了什么").minister == MINISTER_AHAI
    assert router.route("I like apple.").minister == MINISTER_XINGXING
    assert router.route("我不想一个人睡").minister == MINISTER_AHAI
    assert router.route("Why is the sea blue?").minister == MINISTER_WANGGUAN


def test_chitchat_routes_by_script_state():
    """闲聊按剧本状态：朝会→小P / 探险→老颞 / 睡前→阿海。"""
    router = Router()
    text = "哈哈哈真好玩"
    assert router.route(text, script_state="morning_court").minister == MINISTER_XIAOP
    assert router.route(text, script_state="adventure").minister == MINISTER_LAONIE
    assert router.route(text, script_state="bedtime").minister == MINISTER_AHAI
    assert router.route(text).minister == MINISTER_XIAOP  # 未初始化 → 小P


def test_assess_presence_boosts_word_learning():
    """ASR 评估在场 + 孩子英文产出 → 学词（FR-E04 链路入口）。"""
    router = Router()
    d = router.route("I like apple.", assess_present=True)
    assert d.intent == INTENT_WORD_LEARNING


def test_upstream_override_wins():
    router = Router()
    d = router.route("你好呀", route_intent=INTENT_THINGS)
    assert d.intent == INTENT_THINGS and d.minister == MINISTER_WANGGUAN
    assert d.by == "override"


def test_illegal_override_ignored():
    router = Router()
    d = router.route("你好呀", route_intent="hacking_intent")
    assert d.intent == INTENT_CHITCHAT


def test_hybrid_classifier_falls_back_to_model():
    """规则置信度不足时 → 轻量模型；模型挂了 → 回落规则，不阻塞。"""

    def good_model(text: str) -> str:
        return INTENT_THINGS

    def broken_model(text: str) -> str:
        raise RuntimeError("model down")

    d1 = Router(HybridClassifier(good_model)).route("模棱两可的一句话")
    assert d1.intent == INTENT_THINGS
    d2 = Router(HybridClassifier(broken_model)).route("模棱两可的一句话")
    assert d2.intent in {INTENT_CHITCHAT}


def test_empty_input_defaults_chitchat():
    d = Router().route("")
    assert d.intent == INTENT_CHITCHAT and d.minister == MINISTER_XIAOP
