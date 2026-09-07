"""FR-E09 · 降 L 鼓励机制。

孩子连续 2 次卡壳 → 自动降一级句式（下限 L0），写 parent_note，
并用低一级的句式重邀（用户故事 2：'跟着我说——apple。'）。

卡壳判定（任一即算）：
- 无实质话语（空串/纯语气词/静音标记）；
- ASR 置信度过低（< min_confidence）；
- ASR 文本过短且评估器未通过。

链路可观测：每次判定都发 ``engine_stuck(streak, level, downgraded)`` 埋点。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional, Tuple

STUCK_THRESHOLD = 2

_SILENCE_TOKENS = {"", "…", "...", "。", ".", "嗯", "呃", "啊", "额", "唔", "silence", "(silence)"}
_WORD_RE = re.compile(r"[A-Za-z]+|[\u4e00-\u9fff]")
_MIN_CONFIDENCE = 0.30
_MIN_MEANINGFUL_UNITS = 1


@dataclass(frozen=True)
class StuckVerdict:
    stuck: bool
    streak: int                 # 判定后的连续卡壳数
    downgraded: bool            # 本轮是否触发了降级
    new_level: int              # 判定后的会话级别
    reason: str = ""


class StuckTracker:
    """会话级卡壳状态机。实质性开口重置计数。"""

    def __init__(self, level: int = 1) -> None:
        self.level = max(0, min(5, int(level)))
        self.streak = 0

    def observe(
        self,
        utterance: str,
        asr_confidence: float = -1.0,
        assess_passed: bool = True,
        min_confidence: float = _MIN_CONFIDENCE,
    ) -> StuckVerdict:
        text = (utterance or "").strip().lower()
        text = text.strip("。．.，,~～、！!？?…· ")  # 纯标点/省略号视为无实质话语
        units = len(_WORD_RE.findall(text))
        if not text or text in _SILENCE_TOKENS:
            reason = "no_meaningful_speech"
        elif asr_confidence >= 0 and asr_confidence < min_confidence:
            reason = "low_asr_confidence"
        elif units < _MIN_MEANINGFUL_UNITS:
            reason = "too_short"
        elif not assess_passed and units <= 1 and asr_confidence >= 0 and asr_confidence < 0.5:
            reason = "assess_not_passed"
        else:
            # 实质开口 → 重置
            self.streak = 0
            return StuckVerdict(stuck=False, streak=0, downgraded=False, new_level=self.level)

        self.streak += 1
        downgraded = False
        # PRD FR-E09：连续第 2 次卡壳时降一级（只降一次，避免持续沉默被一路压到 L0）
        if self.streak == STUCK_THRESHOLD and self.level > 0:
            self.level -= 1
            downgraded = True
        return StuckVerdict(stuck=True, streak=self.streak, downgraded=downgraded, new_level=self.level,
                            reason=reason)

    def parent_note(self, verdict: StuckVerdict) -> Optional[Tuple[str, str, str]]:
        """触发降级时生成 (type, key, value)，供 memory_write 通知家长端。"""
        if not verdict.downgraded:
            return None
        return (
            "parent_note",
            "level_down",
            f"孩子连续{verdict.streak}次未开口，句式自动降至 L{verdict.new_level}，已换更低难度的邀请语",
        )
