"""FR-E06 · 输出 JSON Schema 强约束。

``{speaker, text, emotion_tag, memory_write[]}``

解析链（验收：无效 JSON 率 <2%，任何情况不空响应）::

    LLM 原文 → extract_json（剥 code fence / 截取首个平衡大括号）
            → json.loads 失败 → 引擎带 repair 提示重试 1 次
            → 仍失败 → schema_ok=False，编排层走兜底模板（FR-E07）

校验规则：speaker 非空 / text 非空且 ≤上限 / emotion_tag 合法 /
memory_write[].{type,key,value}齐全且 type 合法。可修复字段就地修复（emotion_tag 兜底、
memory_write 丢弃坏条目），结构性缺失才算失败。
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from .types import EMOTION_TAGS, MemoryWrite, TurnResponse

MEMORY_WRITE_TYPES = ("learned_word", "story_progress", "parent_note", "fact", "emotion")

MAX_TEXT_CHARS = 400  # TTS 一口气的话术上限（超长由 level 截断前置处理，这里是硬顶）

SCHEMA_INSTRUCTION = """OUTPUT FORMAT (strict): Return ONLY one JSON object, no markdown, no extra words:
{"speaker": "<minister id>", "text": "<what you say to the child, may include a short Chinese scaffold after | >", "emotion_tag": "happy|curious|excited|calm|gentle|proud|sleepy|worried|surprised", "memory_write": [{"type": "learned_word|story_progress|parent_note|fact|emotion", "key": "<short key>", "value": "<short value>"}]}
"memory_write" may be []. Everything the child hears must be inside "text"."""


@dataclass
class SchemaParseOutcome:
    ok: bool
    response: Optional[TurnResponse] = None
    error: str = ""
    repaired: bool = False        # 就地修复过（emotion_tag/坏条目剔除）
    raw: str = ""


def extract_json_blob(raw: str) -> Optional[str]:
    """从模型原文里抠出第一个平衡的 JSON 对象；容忍 ```json 围栏与前后废话。"""
    if not raw:
        return None
    raw = raw.strip()
    raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.MULTILINE).strip()
    start = raw.find("{")
    if start < 0:
        return None
    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(raw)):
        ch = raw[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return raw[start:i + 1]
    return None


def _fix_emotion(tag: Any) -> Tuple[str, bool]:
    t = str(tag or "").strip().lower()
    if t in EMOTION_TAGS:
        return t, False
    # 常见别名归一，减轻模型输出抖动
    alias = {
        "joy": "happy", "glad": "happy", "happiness": "happy",
        "wonder": "curious", "question": "curious",
        "love": "gentle", "soft": "gentle", "warm": "gentle",
        "sleep": "sleepy", "tired": "sleepy",
        "sad": "worried", "angry": "worried", "fear": "worried",
        "wow": "surprised", "amazed": "surprised",
        "cheer": "excited", "hype": "excited",
        "win": "proud", "great": "proud",
        "chill": "calm", "peace": "calm",
    }
    if t in alias:
        return alias[t], True
    return "happy", True  # 未知标签 → 兜底值（算修复，不算失败）


def _parse_memory_writes(arr: Any) -> Tuple[List[MemoryWrite], int]:
    writes: List[MemoryWrite] = []
    dropped = 0
    if not isinstance(arr, list):
        return writes, 0
    for item in arr[:8]:  # 单轮最多 8 条，防止刷屏
        if not isinstance(item, dict):
            dropped += 1
            continue
        wtype = str(item.get("type", "")).strip()
        key = str(item.get("key", "")).strip()[:64]
        value = str(item.get("value", "")).strip()[:200]
        if wtype not in MEMORY_WRITE_TYPES or not key:
            dropped += 1
            continue
        writes.append(MemoryWrite(type=wtype, key=key, value=value))
    return writes, dropped


def parse_llm_output(raw: str, expected_speaker: str = "") -> SchemaParseOutcome:
    """LLM 原文 →（可能修复过的）TurnResponse；结构性失败返回 ok=False。"""
    blob = extract_json_blob(raw or "")
    if blob is None:
        return SchemaParseOutcome(ok=False, error="no json object found", raw=raw or "")
    try:
        obj = json.loads(blob)
    except json.JSONDecodeError as exc:
        return SchemaParseOutcome(ok=False, error=f"json decode: {exc}", raw=raw)
    if not isinstance(obj, dict):
        return SchemaParseOutcome(ok=False, error="json is not an object", raw=raw)

    repaired = False
    text = str(obj.get("text", "")).strip()
    if not text:
        return SchemaParseOutcome(ok=False, error="empty text", raw=raw)
    if len(text) > MAX_TEXT_CHARS:
        text = text[:MAX_TEXT_CHARS].rstrip() + "…"
        repaired = True

    if expected_speaker:
        # TTS 只认本次路由的大臣：模型嘴瓢回了别人 id 也强制拉回（记一次修复）
        repaired = repaired or str(obj.get("speaker", "")).strip() != expected_speaker
        speaker = expected_speaker
    else:
        speaker = str(obj.get("speaker", "")).strip()
    emotion, fixed = _fix_emotion(obj.get("emotion_tag"))
    repaired = repaired or fixed

    writes, dropped = _parse_memory_writes(obj.get("memory_write"))
    repaired = repaired or dropped > 0

    return SchemaParseOutcome(
        ok=True,
        response=TurnResponse(
            speaker=speaker, text=text, emotion_tag=emotion, memory_write=writes
        ),
        repaired=repaired,
        raw=raw,
    )


def repair_user_prompt(original_user_prompt: str, bad_raw: str) -> str:
    """FR-E06：解析失败后的唯一一次重试提示。"""
    return (
        "Your previous reply was NOT valid JSON, so it was discarded:\n"
        f"---\n{bad_raw[:600]}\n---\n"
        "Try again. Return ONLY the JSON object exactly as specified. No markdown, no commentary.\n\n"
        f"{original_user_prompt}"
    )
