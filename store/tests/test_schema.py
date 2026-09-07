"""FR-M01 五库 Schema: 物理分离 / 容量约定 / ER 完整性。"""
from memstore.vector import HashingEmbedder


def test_five_stores_physically_separated(svc):
    """五库各自独立表: working/episodic(+cold)/salience(+whitelist)/procedural,
    语义库=KG 外部 kg.db(health 标注衔接方式)。"""
    tables = {r["name"] for r in svc.db.q(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"working_turns", "episodes", "episodes_cold",
            "salience_buffer", "whitelist", "procedural"} <= tables
    h = svc.health()
    assert set(h["stores"]) == {"working", "episodic", "semantic", "salience",
                                "procedural"}
    assert h["stores"]["semantic"]["kind"] == "kg"  # 语义库不入本库, 经热更接口衔接


def test_capacity_conventions(cfg, svc):
    assert svc.working.cap == 10          # 工作记忆 10 条
    assert svc.salience.cap == 1000       # 显著性缓冲 1k 条
    assert svc.procedural.cap == 500      # 程序性库 500 条


def test_episode_fields_complete(svc):
    """FR-M02 episode 字段: {ts, scene, utterance, assess, emotion, salience}
    + StoryArc 时间线字段(FR-M03: day/chapter/arc)。"""
    row = svc.write_episode(utterance="I like apple", scene="breakfast", assess=90.0,
                            emotion="happy", emotion_v=0.6, salience=0.4,
                            session_id="s1", ts=1756900000.0)
    for key in ("ts", "scene", "utterance", "assess", "emotion", "salience",
                "day", "chapter"):
        assert key in row, f"episode 缺字段 {key}"
    assert row["day"] == "2025-09-03"  # ts 对应本地日期
    assert row["chapter"] == 1


def test_embedding_deterministic_and_rebuildable(svc):
    """嵌入确定性 → SQLite 原始数据可重建索引(风险表对策)。"""
    e = HashingEmbedder(256)
    import numpy as np
    v1 = e.embed("I like apple")
    v2 = e.embed("I like apple")
    assert np.allclose(v1, v2)
    assert abs(float(np.linalg.norm(v1)) - 1.0) < 1e-5  # L2 归一
    row = svc.write_episode(utterance="apple pie is sweet")
    n = svc.episodic.rebuild_index()
    assert n == svc.episodic.counts()["active"] + svc.episodic.counts()["cold"]
    assert len(svc.index) == n


def test_numpy_fallback_backend():
    """无 faiss 环境时 numpy 后端等价可用。"""
    from memstore.vector import VectorIndex
    import numpy as np
    idx = VectorIndex(16, use_faiss=False)
    emb = HashingEmbedder(16)
    idx.add([1, 2], np.stack([emb.embed("apple fruit"), emb.embed("bus car")]))
    hits = idx.search(emb.embed("apple"), k=1)
    assert hits[0][0] == 1
    idx.remove([1])
    assert len(idx) == 1
