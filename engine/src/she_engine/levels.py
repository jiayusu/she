"""FR-E05 · 分级句式（L0-L5）。

每级注入三件事：句长上限 / 词汇池 / 是否给中文脚手架。
验收红线：L1 ≤5 词、L2 ≤10 词、L3+ ≤16 词（抽检达标 → ``check_level_fit``）。

词汇池内置精选（YL Starters/Movers/Flyers 风格）；另提供
``load_pools_from_cefrj()`` 从兄弟模块 kb 的 CEFR-J 词表重建（A1→L2 … C1→L5）。
"""

from __future__ import annotations

import csv
import os
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple


# ---------------------------------------------------------------- 词池（精选内置）
POOLS: Dict[int, Tuple[str, ...]] = {
    # L0：指认跟读，10 个生活锚点词
    0: ("apple", "water", "milk", "ball", "cat", "dog", "bye", "hi", "no", "yes"),
    # L1：朝会/探险常用 40 词（Starters 核心）
    1: (
        "apple", "banana", "water", "milk", "egg", "rice", "ball", "bear", "bird", "cat",
        "dog", "duck", "fish", "big", "small", "hot", "cold", "happy", "sad", "run",
        "jump", "eat", "drink", "sleep", "book", "bed", "cup", "door", "shoe", "hat",
        "morning", "night", "hello", "bye", "yes", "no", "thank you", "please", "sorry", "me",
    ),
    # L2：探险扩展 60 词（Starters+Movers 交集风格）
    2: (
        "fridge", "table", "chair", "window", "garden", "tree", "flower", "sun", "moon", "star",
        "rain", "wind", "river", "boat", "car", "bus", "train", "plane", "hand", "foot",
        "eye", "ear", "mouth", "nose", "shirt", "coat", "bread", "cake", "juice", "soup",
        "walk", "sing", "draw", "read", "write", "play", "help", "look", "listen", "smile",
        "warm", "cool", "soft", "hard", "sweet", "clean", "new", "old", "long", "short",
        "friend", "home", "family", "today", "tomorrow", "again", "more", "very", "good", "nice",
    ),
    # L3：完整句起步（Movers/Flyers 风格，接 CEFR A2-B1）
    3: (
        "kitchen", "bedroom", "bathroom", "village", "city", "beach", "forest", "island", "mountain", "weather",
        "autumn", "spring", "summer", "winter", "breakfast", "lunch", "dinner", "healthy", "hungry", "thirsty",
        "climb", "swim", "fly", "carry", "choose", "answer", "question", "story", "picture", "song",
        "because", "before", "after", "again", "always", "sometimes", "never", "together", "quickly", "slowly",
        "brave", "kind", "quiet", "loud", "round", "heavy", "light", "dark", "bright", "delicious",
    ),
    # L4/L5：开放表达，池子做引导不做上限
    4: (
        "adventure", "treasure", "journey", "secret", "surprise", "invitation", "celebrate", "remember", "imagine", "explore",
        "harvest", "season", "gravity", "magnet", "shadow", "measure", "compare", "describe", "explain", "predict",
    ),
    5: (
        "opinion", "reason", "example", "solution", "invention", "tradition", "festival", "culture", "environment", "universe",
    ),
}

SCAFFOLD_ZH: Dict[int, bool] = {0: True, 1: True, 2: True, 3: False, 4: False, 5: False}

# 验收红线（FR-E05）：L1≤5 / L2≤10 / L3+≤16
MAX_SENTENCE_WORDS: Dict[int, int] = {0: 3, 1: 5, 2: 10, 3: 16, 4: 16, 5: 16}

LEVEL_NAMES: Dict[int, str] = {
    0: "L0 跟读", 1: "L1 单句", 2: "L2 短句", 3: "L3 完整句", 4: "L4 连续表达", 5: "L5 开放讨论",
}


