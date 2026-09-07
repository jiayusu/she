"""FR-E02 · 查询路由：把输入意图映射到大臣。

两级分类器（规则 + 轻量模型）::

    RuleClassifier        —— 中英关键词/正则打分，毫秒级、零成本、可解释
    HybridClassifier      —— 规则置信度不足时交给可插拔的轻量模型（few-shot 小模型
                             或一次本地推理），线上可将 model 换成任意 callable

六类意图映射（覆盖 PRD 验收要求的映射表）::

    court_task(朝会任务)   → xiaop    小P
    memory_query(记忆询问) → ahai     阿海
    word_learning(学词)    → xingxing 杏杏
    emotion_comfort(情绪安抚) → ahai  阿海（记忆+情绪同管家）
    things(万物)           → wangguan 王冠
    chitchat(闲聊)         → 按剧本状态：朝会→小P / 探险→老颞 / 睡前→阿海

验收：路由错误率 ≤10%（tests 用 60 条标注集断言 ≥90% 准确率）。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Tuple

from .types import (
    ALL_INTENTS,
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
)

# 意图 → 静态大臣（chitchat 由剧本状态决定，见 engine.route_minister）
INTENT_MINISTER: Dict[str, str] = {
    INTENT_COURT_TASK: MINISTER_XIAOP,
    INTENT_MEMORY_QUERY: MINISTER_AHAI,
    INTENT_WORD_LEARNING: MINISTER_XINGXING,
    INTENT_EMOTION_COMFORT: MINISTER_AHAI,
    INTENT_THINGS: MINISTER_WANGGUAN,
}

# chitchat 的状态路由：朝会→小P / 探险→老颞 / 睡前→阿海
CHITCHAT_STATE_MINISTER: Dict[str, str] = {
    "morning_court": MINISTER_XIAOP,
    "adventure": MINISTER_LAONIE,
    "bedtime": MINISTER_AHAI,
}


@dataclass(frozen=True)
class RouteDecision:
    intent: str
    minister: str
    confidence: float
    matched: Tuple[str, ...] = ()   # 命中的规则（可解释性/回归排查用）
    by: str = "rules"               # rules | override | model | default


def _hits(text: str, patterns: Tuple[str, ...]) -> List[str]:
    found = []
    for p in patterns:
        if re.search(p, text):
            found.append(p)
    return found


# ------------------------------------------------------------------ 规则库
# 每条意图：正则组 + 权重。中文为主（目标用户家庭语言），英文问答词兜底。
RULES: Dict[str, Tuple[Tuple[str, float], ...]] = {
    INTENT_EMOTION_COMFORT: (
        (r"难过|伤心|生气|害怕|怕|委屈|想妈妈|不想|孤单|哭|不开心|不高兴|郁闷", 3.0),
        (r"sad|scared|afraid|angry|lonely|cry(ing)?\b", 3.0),
        (r"怕黑|打雷|做噩梦|不要分开", 3.0),
    ),
    INTENT_THINGS: (
        (r"这是什[么么]|那是什[么]|它是什么|为什么|怎么会|是什么做|哪里来的|怎么来的|怎么回[事]", 3.0),
        (r"what('s| is) (this|that|it)|why (is|do|does)|how (does|do) .*work", 3.0),
        (r"什么东西|什么呀这是|做什[么]用|干什[么]用|有什么用", 2.5),
    ),
    INTENT_MEMORY_QUERY: (
        (r"昨天|上次|之前讲|还记得|学过(什么|哪些)|我学(了|过)|(学|讲|说)过", 3.0),
        (r"remember|did i|last time|yesterday", 2.5),
        (r"我们讲到哪|讲到哪儿|故事到哪", 3.0),
    ),
    INTENT_WORD_LEARNING: (
        (r"怎么说|什么意思|怎么念|怎么读|教我|跟我读|读一遍|再说一遍", 3.0),
        (r"how (do|to).{0,12}\bsay\b|what does .* mean|say (it )?again|read (it )?again", 3.0),
        (r"^[a-zA-Z][a-zA-Z' ]{0,24}[.!?]?$", 1.5),  # 孤立英文短产出（跟读/造句）
    ),
    INTENT_COURT_TASK: (
        (r"早上好|早安|朝会|开(会|工)|任务|打卡|今天要(做|干)什[么]|准备好|开始吧", 3.0),
        (r"good morning|morning|start|ready|task", 2.0),
    ),
    INTENT_CHITCHAT: (
        (r"你好|你是谁|我喜欢你|我爱你|哈哈哈|好玩|你看我", 2.0),
        (r"hello|hi\b|who are you|i like you|funny|haha", 2.0),
    ),
}


class RuleClassifier:
    """规则打分分类器。返回 (intent, confidence, matched)。"""

    name = "rules"

    def classify(self, text: str) -> Tuple[str, float, Tuple[str, ...]]:
        t = (text or "").strip().lower()
        if not t:
            return INTENT_CHITCHAT, 0.0, ()
        best_intent, best_score, best_hits = INTENT_CHITCHAT, 0.0, ()
        for intent, rules in RULES.items():
            hits = _hits(t, tuple(p for p, _ in rules))
            if not hits:
                continue
            score = sum(w for p, w in rules if p in hits)
            if score > best_score:
                best_intent, best_score, best_hits = intent, score, tuple(hits)
        if best_score == 0.0:
            return INTENT_CHITCHAT, 0.35, ()
        # 置信度：≥6 分非常确信；1-2 条弱规则 → 中低置信，交给混合层
        conf = min(0.98, 0.55 + best_score * 0.08)
        return best_intent, conf, best_hits


class HybridClassifier:
    """规则优先；规则置信度 < threshold 时回调轻量模型（可换本地小模型/few-shot LLM）。

    model(text) -> intent 字符串。模型异常/返回非法 → 回落规则结果，永不阻塞。
    """

    name = "hybrid"

    def __init__(self, model: Callable[[str], str], threshold: float = 0.72) -> None:
        self._rules = RuleClassifier()
        self._model = model
        self._threshold = threshold

    def classify(self, text: str) -> Tuple[str, float, Tuple[str, ...]]:
        intent, conf, hits = self._rules.classify(text)
        if conf >= self._threshold:
            return intent, conf, hits
        try:
            m_intent = self._model(text)
        except Exception:  # noqa: BLE001 —— 轻量模型挂了不阻塞主链路
            return intent, max(conf, 0.5), hits
        if m_intent in ALL_INTENTS:
            return m_intent, 0.8, hits + ("model",)
        return intent, max(conf, 0.5), hits


# ------------------------------------------------------------------ 路由器
class Router:
    """意图分类 → 大臣路由（含上游 override 与剧本状态参与闲聊路由）。"""

    def __init__(self, classifier: Optional[RuleClassifier | HybridClassifier] = None) -> None:
        self._clf = classifier or RuleClassifier()

    def classify(self, text: str) -> Tuple[str, float, Tuple[str, ...]]:
        return self._clf.classify(text)

    def route(
        self,
        text: str,
        route_intent: str = "",
        script_state: str = "",
        assess_present: bool = False,
    ) -> RouteDecision:
        # 1) 上游显式指定意图 → 直接采信（override 也要合法）
        if route_intent in ALL_INTENTS:
            minister = INTENT_MINISTER.get(route_intent) or CHITCHAT_STATE_MINISTER.get(
                script_state, MINISTER_XIAOP
            )
            return RouteDecision(route_intent, minister, 1.0, ("override",), by="override")

        # 2) ASR 评估在场且孩子产出了英文 → 学词场景强信号（FR-E04 链路）
        intent, conf, hits = self.classify(text)
        if assess_present and intent in (INTENT_CHITCHAT, INTENT_WORD_LEARNING):
            intent, conf = INTENT_WORD_LEARNING, max(conf, 0.8)
            hits = hits + ("assess",)

        # 3) 意图 → 大臣；chitchat 看剧本状态
        if intent == INTENT_CHITCHAT:
            minister = CHITCHAT_STATE_MINISTER.get(script_state, MINISTER_XIAOP)
        else:
            minister = INTENT_MINISTER[intent]
        return RouteDecision(intent, minister, conf, hits, by="rules" if "model" not in hits else "model")


# ------------------------------------------------------------------ 标注评测集（60 条）
# 用于验收「路由错误率 ≤10%」。格式：(utterance, expected_intent)。
EVAL_SET: Tuple[Tuple[str, str], ...] = (
    # 朝会任务（10）
    ("早上好小P！", INTENT_COURT_TASK),
    ("今天朝会开始了吗", INTENT_COURT_TASK),
    ("今天的任务是什么", INTENT_COURT_TASK),
    ("我要打卡", INTENT_COURT_TASK),
    ("Good morning!", INTENT_COURT_TASK),
    ("我准备好了，开始吧", INTENT_COURT_TASK),
    ("我还没完成任务呢", INTENT_COURT_TASK),
    ("朝会几点开始", INTENT_COURT_TASK),
    ("今天要做什么", INTENT_COURT_TASK),
    ("Ready! Start!", INTENT_COURT_TASK),
    # 记忆询问（10）
    ("昨天我们讲到哪了", INTENT_MEMORY_QUERY),
    ("你还记得我的名字吗", INTENT_MEMORY_QUERY),
    ("我今天学过什么词", INTENT_MEMORY_QUERY),
    ("上次的故事讲完了吗", INTENT_MEMORY_QUERY),
    ("Do you remember my ball?", INTENT_MEMORY_QUERY),
    ("我们之前学过 apple 吗", INTENT_MEMORY_QUERY),
    ("昨天学了什么", INTENT_MEMORY_QUERY),
    ("我上次说到哪了", INTENT_MEMORY_QUERY),
    ("还记得昨天的小狗吗", INTENT_MEMORY_QUERY),
    ("Yesterday story, continue", INTENT_MEMORY_QUERY),
    # 学词（10）
    ("apple 怎么说", INTENT_WORD_LEARNING),
    ("这个用英语怎么说", INTENT_WORD_LEARNING),
    ("banana 是什么意思", INTENT_WORD_LEARNING),
    ("跟我读一遍好不好", INTENT_WORD_LEARNING),
    ("How do you say 西瓜", INTENT_WORD_LEARNING),
    ("I like apple.", INTENT_WORD_LEARNING),
    ("banana", INTENT_WORD_LEARNING),
    ("再教我一遍", INTENT_WORD_LEARNING),
    ("苹果怎么说呀", INTENT_WORD_LEARNING),
    ("What does sleepy mean?", INTENT_WORD_LEARNING),
    # 情绪安抚（10）
    ("我有点害怕", INTENT_EMOTION_COMFORT),
    ("我不想一个人睡", INTENT_EMOTION_COMFORT),
    ("我想妈妈了", INTENT_EMOTION_COMFORT),
    ("我好难过呀", INTENT_EMOTION_COMFORT),
    ("I am sad.", INTENT_EMOTION_COMFORT),
    ("我怕黑", INTENT_EMOTION_COMFORT),
    ("他抢我玩具，我生气了", INTENT_EMOTION_COMFORT),
    ("我有点想哭", INTENT_EMOTION_COMFORT),
    ("今天我不开心", INTENT_EMOTION_COMFORT),
    ("打雷了，我害怕", INTENT_EMOTION_COMFORT),
    # 万物（10）
    ("这是什么呀", INTENT_THINGS),
    ("那是什么呀", INTENT_THINGS),
    ("为什么冰箱会制冷", INTENT_THINGS),
    ("月亮为什么跟着我们走", INTENT_THINGS),
    ("What's this?", INTENT_THINGS),
    ("这个是做什么用的", INTENT_THINGS),
    ("彩虹是怎么来的", INTENT_THINGS),
    ("Why is the sea blue?", INTENT_THINGS),
    ("杯子是什么做的", INTENT_THINGS),
    ("蜗牛为什么走得慢", INTENT_THINGS),
    # 闲聊（10）
    ("你好呀", INTENT_CHITCHAT),
    ("你是谁呀", INTENT_CHITCHAT),
    ("我喜欢你", INTENT_CHITCHAT),
    ("哈哈哈真好玩", INTENT_CHITCHAT),
    ("Hello!", INTENT_CHITCHAT),
    ("你看我画的车车", INTENT_CHITCHAT),
    ("我今天穿了新鞋子", INTENT_CHITCHAT),
    ("I like you!", INTENT_CHITCHAT),
    ("我们一起玩吧", INTENT_CHITCHAT),
    ("嗨嗨嗨", INTENT_CHITCHAT),
)


def eval_router_accuracy(classifier: Optional[RuleClassifier | HybridClassifier] = None) -> float:
    """跑标注集返回准确率（验收断言 ≥0.9）。"""
    router = Router(classifier or RuleClassifier())
    correct = 0
    for text, expected in EVAL_SET:
        decision = router.route(text)
        if decision.intent == expected:
            correct += 1
    return correct / len(EVAL_SET)
