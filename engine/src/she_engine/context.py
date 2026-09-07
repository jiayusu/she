"""FR-E08 · 上下文注入：最近 10 轮工作记忆 + 今日已学词 + 当前剧本状态。

预算红线：整块 ≤1500 token（估算器对中英混排友好）。
截断策略按优先级：剧本状态（必保）> 今日已学词（必保，最多 40 个）
> 最近轮次（从最旧开始丢，直到预算内）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

MAX_CTX_TOKENS = 1500
MAX_RECENT_TURNS = 10
MAX_LEARNED_WORDS = 40


def est_tokens(s: str) -> int:
    """粗估 token：中文≈0.9/字，英文≈1.3/词。对预算控制足够，不追求精确分词。"""
    if not s:
        return 0
    zh = sum(1 for ch in s if "\u4e00" <= ch <= "\u9fff")
    rest = len(s) - zh
    return max(1, round(zh * 0.9 + rest / 3.8))


@dataclass
class CtxStats:
    tokens: int = 0
    turns_kept: int = 0
    turns_dropped: int = 0
    truncated: bool = False


@dataclass
class ContextBlock:
    """渲染进 prompt 的 ``{ctx_block}``。"""

    text: str = ""
    stats: CtxStats = field(default_factory=CtxStats)


def build_ctx_block(
    recent_turns: Sequence[Dict[str, str]],
    learned_words_today: Sequence[str],
    script_state_line: str,
    budget: int = MAX_CTX_TOKENS,
) -> ContextBlock:
    """拼装 ≤budget 的上下文块。输入轮次应为「旧→新」顺序。"""
    turns = [t for t in recent_turns if isinstance(t, dict) and (t.get("text") or t.get("speaker"))]
    turns = turns[-MAX_RECENT_TURNS:]                       # 最多 10 轮
    words = list(learned_words_today)[:MAX_LEARNED_WORDS]

    state_part = f"[SCRIPT STATE]\n{script_state_line}"
    words_part = "[WORDS LEARNED TODAY]\n" + (", ".join(words) if words else "(none yet)")
    state_tokens = est_tokens(state_part) + est_tokens(words_part)

    # 预算内尽量多保留最近轮次：优先丢最旧的
    kept: List[Dict[str, str]] = list(turns)
    stats = CtxStats()
    while True:
        convo = "\n".join(f"{t.get('speaker', 'child')}: {t.get('text', '')}" for t in kept)
        convo_part = "[RECENT TURNS (old->new)]\n" + convo if kept else "[RECENT TURNS] (new session)"
        total = state_tokens + est_tokens(convo_part)
        if total <= budget or not kept:
            stats = CtxStats(tokens=total, turns_kept=len(kept), turns_dropped=len(turns) - len(kept),
                             truncated=len(turns) > len(kept))
            text = f"{state_part}\n{words_part}\n{convo_part}"
            return ContextBlock(text=text, stats=stats)
        kept.pop(0)  # 丢最旧一轮
