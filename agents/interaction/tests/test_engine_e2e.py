"""端到端验收：PRD §3 用户故事 / 拔网线 / 埋点 / 持久化续剧 / 成本与延迟预算。"""

import pytest

from she_engine import Engine, EngineConfig
from she_engine.events import InMemorySink
from she_engine.llm import FlakyProvider, GarbledProvider, MockProvider
from she_engine.memory import FileMemoryStore
from she_engine.types import INTENT_THINGS


@pytest.fixture
def sink():
    return InMemorySink()


def _engine(sink=None, **kw):
    if sink is not None:
        kw["event_sink"] = sink
    kw.setdefault("provider", MockProvider())
    kw.setdefault("session_level", 1)
    return Engine(EngineConfig(**kw))


# ---------------------------------------------------------------- 用户故事 1：Recast
def test_user_story_1_recast():
    """孩子说 "I like apple"，杏杏回 "I like apples too!..."（Recast，不指出错误）。"""
    eng = _engine()
    r = eng.turn({
        "child_utterance": "I like apple", "level": 1,
        "asr_result": {"text": "I like apple", "confidence": 0.92},
        "assess_result": {"has_error": True, "original": "I like apple",
                          "corrected": "I like apples", "error_type": "plural",
                          "word": "apple", "score": 78},
    })
    d = r.to_dict()
    assert set(d) == {"speaker", "text", "emotion_tag", "memory_write"}  # FR-E06 Schema
    assert d["speaker"] == "xingxing"
    assert d["text"].startswith("I like apples too! Apples are sweet.")
    assert not any(w in d["text"] for w in ("错", "wrong", "should", "不对"))


# ---------------------------------------------------------------- 用户故事 2：沉默重邀
def test_user_story_2_silence_reinvite():
    """孩子 10 秒没说话，小P 用更低一级句式重邀："跟着我说——apple。" """
    eng = _engine()
    r = eng.handle_silence("apple")
    assert r.speaker == "xiaop"
    assert "apple" in r.text and "跟我说" in r.text


# ---------------------------------------------------------------- 用户故事 3：拔网线
@pytest.mark.parametrize("provider", [
    FlakyProvider(MockProvider(), fail_times=999),   # 网络彻底挂
    GarbledProvider("嘿嘿我不知道"),                  # 模型返回乱码（非 JSON）
])
def test_user_story_3_no_empty_response(provider):
    """LLM 服务商挂了，孩子依然听到模板回应，无任何空响应（回应率 100%）。"""
    eng = _engine(provider=provider)
    script = [
        {"child_utterance": "早上好！", "level": 1},
        {"child_utterance": "I like apple", "level": 1,
         "assess_result": {"has_error": True, "original": "I like apple",
                           "corrected": "I like apples", "error_type": "plural", "word": "apple"}},
        {"child_utterance": "", "level": 1},                 # 沉默
        {"child_utterance": "这是什么呀", "level": 2},        # 万物
        {"child_utterance": "我有点害怕", "level": 1},        # 情绪
        {"child_utterance": "昨天讲到哪了", "level": 1},      # 记忆
    ]
    for turn in script:
        r = eng.turn(turn)
        d = r.to_dict()
        assert d["text"].strip(), f"empty response for {turn}"
        assert d["speaker"] in ("xiaop", "laonie", "xingxing", "ahai", "wangguan")
        assert d["emotion_tag"]
        assert isinstance(d["memory_write"], list)
        assert r.meta["fallback_used"]


# ---------------------------------------------------------------- FR-E06 重试链
def test_retry_once_then_template():
    """解析失败重试 1 次，再失败走模板；且只重试一次。"""
    calls = {"n": 0}

    class CountingGarbled(GarbledProvider):
        def complete(self, system_prompt, user_prompt):
            calls["n"] += 1
            return super().complete(system_prompt, user_prompt)

    eng = _engine(provider=CountingGarbled())
    r = eng.turn({"child_utterance": "早上好！", "level": 1})
    assert calls["n"] == 2          # 首次 + 重试 1 次
    assert r.meta["fallback_used"]