@dataclass(frozen=True)
class LevelRules:
    level: int
    max_words: int
    vocab_pool: Tuple[str, ...]
    scaffold_zh: bool

    def to_prompt(self) -> str:
        """注入 prompt 的分级硬规则块（FR-E05 的「按级注入」）。"""
        lines = [
            f"LEVEL {self.level} hard constraints:",
            f"- Max English sentence length: {self.max_words} words. Count before you output.",
        ]
        if self.level <= 2:
            lines.append("- Use ONLY words from this vocab pool (plus the child's own words): "
                         + ", ".join(self.vocab_pool[:60]))
        else:
            lines.append("- Prefer words from this pool: " + ", ".join(self.vocab_pool[:40]))
        if self.scaffold_zh:
            lines.append('- End with a short Chinese scaffold after " | " (one clause, no pinyin).')
        else:
            lines.append('- No Chinese scaffold. English only after "text".')
        if self.level == 0:
            lines.append("- One word or one two-word phrase at a time; model it twice.")
        return "\n".join(lines)


def get_level_rules(level: int) -> LevelRules:
    lv = max(0, min(5, int(level)))
    return LevelRules(
        level=lv,
        max_words=MAX_SENTENCE_WORDS[lv],
        vocab_pool=POOLS[lv],
        scaffold_zh=SCAFFOLD_ZH[lv],
    )


EN_WORD_RE = r"[A-Za-z]+(?:'[A-Za-z]+)?"


def _split_sentences(en: str) -> List[str]:
    en = en.strip()
    if not en:
        return []
    out: List[str] = []
    buf = ""
    for ch in en:
        buf += ch
        if ch in ".!?":
            out.append(buf.strip())
            buf = ""
    if buf.strip():
        out.append(buf.strip())
    return out


def max_sentence_words(text: str) -> int:
    """文本中最长英文句的词数（验收抽检口径：单句 ≤ 上限）。"""
    en_part = text.split("|", 1)[0]
    sents = _split_sentences(en_part)
    return max((len(s.split()) for s in sents), default=0)


def fit_text_to_level(text: str, level: int) -> Tuple[str, bool]:
    """确定性收敛到级别约束：单句 ≤ max_words，句数 ≤ max_sentences。

    超长句按词数硬截（保开头语义），放不下的尾部句丢弃。返回 (text, trimmed)。
    """
    lv = max(0, min(5, int(level)))
    cap = MAX_SENTENCE_WORDS[lv]
    max_sents = {0: 1, 1: 2, 2: 3, 3: 3, 4: 4, 5: 4}[lv]
    en_part, sep, zh_part = text.partition("|")
    sents = _split_sentences(en_part)
    trimmed = False
    kept: List[str] = []
    for s in sents[:max_sents]:
        words = s.split()
        if len(words) > cap:
            s = " ".join(words[:cap]).rstrip(",;:") + "."
            trimmed = True
        kept.append(s)
    trimmed = trimmed or len(sents) > max_sents
    out = " ".join(k if k.endswith((".", "!", "?")) else k + "." for k in kept).strip()
    if not out:
        out = "Try again!"
        trimmed = True
    if sep and zh_part:
        out = f"{out} | {zh_part.strip()}"
    return out, trimmed


def check_level_fit(text: str, level: int) -> bool:
    """验收抽检：最长单句是否 ≤ 该级词数上限（L1≤5 / L2≤10 / L3+≤16）。"""
    return max_sentence_words(text) <= MAX_SENTENCE_WORDS[max(0, min(5, int(level)))]


# ---------------------------------------------------------------- kb 联动（可选）
def load_pools_from_cefrj(path: str, per_level: int = 80) -> Dict[int, Tuple[str, ...]]:
    """从 kb/raw/cefrj-vocabulary-profile-1.5.csv 重建 L2-L5 词池。

    映射：A2→L2, B1→L3, B2→L4, C1→L5（A1 太泛不收录）。缺文件返回空 dict，
    引擎继续用内置池 —— 本地优先，在线兜底的同款思路。
    """
    if not os.path.isfile(path):
        return {}
    buckets: Dict[str, List[str]] = {"A2": [], "B1": [], "B2": [], "C1": []}
    with open(path, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            cefr = (row.get("CEFR") or "").strip().upper()
            head = (row.get("headword") or "").strip().lower()
            if cefr in buckets and head and " " not in head and head.isalpha():
                buckets[cefr].append(head)
    level_of = {"A2": 2, "B1": 3, "B2": 4, "C1": 5}
    return {level_of[k]: tuple(v[:per_level]) for k, v in buckets.items() if v}
