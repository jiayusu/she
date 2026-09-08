"""FR-I02: 质量排序 + 标题相似度去重 (阈值 0.8)。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipeline import dedup, rank_score, title_similarity

A = "孩子为什么天空是蓝色的？家长被问倒了"


def test_similarity_identical_and_unrelated():
    assert title_similarity(A, A) == 1.0
    assert title_similarity(A, "今天股市大盘走势分析") < 0.1


def test_similarity_threshold_merge():
    b = "孩子问为什么天空是蓝色的？家长被问倒了怎么办"  # 灌水变体: 插词+尾巴
    c = "孩子问为什么月亮会跟着我走"
    assert title_similarity(A, b) > 0.8
    assert title_similarity(A, c) < 0.5


def test_dedup_keeps_higher_score_and_counts():
    items = [
        {"title": A, "score": 5.0, "content_id": "a"},
        {"title": "孩子问为什么天空是蓝色的？家长被问倒了怎么办", "score": 2.0, "content_id": "b"},
        {"title": "完全无关的另一个问题标题示例", "score": 1.0, "content_id": "c"},
    ]
    kept, merged, dups = dedup(items)
    assert len(kept) == 2 and dups == 1
    assert kept[0]["content_id"] == "a"          # 分高者保留
    assert merged[0]["content_id"] == "b"


def test_dedup_cross_check_against_db_titles():
    kept, merged, dups = dedup(
        [{"title": "孩子为什么天空是蓝色的？家长被问倒了", "score": 1.0, "content_id": "x"}],
        against=[(99, "孩子为什么天空是蓝色的？家长被问倒了(旧)")])
    assert kept == [] and dups == 1 and merged[0]["merged_into"] == 99


def test_rank_score_orders_by_engagement():
    hot = {"vote_up": 500, "comment_count": 30, "authority": "2"}
    cold = {"vote_up": 5, "comment_count": 0, "authority": "1"}
    assert rank_score(hot) > rank_score(cold)
