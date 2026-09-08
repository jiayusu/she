"""temporal.py — StoryArc 时间查询解析(FR-M03)。

把"第一次/上周/第 N 章/昨天/最近"类自然语言时间词解析为结构化过滤条件
(对齐 BMAM temporal query)。语义约定:

  今天/今日      day = 当天
  昨天/昨日      day = 当天-1
  前天           day = 当天-2
  大前天         day = 当天-3
  N天前          day = 当天-N(精确单日)
  最近/这几天    [当天-2, 当天]
  本周/这周      [当天-6, 当天]
  上周           [当天-13, 当天-7](上一个自然 7 天块)
  上个月         [当天-60, 当天-30]
  第N章/话/集    chapter = N
  第一次/首次    first = True(窗口内最早一条, 文本部分做匹配)

时间词剥离后的剩余文本作为内容匹配串。
"""
import re
import time

_MARKERS = [
    ("第一次", "first"), ("第1次", "first"), ("首次", "first"),
    ("今天", "today"), ("今日", "today"),
    ("昨天", "yesterday"), ("昨日", "yesterday"),
    ("前天", "2d"), ("大前天", "3d"),
    ("上周", "last_week"), ("本周", "this_week"), ("这周", "this_week"),
    ("上个月", "last_month"), ("最近", "recent"), ("这几天", "recent"),
]
_CHAPTER = re.compile(r"第\s*(\d+)\s*[章话集]")


def parse(query: str, now: float | None = None) -> dict:
    now = time.time() if now is None else now
    today = time.strftime("%Y-%m-%d", time.localtime(now))
    day_of = lambda offset: time.strftime(  # noqa: E731
        "%Y-%m-%d", time.localtime(now - offset * 86400))

    out = {"query": query, "first": False, "day_from": None, "day_to": None,
           "chapter": None, "text": "", "matched": []}
    text = query.strip()

    for marker, kind in _MARKERS:
        if marker in text:
            text = text.replace(marker, "")
            out["matched"].append({"marker": marker, "kind": kind})
            if kind == "first":
                out["first"] = True
            elif kind == "today":
                out["day_from"] = out["day_to"] = today
            elif kind == "yesterday":
                out["day_from"] = out["day_to"] = day_of(1)
            elif kind == "2d":
                out["day_from"] = out["day_to"] = day_of(2)
            elif kind == "3d":
                out["day_from"] = out["day_to"] = day_of(3)
            elif kind == "recent":
                out["day_from"], out["day_to"] = day_of(2), today
            elif kind == "this_week":
                out["day_from"], out["day_to"] = day_of(6), today
            elif kind == "last_week":
                out["day_from"], out["day_to"] = day_of(13), day_of(7)
            elif kind == "last_month":
                out["day_from"], out["day_to"] = day_of(60), day_of(30)

    m = _CHAPTER.search(text)
    if m:
        out["chapter"] = int(m.group(1))
        out["matched"].append({"marker": m.group(0), "kind": "chapter"})
        text = _CHAPTER.sub("", text)

    m = re.search(r"(\d+)\s*天前", text)
    if m:
        n = int(m.group(1))
        out["day_from"] = out["day_to"] = day_of(n)
        out["matched"].append({"marker": m.group(0), "kind": "n_days_ago"})
        text = re.sub(r"(\d+)\s*天前", "", text)

    out["text"] = text.strip(" 的了吗呢啊，。？? ")
    return out


def is_temporal(parsed: dict) -> bool:
    return bool(parsed["matched"])
