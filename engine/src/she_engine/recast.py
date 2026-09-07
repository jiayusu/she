"""FR-E04 · Recast 改写（吸收式纠错）。

把 ASR 的「发音评估结果 + 原句」编译成 Recast 指令注入 prompt：
LLM 以正确形式重述孩子的意思并自然扩展一句，**绝不指出错误**。

三重防线（验收：盲评 100 条回应中打断式纠错 ≤5 条）::

    1. 提示词铁律 —— 杏杏人格禁则 + recast_directive 明说"不许纠错式表达"
    2. 后置扫描   —— detect_error_pointing() 抓"你说错了/应该/不对哦/wrong/should"等
    3. 兜底重述   —— 命中扫描后，由模板层做一次确定性 Recast（模板永远安全）

交互约定（PRD 用户故事 1）::

    孩子 "I like apple" → 杏杏 "I like apples too! Apples are sweet."
    （正确形式 + 扩展 + 零点名批评）
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from .types import AssessResult

# 打断式纠错话术黑名单（中英）。设计上偏保守：宁可多拦，交给模板重述。
ERROR_POINTING_PATTERNS: tuple = (
    r"你说错", r"说错了", r"不对哦", r"不对哟", r"这样说才对", r"应该说",
    r"你说的不对", r"再试一次.{0,4}对", r"纠正你", r"你错了", r"错了(哦|呀|啦)",
    r"不是.{0,10}而是", r"注意.{0,8}(说|读)", r"重(新|遍)说对",
    r"\bwrong\b", r"\bmistake\b", r"\berror\b", r"\bincorrect\b",
    r"should (say|be|have said)", r"you said it wrong", r"try again.{0,12}(correct|right)",
    r"the correct (word|way|answer)", r"not\s+\w+.{0,8},?\s+(it'?s|say)",
)

_ERROR_POINTING_RE = re.compile("|".join(ERROR_POINTING_PATTERNS), re.IGNORECASE)

# 中文语法术语（低龄场景一律不出现，出现即视为打断式教学）
_GRAMMAR_JARGON_RE = re.compile(r"语法|复数|单数|过去式|时态|主谓|冠词|第三人称", re.IGNORECASE)


@dataclass(frozen=True)
class RecastDirective:
    """编译后的 Recast 注入块。has_error=False 时为空串（非纠错轮不注入）。"""

    has_error: bool
    text: str = ""

    def __bool__(self) -> bool:  # 允许 prompt 渲染处 f"{directive or ''}"
        return self.has_error and bool(self.text)


def build_recast_directive(assess: Optional[AssessResult]) -> RecastDirective:
    """把评估结果编译成 Recast 指令（FR-E04：评估结果+原句 → 提示词）。"""
    if assess is None or not assess.has_error:
        return RecastDirective(has_error=False)
    original = (assess.original or "").strip()
    corrected = (assess.corrected or "").strip()
    etype = (assess.error_type or "").strip()
    lines = [
        "RECAST MODE (mandatory, this is the product's north star):",
        '- The child just said: "' + original + '"'
        + (f"  [assessment flag: {etype}]" if etype else ""),
    ]
    if corrected:
        lines.append(
            f'- The target form is: "{corrected}". Restate the child\'s meaning using the '
            "target form, then extend naturally with ONE related short sentence "
            "(e.g. child: \"I like apple\" -> \"I like apples too! Apples are sweet.\")."
        )
    else:
        lines.append(
            "- No explicit target form was provided: restate the child's meaning in a clearly "
            "well-formed short sentence, then extend naturally with ONE related short sentence."
        )
    lines += [
        "- NEVER point out the mistake. Never say the child was wrong. No 'you should say', "
        "no 'wrong', no grammar terms, no side-by-side comparison with the child's sentence.",
        "- The error disappears silently inside your fluent restatement (absorption).",
        "- Keep the child's own words wherever they were already correct.",
    ]
    return RecastDirective(has_error=True, text="\n".join(lines))


def detect_error_pointing(text: str) -> bool:
    """输出守门：是否含打断式纠错/语法术语（FR-E04 后置防线 2）。"""
    if not text:
        return False
    return bool(_ERROR_POINTING_RE.search(text) or _GRAMMAR_JARGON_RE.search(text))


def template_recast(assess: AssessResult, minister: str = "xingxing") -> str:
    """防线 3：确定性 Recast 模板（LLM 两次违规或全挂时仍保证「吸收式纠错」）。"""
    corrected = (assess.corrected or assess.original or "").strip() or "Well done!"
    extend = {
        "xingxing": ("I like it too!", "我也喜欢!"),
        "xiaop": ("Good job!", "好样的!"),
        "laonie": ("The story goes on.", "故事继续啦。"),
        "ahai": ("The sea heard you.", "海听见啦。"),
        "wangguan": ("Wow, nice words!", "哇,说得真好!"),
    }.get(minister, ("I like it too!", "我也喜欢!"))
    en, zh = extend
    return f"{corrected} {en} | {zh}"