# ---------------------------------------------------------------- 埋点（PRD §8）
def test_events_emitted(sink):
    eng = _engine(sink=sink)
    eng.turn({
        "child_utterance": "I like apple", "level": 1,
        "asr_result": {"text": "I like apple", "confidence": 0.9},
        "assess_result": {"has_error": True, "original": "I like apple",
                          "corrected": "I like apples", "error_type": "plural", "word": "apple"},
    })
    eng.handle_silence("apple")
    routed = sink.of("engine_routed")
    assert routed and routed[0]["minister"] == "xingxing"
    recasts = sink.of("engine_recast")
    assert recasts and recasts[0]["assess_used"] is True
    latency = sink.of("engine_latency")
    assert latency and "ttft" in latency[0] and "total" in latency[0]


def test_fallback_event_on_network_down(sink):
    eng = _engine(provider=FlakyProvider(MockProvider(), fail_times=999), event_sink=sink)
    eng.turn({"child_utterance": "早上好！", "level": 1})
    assert sink.count("engine_fallback") >= 1


# ---------------------------------------------------------------- FR-E03 跨天续剧
def test_restart_resumes_story(tmp_path):
    """关机重开后能接续"昨天讲到哪"。"""
    data_dir = str(tmp_path / "data")
    eng1 = Engine(EngineConfig(provider=MockProvider(), memory=FileMemoryStore(data_dir)))
    # 走完朝会 3 个任务，进入探险并开口 2 次
    for text in ("早上好", "我会说 apple", "我找到了球"):
        eng1.turn({"child_utterance": text, "level": 1})
    for text in ("我在过河", "山那边有树"):
        eng1.turn({"child_utterance": text, "level": 1})
    assert eng1.script_state.state == "adventure"
    assert eng1.script_state.adventure_done == 2

    # —— 关机重开 ——
    eng2 = Engine(EngineConfig(provider=MockProvider(), memory=FileMemoryStore(data_dir)))
    assert eng2.script_state.state == "adventure"           # 同天重启：进度原样接续
    assert eng2.script_state.adventure_done == 2

    # —— 跨天重开（把快照日期改成昨天模拟） ——
    state = eng2._memory.load_script_state()
    import datetime as dt
    state["date"] = (dt.date.today() - dt.timedelta(days=1)).isoformat()
    eng2._memory.save_script_state(state)
    eng3 = Engine(EngineConfig(provider=MockProvider(), memory=FileMemoryStore(data_dir)))
    assert eng3.script_state.days_played == 2
    assert eng3.script_state.adventure_done == 2            # 从中途接续
    r = eng3.turn({"child_utterance": "我们继续吧", "level": 1})
    assert r.meta["recap"]                                  # "昨天讲到哪" 已注入本轮


# ---------------------------------------------------------------- FR-E09 会话级降级
def test_stuck_downgrade_e2e():
    eng = _engine(session_level=2)
    assert eng.level == 2
    eng.turn({"child_utterance": "", "level": 2})     # 卡壳 1
    r2 = eng.turn({"child_utterance": "……", "level": 2})  # 卡壳 2 → 降级
    assert eng.level == 1
    assert any(w.type == "parent_note" for w in r2.memory_write)


# ---------------------------------------------------------------- FR-E08 上游 ctx_bundle
def test_ctx_bundle_from_upstream():
    eng = _engine()
    r = eng.turn({
        "child_utterance": "我找到了球", "level": 2,
        "ctx_bundle": {
            "recent_turns": [{"speaker": "xiaop", "text": "Find a ball!"}] * 12,
            "learned_words_today": ["apple", "ball"],
            "script_state": {"state": "adventure"},
        },
    })
    assert r.meta["ctx_tokens"] > 0
    assert r.meta["ctx_tokens"] <= 1500


