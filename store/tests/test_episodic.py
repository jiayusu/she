"""FR-M02 情景写入与跨天召回: 写入 ≤20ms / 检索 top-k ≤50ms / 向量正确性。"""
import statistics
import time


def test_write_latency_p95_under_20ms(svc):
    """验收: 写入 ≤20ms(哈希嵌入+SQLite+FAISS 入库全路径)。"""
    lat = []
    for i in range(300):
        t0 = time.perf_counter()
        svc.write_episode(utterance=f"today we learn word {i}", scene="class",
                          session_id="perf")
        lat.append((time.perf_counter() - t0) * 1000)
    p95 = statistics.quantiles(lat, n=20)[-1]
    assert p95 < 20, f"写入 p95={p95:.2f}ms 超 20ms 红线"
    assert svc.metrics.snapshot()["latency_ms"]["ep_write_ms"]["p95"] < 20


def test_recall_latency_p95_under_50ms(svc):
    """验收: 检索 top-k ≤50ms。"""
    for i in range(300):
        svc.write_episode(utterance=f"episode number {i} about fruit {i % 7}",
                          scene="s", session_id="perf")
    lat = []
    for i in range(200):
        out = svc.recall("episode fruit", k=5)
        lat.append(out["latency_ms"])
    p95 = statistics.quantiles(lat, n=20)[-1]
    assert p95 < 50, f"召回 p95={p95:.2f}ms 超 50ms 红线"


def test_recall_relevance_and_topk(svc):
    """向量召回: 相似内容排前, k 截断生效。"""
    svc.write_episode(utterance="I picked a red apple in the garden", scene="garden")
    svc.write_episode(utterance="the bus is big and yellow", scene="street")
    svc.write_episode(utterance="apple juice is sweet", scene="kitchen")
    out = svc.recall("apple", k=2)
    assert len(out["results"]) == 2
    assert "apple" in out["results"][0]["utterance"]
    assert all("bus" not in r["utterance"] for r in out["results"])


def test_recall_hits_metric(svc):
    svc.write_episode(utterance="milk in the cup", scene="breakfast")
    before = svc.metrics.snapshot()["counters"].get("recall_total", 0)
    out = svc.recall("milk cup", k=3)
    after = svc.metrics.snapshot()["counters"]
    assert after["recall_total"] == before + 1
    assert after.get("recall_hit", 0) >= 1
    assert "recall_ms" in svc.metrics.snapshot()["latency_ms"]


def test_cross_day_recall(svc):
    """跨天召回: 3 天前的记忆仍可命中。"""
    now = time.time()
    svc.write_episode(utterance="we planted a seed in the pot", scene="garden",
                      ts=now - 3 * 86400)
    svc.write_episode(utterance="we watered the flowers", scene="garden",
                      ts=now - 1 * 86400)
    out = svc.recall("seed pot", k=3)
    assert any("planted a seed" in r["utterance"] for r in out["results"])
