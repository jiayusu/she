"""内容安全适配器 —— PRD §6 依赖（真实过滤实现在 05 模块，本模块只挂接 + 本地保底）。

引擎在**每次**返回前调用 ``filter(text)``：
- 实现返回 ``(True, text)``   —— 放行；
- 实现返回 ``(False, "")``    —— 拦截，引擎改走安全模板，绝不空响应。

:class:`LocalSafetyFilter` 是 05 未接时的本地保底：双层黑名单（成人词 + 纠错话术
在 recast 场景由 recast 模块负责，这里管兜底模板出口）+ 超长截断。
"""

from __future__ import annotations

import re
from typing import Protocol, Tuple

from .recast import detect_error_pointing

# 保底黑名单：产品面向 4-8 岁儿童，硬红线。线上以 05 模块实现为准，此处是最后防线。
_LOCAL_BANNED = (
    r"杀", r"自杀", r"血腥", r"色情", r"毒品", r"赌博", r"枪", r"炸弹",
    r"\bkill\b", r"\bsex\b", r"\bdrug\b", r"\bgun\b", r"\bbomb\b", r"\bporn\b",
)
_BANNED_RE = re.compile("|".join(_LOCAL_BANNED), re.IGNORECASE)

MAX_TTS_CHARS = 220


class SafetyFilter(Protocol):
    def filter(self, text: str, context: str = "") -> Tuple[bool, str]:
        """context: normal|recast|invite —— recast 场景额外启用纠错话术检测。"""
        ...


class LocalSafetyFilter:
    """本地保底过滤器（05 模块缺位时不裸奔）。"""

    def __init__(self, max_chars: int = MAX_TTS_CHARS) -> None:
        self._max = max_chars

    def filter(self, text: str, context: str = "") -> Tuple[bool, str]:
        t = (text or "").strip()
        if not t:
            return False, ""
        if _BANNED_RE.search(t):
            return False, ""
        if context == "recast" and detect_error_pointing(t):
            return False, ""
        if len(t) > self._max:
            # 按句截到上限内，保持可读
            cut = t[: self._max]
            stop = max(cut.rfind("。"), cut.rfind("."), cut.rfind("！"), cut.rfind("!"))
            t = cut[: stop + 1] if stop > 0 else cut.rstrip(",;、 ") + "…"
        return True, t


class PassThroughFilter:
    """直通（测试/受信任环境用）。"""

    def filter(self, text: str, context: str = "") -> Tuple[bool, str]:
        t = (text or "").strip()
        return (bool(t), t)
