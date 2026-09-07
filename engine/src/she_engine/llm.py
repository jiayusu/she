"""LLM Provider 抽象层。

- :class:`OpenAICompatProvider` —— 线上真调用（OpenAI 兼容 /v1/chat/completions，stdlib HTTP）。
- :class:`MockProvider` —— 离线确定性 provider：测试、拔网线演示、CI 全靠它。
- :class:`FlakyProvider` —— 包一层「前 N 次失败」，用于测 FR-E06 重试与 FR-E07 兜底。
- :class:`CachedProvider` —— 同 prompt 命中缓存，压 FR-E08 成本/延迟。

provider 不许抛异常穿透到编排层之外：失败统一返回 ``LLMResult(ok=False)``。
"""

from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol

from .types import (
    MINISTER_AHAI,
    MINISTER_LAONIE,
    MINISTER_WANGGUAN,
    MINISTER_XIAOP,
    MINISTER_XINGXING,
)


@dataclass
class LLMResult:
    ok: bool
    text: str = ""                      # 模型原文（应含 FR-E06 JSON）
    ttft_ms: float = 0.0                # 首 token 延迟（非流式≈请求耗时）
    total_ms: float = 0.0
    tokens_in: int = 0
    tokens_out: int = 0
    error: str = ""

    @property
    def cost_yuan(self) -> float:
        """按国产轻量模型常见价目估：¥0.8/M in + ¥2/M out。"""
        return self.tokens_in * 0.8 / 1_000_000 + self.tokens_out * 2.0 / 1_000_000


class LLMProvider(Protocol):
    def complete(self, system_prompt: str, user_prompt: str) -> LLMResult: ...


# ----------------------------------------------------------------- Mock
def _clamp_words(text: str, max_words: int) -> str:
    """把英文部分截到句长上限（按空格切词，中文脚手架不计）。"""
    parts = text.split("|")
    en = parts[0].strip()
    zh = parts[1].strip() if len(parts) > 1 else ""
    words = en.split()
    if len(words) > max_words:
        en = " ".join(words[:max_words]).rstrip(",.;:!?") + "."
    return f"{en} | {zh}" if zh else en


class MockProvider:
    """离线确定性响应。

    引擎在 user_prompt 顶部写入一行 ``__ENGINE_META__ {json}``（minister/mode/level/
    recast 等），Mock 只消费这一行，产出符合 FR-E06 的 JSON。真模型同样读得到这行
    结构化上下文，属于无害冗余。
    """

    name = "mock"

    def complete(self, system_prompt: str, user_prompt: str) -> LLMResult:
        t0 = time.perf_counter()
        meta = {}
        m = re.search(r"__ENGINE_META__\s*(\{.*\})", user_prompt)
        if m:
            try:
                meta = json.loads(m.group(1))
            except json.JSONDecodeError:
                meta = {}
        text = self._respond(meta)
        out = json.dumps(
            {
                "speaker": meta.get("minister", "xiaop"),
                "text": text,
                "emotion_tag": meta.get("emotion_hint", "happy"),
                "memory_write": self._memory_writes(meta),
            },
            ensure_ascii=False,
        )
        return LLMResult(
            ok=True,
            text=out,
            ttft_ms=(time.perf_counter() - t0) * 1000,
            total_ms=(time.perf_counter() - t0) * 1000,
            tokens_in=len(user_prompt) // 4 + 40,
            tokens_out=len(out) // 4 + 20,
        )

    # -- 各模式 ---------------------------------------------------------------
    def _respond(self, meta: Dict[str, Any]) -> str:
        minister = meta.get("minister", MINISTER_XIAOP)
        mode = meta.get("mode", "normal")
        level = int(meta.get("level", 1))
        limits = {0: 3, 1: 5, 2: 10, 3: 16, 4: 16, 5: 16}
        cap = limits.get(level, 16)
        utter = str(meta.get("child_utterance", "")).strip()

        if mode == "recast":
            corrected = str(meta.get("recast_corrected", "")) or utter or "Nice try!"
            if minister == MINISTER_XINGXING and corrected:
                # 用户故事 1：child "I like apple" → "I like apples too! Apples are sweet."
                en, zh = f"{corrected} too! Apples are sweet.", "你也喜欢呀!"
            else:
                en, zh = {
                    MINISTER_XIAOP: ("Apples are sweet.", "苹果甜甜的!"),
                    MINISTER_LAONIE: ("Apples grow on the tree.", "苹果长在树上哦。"),
                    MINISTER_AHAI: ("Apples are yummy.", "苹果很好吃呀。"),
                    MINISTER_WANGGUAN: ("Apples are fruit!", "苹果是水果!"),
                    MINISTER_XINGXING: ("I like apples too! Apples are sweet.", "你也喜欢呀!"),
                }[minister]
            return f"{en} | {zh}"

        if mode == "invite":
            word = str(meta.get("invite_word", "apple"))
            body = f"Say: {word}!" if level == 0 else f"Say: {word}. Your turn!"
            return _clamp_words(f"{body} | 跟我说——{word}。", max(cap, 4))

        # normal：各大臣固定口癖 + 针对孩子话语的简单追问，保证盲测可区分
        style = {
            MINISTER_XIAOP: ("Kada! Task done! Salute!", "咔哒!任务达成!敬礼!"),
            MINISTER_LAONIE: ("Em—the story goes on.", "嗯——故事继续啦。"),
            MINISTER_XINGXING: ("Say again with me!", "再跟我念一遍!"),
            MINISTER_AHAI: ("The sea hears you.", "海都听见啦。"),
            MINISTER_WANGGUAN: ("Wow! Tell me more!", "哇!多讲一点!"),
        }[minister]
        en, zh = style
        tail = f"You said: {utter}." if utter else "Your turn!"
        return _clamp_words(f"{en} {tail} | {zh}", max(cap, 16))

    def _memory_writes(self, meta: Dict[str, Any]) -> List[Dict[str, str]]:
        writes: List[Dict[str, str]] = []
        if meta.get("mode") == "recast" and meta.get("recast_word"):
            writes.append({"type": "learned_word", "key": "word", "value": str(meta["recast_word"])})
        if meta.get("mode") == "normal" and meta.get("scene") == "adventure":
            writes.append({"type": "story_progress", "key": "advance", "value": "1"})
        return writes


