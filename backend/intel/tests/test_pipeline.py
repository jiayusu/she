"""FR-I01/02/03: 采集落库/去重/敏感前置过滤/LLM 结构化/kg_edges 校验。"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import archive
import config
import pipeline


def test_fetch_dedup_sensitive_and_raw_archive(conn, fake_provider):
    out = pipeline.fetch_and_store(conn, queries=list({"孩子 问倒 家长",
                                                       "儿童 十万个为什么"}))
    # fake provider 两个查询词共 4 条: 1 条与 q100 标题相似被合并, 1 条敏感词过滤前先入库
    assert out["fetched"] == 4
    assert out["inserted"] == 3          # q102 与 q100 同款 → 批内去重
    assert out["dups"] == 1 and out["dup_rate"] <= 0.5
    rows = conn.execute("SELECT * FROM candidates ORDER BY id").fetchall()
    assert all(r["raw_path"] for r in rows)              # FR-I08 原始归档路径可溯源
    assert archive.find_raw(rows[0]["raw_path"]) is not None
    assert conn.execute("SELECT COUNT(*) c FROM candidates WHERE content_id='q102'"
                        ).fetchone()["c"] == 0
    # fake provider 不消耗真实平台配额 → 台账不记账 (FR-I07 实际调用口径)
    assert conn.execute("SELECT COUNT(*) c FROM quota_ledger"
                        ).fetchone()["c"] == 0


def test_structure_success_rate_and_edge_clamp(conn, fake_provider, fake_llm):
    pipeline.fetch_and_store(conn, queries=["孩子 问倒 家长", "儿童 十万个为什么"])
    out = pipeline.structure_pending(conn)
    assert out["ok"] >= 2 and out["failed"] == 0
    ok_rate = out["ok"] / max(1, out["ok"] + out["failed"])
    assert ok_rate >= 0.95  # 验收: 结构化成功率 ≥95%
    row = conn.execute("SELECT * FROM candidates WHERE content_id='q100'").fetchone()
    assert row["status"] == "structured"
    assert row["child_question"] and row["fact"]
    edges = json.loads(row["kg_edges"])
    assert edges and edges[0]["rel"] in config.KG_EDGE_RELS
    assert 0.5 <= edges[0]["weight"] <= 3.0
    assert 1 <= row["difficulty"] <= 5


def test_sensitive_pre_filter_blocks_before_llm(conn, fake_provider, fake_llm):
    pipeline.fetch_and_store(conn, queries=["儿童 十万个为什么"])  # 含死亡话题 q103
    row = conn.execute("SELECT * FROM candidates WHERE content_id='q103'").fetchone()
    assert row is not None
    # §8 前置: sensitive 词在标题中, LLM 未运行即标记 (此处直接验证管线标记能力)
    hit = pipeline.sensitive_hit(row["title"], row["excerpt"])
    assert hit is not None
    # fake LLM 不会标 sensitive → 前置过滤兜底应在结构化时落 filtered
    pipeline.structure_pending(conn)
    row = conn.execute("SELECT * FROM candidates WHERE content_id='q103'").fetchone()
    assert row["status"] == "filtered"


def test_edge_clamp_rejects_bad_rels():
    edges = [{"head": "sky", "rel": "CausedBy", "tail": "light"},   # rel 不在白名单
             {"head": "sky", "rel": "RelatedTo", "tail": "sky"},     # 自环
             {"head": "Sky Blue", "rel": "RelatedTo", "tail": "颜色"},  # 非英文/形态不合规
             {"head": "sky", "rel": "HasProperty", "tail": "blue"}]  # 合法
    out = pipeline._clamp_edges(edges)
    assert out == [{"head": "sky", "rel": "HasProperty", "tail": "blue"}]


def test_llm_unavailable_leaves_pending(conn, fake_provider, monkeypatch):
    import llm_client
    pipeline.fetch_and_store(conn, queries=["孩子 问倒 家长"])
    def boom(*a, **k):
        raise llm_client.LLMUnavailable("no key")
    monkeypatch.setattr(llm_client, "_chat", boom)
    out = pipeline.structure_pending(conn)
    assert out["failed"] >= 1 and "error" in out
    n = conn.execute("SELECT COUNT(*) c FROM candidates WHERE status='pending_struct'"
                     ).fetchone()["c"]
    assert n >= 1  # 挂起重试, 不丢弃 (§5 优雅降级)
