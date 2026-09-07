"""she_engine — LLM 剧情引擎（PRD 01 · V1.0）

「开口是唯一货币」的执行层：把孩子的开口转化为剧情推进，
把大臣人格转化为语言。其他模块（ASR/视觉/记忆/内容安全）向本模块供数或受它调度。

对外接口（PRD §6）::

    in:  { child_utterance, asr_result, assess_result, level, route_intent, ctx_bundle }
    out: { speaker, text, emotion_tag, memory_write[] }   # FR-E06 Schema
"""

from .types import (
    AssessResult,
    AsrResult,
    CtxBundle,
    MemoryWrite,
    TurnRequest,
    TurnResponse,
)
from .engine import Engine, EngineConfig

__all__ = [
    "Engine",
    "EngineConfig",
    "TurnRequest",
    "TurnResponse",
    "MemoryWrite",
    "AsrResult",
    "AssessResult",
    "CtxBundle",
]

__version__ = "1.0.0"
