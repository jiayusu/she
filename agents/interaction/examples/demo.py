# -*- coding: utf-8 -*-
"""演示：LLM 剧情引擎 · 一个完整会话（离线 MockProvider，无需网络）。

跑法::

    cd engine
    python examples/demo.py

演示脚本覆盖 PRD §3 的三个用户故事：
1. 孩子说 "I like apple"，杏杏 Recast："I like apples too! Apples are sweet."
2. 孩子 10 秒没说话，小P 用更低一级句式重邀："跟着我说——apple。"
3. LLM 服务商挂了（演示后半段切到「拔网线」provider），孩子依然听到模板回应。
"""
import datetime as dt
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from she_engine import Engine, EngineConfig                     # noqa: E402
from she_engine.llm import FlakyProvider, MockProvider           # noqa: E402
from she_engine.memory import FileMemoryStore                    # noqa: E402

LINE = "─" * 78


def _state_brief(s: dict) -> str:
    name = {"morning_court": "朝会", "adventure": "探险",
            "bedtime": "睡前", "ended": "一日结束"}[s["state"]]
    if s["state"] == "morning_court":
        return f"{name}({s['tasks_done']}/{s['tasks_total']}任务)"
    if s["state"] == "adventure":
        return f"{name}(第{s['chapter']}章 {s['adventure_done']}/{s['adventure_turns']}步)"
    if s["state"] == "bedtime":
        return f"{name}({s['bedtime_done']}/{s['bedtime_turns']})"
    return name


def show(step: str, r) -> None:
    print(f"\n{step}")
    print(f"  🗣  [{r.speaker}] {r.text}")
    m = r.meta
    extra = []
    if m.get("mode") == "recast":
        extra.append("mode=recast(吸收式纠错)")
    if m.get("fallback_used"):
        extra.append(f"fallback→{m.get('template_id')}")
    print(f"     路由={m['intent']} → {m['minister']} | L{m['level']} | "
          f"剧本={_state_brief(m['state'])} | 延迟={m['latency_ms']['total']:.1f}ms"
          + (f" | {' · '.join(extra)}" if extra else ""))
    if m.get("recap"):
        print(f"     ♻ 接续昨天剧情: {m['recap']}")


def main() -> None:
    print(LINE)
    print("LLM 剧情引擎演示 · 「开口是唯一货币」")
    print(LINE)

    data_dir = os.path.join(
        os.path.dirname(__file__), "..", "data",
        "demo_" + dt.datetime.now().strftime("%H%M%S"))  # 每次运行全新存档
    eng = Engine(EngineConfig(
        provider=MockProvider(),
        memory=FileMemoryStore(data_dir),
        session_level=1,
        kg_lookup=lambda thing: [f"{thing} is cold", f"{thing} keeps food fresh",
                                 f"{thing} is in the kitchen"],
    ))
    print(f"\n已注册大臣：{', '.join(eng.registry.ids())}")
    print(f"今日朝会任务：{eng.script_state.tasks_planned}")

    # ── 第一幕：朝会 ─────────────────────────────────────────────────────
    show("① 朝会开始，孩子问好", eng.turn({"child_utterance": "早上好！", "level": 1}))

    # ── 用户故事 1：Recast 吸收式纠错 ────────────────────────────────────
    show("② 孩子说 I like apple（发音评估发现单复数错误）",
         eng.turn({
             "child_utterance": "I like apple", "level": 1,
             "asr_result": {"text": "I like apple", "confidence": 0.92},
             "assess_result": {"has_error": True, "original": "I like apple",
                               "corrected": "I like apples", "error_type": "plural",
                               "word": "apple", "score": 78},
         }))

    # ── 用户故事 2：10 秒沉默 → 小P 低一级句式重邀 ──────────────────────
    show("③ 孩子 10 秒没说话", eng.handle_silence("apple"))

    # ── 孩子开口，完成任务，进入探险 ────────────────────────────────────
    show("④ 孩子跟读并完成任务", eng.turn({
        "child_utterance": "apple", "level": 1,
        "asr_result": {"text": "apple", "confidence": 0.95},
        "assess_result": {"has_error": False, "word": "apple", "score": 92},
    }))
    for text in ("我找到了球", "ball"):
        eng.turn({"child_utterance": text, "level": 1,
                  "assess_result": {"has_error": False, "word": "ball", "score": 90}})

    # ── 探险 + 万物 + 情绪 ──────────────────────────────────────────────
    show("⑤ 探险途中孩子指着冰箱问（万物 → 王冠，KG 事实注入）",
         eng.turn({"child_utterance": "这是什么呀 fridge", "level": 2,
                   "route_intent": "things"}))
    show("⑥ 孩子有点害怕（情绪安抚 → 阿海）",
         eng.turn({"child_utterance": "打雷了，我有点害怕", "level": 1}))
    show("⑦ 闲聊（探险中 → 老颞接话推进剧情）",
         eng.turn({"child_utterance": "哈哈哈真好玩", "level": 1}))

    # ── FR-E09：连续 2 次卡壳 → 自动降 L ────────────────────────────────
    print(f"\n（当前句式级别 L{eng.level}，连续卡壳模拟开始）")
    show("⑧ 孩子没有回应", eng.turn({"child_utterance": "", "level": 1}))
    show("⑨ 孩子还是没有回应（触发降级）", eng.turn({"child_utterance": "……", "level": 1}))
    print(f"     ➜ 句式级别已自动降至 L{eng.level}（parent_note 已写入记忆）")

    # ── FR-E03：跨天续剧情（关机重开接续"昨天讲到哪"） ────────────────────
    print("\n" + LINE)
    print("🌙 跨天续剧情演示：把存档日期改成昨天 → 模拟关机重开")
    print(LINE)
    state = eng._memory.load_script_state()
    state["date"] = (dt.date.today() - dt.timedelta(days=1)).isoformat()
    eng._memory.save_script_state(state)
    eng2 = Engine(EngineConfig(provider=MockProvider(), memory=FileMemoryStore(data_dir),
                               session_level=1))
    show("⑩ 新的一天开机，孩子说：我们继续吧", eng2.turn({"child_utterance": "我们继续吧", "level": 1}))

    # ── 用户故事 3：拔网线 ──────────────────────────────────────────────
    print("\n" + LINE)
    print("🔥 模拟 LLM 服务商宕机（拔网线测试：回应率必须 100%）")
    print(LINE)
    dead = Engine(EngineConfig(
        provider=FlakyProvider(MockProvider(), fail_times=999),
        memory=FileMemoryStore(data_dir + "_offline"),
        session_level=1,
    ))
    for text in ("早上好！", "这是什么呀", "我有点害怕", "I like apple", ""):
        r = dead.turn({"child_utterance": text, "level": 1})
        show(f"  离线回应（孩子说: {text or '(沉默)'}）", r)

    print("\n" + LINE)
    print(f"会话成本：¥{eng._session_cost_yuan:.4f} / 预算 ¥0.02（MockProvider 零成本）")
    print("演示数据已写入 engine/data/demo_child/（关掉重跑可体验跨天续剧情）")
    print(LINE)


if __name__ == "__main__":
    main()
