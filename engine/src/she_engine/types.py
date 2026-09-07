"""核心数据类型 —— PRD §6 接口契约。

引擎只依赖本文件定义的形状，与上下游模块（ASR/记忆/安全/TTS）解耦：
上游把 dict 打进来，下游拿 4 字段 Schema（FR-E06）出去。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------- 六类意图（FR-E02）
# 朝会任务 / 记忆询问 / 学词 / 情绪安抚 / 万物 / 闲聊
INTENT_COURT_TASK = "court_task"
INTENT_MEMORY_QUERY = "memory_query"
INTENT_WORD_LEARNING = "word_learning"
INTENT_EMOTION_COMFORT = "emotion_comfort"
INTENT_THINGS = "things"
INTENT_CHITCHAT = "chitchat"

ALL_INTENTS = (
    INTENT_COURT_TASK,
    INTENT_MEMORY_QUERY,
    INTENT_WORD_LEARNING,
    INTENT_EMOTION_COMFORT,
    INTENT_THINGS,
    INTENT_CHITCHAT,
)

# ---------------------------------------------------------------- 五大臣（FR-E01/FR-E10）
MINISTER_XIAOP = "xiaop"        # 小P    · 企鹅小管家 —— 朝会任务 / 重邀
MINISTER_LAONIE = "laonie"      # 老颞   · 老蛇说书人 —— 探险剧情
MINISTER_XINGXING = "xingxing"  # 杏杏   · 杏色小鹦鹉 —— 学词 / Recast
MINISTER_AHAI = "ahai"          # 阿海   · 老海獭 —— 记忆询问 / 情绪安抚 / 睡前
MINISTER_WANGGUAN = "wangguan"  # 王冠   · 爱提问的小王冠 —— 万物

EMOTION_TAGS = (
    "happy", "curious", "excited", "calm", "gentle",
    "proud", "sleepy", "worried", "surprised",
)


def _s(v: Any, default: str = "") -> str:
    return v if isinstance(v, str) else default


def _f(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


@dataclass
class AsrResult:
    """ASR 模块（02）的原始识别输出。"""

    text: str = ""
    confidence: float = 0.0
    words: List[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: Optional[Dict[str, Any]]) -> "AsrResult":
        if not d:
            return cls()
        words = d.get("words") or []
        return cls(
            text=_s(d.get("text")),
            confidence=_f(d.get("confidence")),
            words=[str(w) for w in words] if isinstance(words, list) else [],
        )


@dataclass
class AssessResult:
    """发音评估结果（02 模块产出，FR-E04 的输入）。

    corrected/target_form：评估器给出的「正确形式」，Recast 以它为准重述。
    error_type 例：plural / tense / pronunciation / article ...
    """

    has_error: bool = False
    original: str = ""
    corrected: str = ""
    error_type: str = ""
    word: str = ""          # 本轮目标词（学词任务）
    score: float = 0.0      # 发音分 0-100

    @classmethod
    def from_dict(cls, d: Optional[Dict[str, Any]]) -> "AssessResult":
        if not d:
            return cls()
        return cls(
            has_error=bool(d.get("has_error", False)),
            original=_s(d.get("original") or d.get("text")),
            corrected=_s(d.get("corrected") or d.get("target_form")),
            error_type=_s(d.get("error_type")),
            word=_s(d.get("word")),
            score=_f(d.get("score")),
        )


@dataclass
class CtxBundle:
    """FR-E08 上下文包。上游（记忆模块 04）可以直接给，不给则引擎自查记忆存储。"""

    recent_turns: List[Dict[str, str]] = field(default_factory=list)   # [{speaker,text}]
    learned_words_today: List[str] = field(default_factory=list)
    script_state: Optional[Dict[str, Any]] = None

    @classmethod
    def from_dict(cls, d: Optional[Dict[str, Any]]) -> "CtxBundle":
        if not d:
            return cls()
        turns = d.get("recent_turns") or []
        words = d.get("learned_words_today") or []
        return cls(
            recent_turns=[t for t in turns if isinstance(t, dict)],
            learned_words_today=[str(w) for w in words],
            script_state=d.get("script_state") if isinstance(d.get("script_state"), dict) else None,
        )


@dataclass
class TurnRequest:
    """PRD §6 输入。全部字段可由 dict 构造（容错）。"""

    child_utterance: str = ""
    asr_result: AsrResult = field(default_factory=AsrResult)
    assess_result: AssessResult = field(default_factory=AssessResult)
    level: int = 1                       # L0-L5
    route_intent: str = ""               # 上游可强制路由；空则引擎自行分类
    ctx_bundle: Optional[CtxBundle] = None

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "TurnRequest":
        lv = d.get("level", 1)
        try:
            lv = int(lv)
        except (TypeError, ValueError):
            lv = 1
        return cls(
            child_utterance=_s(d.get("child_utterance")),
            asr_result=AsrResult.from_dict(d.get("asr_result")),
            assess_result=AssessResult.from_dict(d.get("assess_result")),
            level=max(0, min(5, lv)),
            route_intent=_s(d.get("route_intent")),
            ctx_bundle=CtxBundle.from_dict(d.get("ctx_bundle")),
        )


@dataclass
class MemoryWrite:
    """FR-E06 Schema 的 memory_write 条目 —— 引擎负责转交记忆存储（04）落盘。

    type: learned_word / story_progress / parent_note / fact / emotion
    """

    type: str
    key: str
    value: str

    def to_dict(self) -> Dict[str, str]:
        return {"type": self.type, "key": self.key, "value": self.value}


@dataclass
class TurnResponse:
    """PRD §6 输出。``to_dict()`` 严格返回 FR-E06 的 4 字段；
    调度元信息（路由/降级/延迟/灯色…）放 :attr:`meta`，供内部与硬件消费，不进 Schema。"""

    speaker: str           # 大臣 id，TTS 据此取音色
    text: str              # 面向孩子的话（可能含中文脚手架），TTS 直接消费
    emotion_tag: str
    memory_write: List[MemoryWrite] = field(default_factory=list)
    meta: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """PRD §6 / FR-E06 严格输出（TTS/上游只看这四个键）。"""
        return {
            "speaker": self.speaker,
            "text": self.text,
            "emotion_tag": self.emotion_tag,
            "memory_write": [m.to_dict() for m in self.memory_write],
        }