# ----------------------------------------------------------------- 线上 OpenAI 兼容
class OpenAICompatProvider:
    """OpenAI 兼容 chat/completions（stdlib 实现，无第三方依赖）。"""

    name = "openai_compat"

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        timeout_s: float = 2.0,     # 首 token ≤800ms(P95) 的红线 → 超时立刻降级
        temperature: float = 0.7,
        max_tokens: int = 220,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout_s = timeout_s
        self.temperature = temperature
        self.max_tokens = max_tokens

    def complete(self, system_prompt: str, user_prompt: str) -> LLMResult:
        t0 = time.perf_counter()
        body = json.dumps(
            {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": self.temperature,
                "max_tokens": self.max_tokens,
                # 强约束 JSON 输出：服务支持则直接生效，不支持则靠 FR-E06 重试链
                "response_format": {"type": "json_object"},
            },
            ensure_ascii=False,
        ).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=body,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
            return LLMResult(ok=False, error=f"{type(exc).__name__}: {exc}",
                             total_ms=(time.perf_counter() - t0) * 1000)
        total_ms = (time.perf_counter() - t0) * 1000
        try:
            text = data["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError):
            return LLMResult(ok=False, error="malformed response", total_ms=total_ms)
        usage = data.get("usage") or {}
        return LLMResult(
            ok=True, text=text, ttft_ms=total_ms, total_ms=total_ms,
            tokens_in=int(usage.get("prompt_tokens", 0)),
            tokens_out=int(usage.get("completion_tokens", 0)),
        )


# ----------------------------------------------------------------- 测试/降级包装器
class FlakyProvider:
    """前 ``fail_times`` 次调用返回失败，之后透传。测 FR-E06 重试 / FR-E07 兜底。"""

    name = "flaky"

    def __init__(self, inner: LLMProvider, fail_times: int = 999, error: str = "network down") -> None:
        self._inner = inner
        self._remain = fail_times
        self._error = error

    def complete(self, system_prompt: str, user_prompt: str) -> LLMResult:
        if self._remain > 0:
            self._remain -= 1
            return LLMResult(ok=False, error=self._error)
        return self._inner.complete(system_prompt, user_prompt)


class GarbledProvider:
    """永远返回非 JSON 乱码：专测 FR-E06「解析失败重试 1 次→再失败走模板」。"""

    name = "garbled"

    def __init__(self, payload: str = "抱歉我不知道该怎么回答你呢~") -> None:
        self._payload = payload

    def complete(self, system_prompt: str, user_prompt: str) -> LLMResult:
        return LLMResult(ok=True, text=self._payload, ttft_ms=5.0, total_ms=8.0)


class CachedProvider:
    """精确匹配 (system,user) 的 LRU 缓存。万物/朝会等高频问法命中后零成本。"""

    name = "cached"

    def __init__(self, inner: LLMProvider, maxsize: int = 256) -> None:
        self._inner = inner
        self._maxsize = maxsize
        self._cache: Dict[tuple, LLMResult] = {}
        self.hits = 0

    def complete(self, system_prompt: str, user_prompt: str) -> LLMResult:
        key = (system_prompt, user_prompt)
        if key in self._cache:
            self.hits += 1
            return self._cache[key]
        res = self._inner.complete(system_prompt, user_prompt)
        if res.ok:
            if len(self._cache) >= self._maxsize:
                self._cache.pop(next(iter(self._cache)))
            self._cache[key] = res
        return res
