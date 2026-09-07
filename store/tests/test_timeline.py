"""FR-M03 StoryArc 时间线: 时间查询解析与"天+剧本章节"组织, 准确率 ≥80%。"""
import time

import pytest

from memstore.temporal import parse

NOW = time.mktime(time.strptime("2026-09-04 15:00:00", "%Y-%m-%d %H:%M:%S"))


def day_of(offset):
    return time.strftime("%Y-%m-%d", time.localtime(NOW - offset * 86400))


# (查询, 期望属性) — 文档化语义见 memstore/temporal.py
CASES = [
    ("今天学了什么", {"day_from": "2026-09-04", "day_to": "2026-09-04"}),
    ("昨天的朝会", {"day_from": "2026-09-03", "day_to": "2026-09-03"}),
    ("前天吃的什么", {"day_from": "2026-09-02", "day_to": "2026-09-02"}),
    ("大前天唱歌", {"day_from": "2026-09-01", "day_to": "2026-09-01"}),
    ("3天前浇花", {"day_from": "2026-09-01", "day_to": "2026-09-01"}),
    ("最近画的画", {"day_from": day_of(2), "day_to": "2026-09-04"}),
    ("本周学的词", {"day_from": day_of(6), "day_to": "2026-09-04"}),
    ("上周的故事", {"day_from": day_of(13), "day_to": day_of(7)}),
    ("上个月的旅行", {"day_from": day_of(60), "day_to": day_of(30)}),
    ("第3章的冒险", {"chapter": 3}),
    ("第 2 话", {"chapter": 2}),
    ("第一次见小熊", {"first": True}),
    ("我第一次教它说话", {"first": True}),
    ("今天第一次举手", {"first": True, "day_from": "2026-09-04"}),
    ("上周第一次得小星星", {"first": True, "day_from": day_of(13)}),
    ("7天前种的苹果树", {"day_from": day_of(7), "day_to": day_of(7)}),
    ("这几天学的歌", {"day_from": day_of(2), "day_to": "2026-09-04"}),
    ("昨天的第1章", {"day_from": "2026-09-03", "chapter": 1}),
    ("无时间词普通查询", {"day_from": None, "chapter": None}),
    ("最近一周", {"day_from": day_of(2)}),  # "最近"命中, 一周留在文本
]


def test_temporal_parse_accuracy():
    """时间查询准确率 ≥80%(PRD 对齐度量#10), 自测集 20 例。"""
    ok = 0
    for query, expect in CASES:
        got = parse(query, now=NOW)
        good = all(got[k] == v for k, v in expect.items())
        if good:
            ok += 1
        else:  # pragma: no cover - 打印便于修错
            print(f"FAIL {query!r}: got day={got['day_from']}..{got['day_to']} "
                  f"ch={got['chapter']} first={got['first']}")
    accuracy = ok / len(CASES)
    assert accuracy >= 0.8, f"时间查询准确率 {accuracy:.0%} < 80%"


def test_temporal_text_remainder():
    got = parse("昨天第一次吃apple", now=NOW)
    assert got["text"] == "吃apple"
    assert got["first"] is True
    assert got["day_from"] == "2026-09-03"


def test_storyarc_chapter_timeline(svc):
    """episode 按'天+剧本章节'组织, 章节过滤查询命中对应章节。"""
    svc.write_episode(utterance="morning greeting song", chapter=1, ts=NOW - 86400 * 3)
    svc.write_episode(utterance="forest adventure begins", chapter=2, ts=NOW - 86400 * 2)
    svc.write_episode(utterance="river crossing puzzle", chapter=3, ts=NOW - 86400)
    out = svc.recall("forest adventure", k=5)
    assert out["results"][0]["chapter"] == 2
    out = svc.recall("第3章 冒险", k=5)
    assert all(r["chapter"] == 3 for r in out["results"])


def test_first_occurrence_query(svc):
    """"第一次 X" → 最早一条匹配记忆。"""
    t0 = time.mktime(time.strptime("2026-08-01 10:00:00", "%Y-%m-%d %H:%M:%S"))
    svc.write_episode(utterance="第一次骑自行车", ts=t0)
    svc.write_episode(utterance="又骑自行车了", ts=t0 + 86400 * 10)
    svc.write_episode(utterance="骑自行车比赛", ts=t0 + 86400 * 20)
    out = svc.recall("第一次骑自行车", k=3)
    assert out["results"][0]["utterance"] == "第一次骑自行车"
    assert out["results"][0]["ts"] == t0


def test_temporal_filter_excludes_other_days(svc):
    t0 = time.mktime(time.strptime("2026-09-04 10:00:00", "%Y-%m-%d %H:%M:%S"))
    svc.write_episode(utterance="milk", ts=t0)
    svc.write_episode(utterance="apple", ts=t0 - 86400 * 8)  # 8 天前 = 上周窗口内
    out = svc.recall("最近 apple", k=5, now=NOW)  # apple 在 8 天前, 不在"最近"窗口
    assert [r["day"] for r in out["results"]] == ["2026-09-04"]
    out = svc.recall("上周 apple", k=5, now=NOW)
    assert [r["day"] for r in out["results"]] == [day_of(8)]