# ---------------------------------------------------------------- 万物 KG 事实注入
def test_things_intent_injects_kg_facts(sink):
    captured = {}

    class SpyProvider(MockProvider):
        def complete(self, system_prompt, user_prompt):
            captured["system"] = system_prompt
            captured["user"] = user_prompt
            return super().complete(system_prompt, user_prompt)

    def _kg_facts(thing: str):
        return [f"{thing} is cold", f"{thing} is in the kitchen", f"{thing} keeps food fresh"]

    eng = _engine(provider=SpyProvider(), kg_lookup=_kg_facts)
    eng.turn({
        "child_utterance": "这是什么呀 fridge", "level": 2,
        "route_intent": INTENT_THINGS,
    })
    assert "KG FACTS" in captured["user"]
    assert "fridge is cold" in captured["user"]


# ---------------------------------------------------------------- 安全拦截走模板
def test_safety_block_falls_back_to_template():
    from she_engine.safety import SafetyFilter

    class BlockAll(SafetyFilter):
        def filter(self, text, context=""):
            return False, ""

    eng = _engine(safety=BlockAll())
    r = eng.turn({"child_utterance": "早上好！", "level": 1})
    assert r.text  # 被拦截也不空响应，走模板
    assert r.meta["fallback_used"]


@pytest.mark.parametrize("provider_failure", ["blocked_text", "unavailable", "malformed"])
@pytest.mark.parametrize("custom_safety", [False, True])
def test_final_fallback_rejects_unsafe_assessment_slot(provider_failure, custom_safety):
    """Synthetic untrusted slot must not reappear after an unsafe output is rejected."""
    from she_engine.llm import LLMResult
    from she_engine.safety import LocalSafetyFilter, PassThroughFilter

    class UnsafeProvider:
        def complete(self, system_prompt, user_prompt):
            return LLMResult(ok=True, text=(
                '{"speaker":"xingxing","text":"bomb",'
                '"emotion_tag":"happy","memory_write":[]}'
            ))

    providers = {
        "blocked_text": UnsafeProvider(),
        "unavailable": FlakyProvider(MockProvider(), fail_times=999),
        "malformed": GarbledProvider(),
    }
    eng = _engine(provider=providers[provider_failure],
                  safety=PassThroughFilter() if custom_safety else None)
    response = eng.turn({
        "child_utterance": "apple",
        "route_intent": "word_learning",
        "assess_result": {"word": "bomb", "has_error": False},
    })

    assert response.text.strip()
    assert "bomb" not in response.text.lower()
    assert LocalSafetyFilter().filter(response.text)[0]
    assert response.meta["fallback_used"]
    assert response.meta["template_id"] == "hardcoded"


# ---------------------------------------------------------------- 成本护栏
def test_cost_warning_event(sink):
    class CostlyProvider(MockProvider):
        def complete(self, system_prompt, user_prompt):
            res = super().complete(system_prompt, user_prompt)
            res.tokens_in = 100_000  # 抬高成本触发报警
            res.tokens_out = 50_000
            return res

    eng = _engine(provider=CostlyProvider(), event_sink=sink)
    eng.turn({"child_utterance": "早上好！", "level": 1})
    assert sink.count("engine_cost_warn") == 1
    assert eng._session_cost_yuan > 0.02


# ---------------------------------------------------------------- 缓存命中
def test_cached_provider_hits():
    from she_engine.llm import CachedProvider
    cached = CachedProvider(MockProvider())
    r1 = cached.complete("sys", "user")
    r2 = cached.complete("sys", "user")
    assert cached.hits == 1 and r1.text == r2.text


# ---------------------------------------------------------------- 级别收敛
def test_level_fit_enforced_even_if_model_verbose():
    class VerboseProvider(MockProvider):
        def complete(self, system_prompt, user_prompt):
            res = super().complete(system_prompt, user_prompt)
            import json as _json
            obj = _json.loads(res.text)
            obj["text"] = ("I like apples and bananas and pears and plums and grapes today. " * 3
                           + "| 好长呀")
            res.text = _json.dumps(obj, ensure_ascii=False)
            return res

    eng = _engine(provider=VerboseProvider(), session_level=1)
    r = eng.turn({"child_utterance": "早上好！", "level": 1})
    from she_engine.levels import check_level_fit
    assert check_level_fit(r.text, 1)  # 无论模型多啰嗦，输出都收敛到 L1 约束
