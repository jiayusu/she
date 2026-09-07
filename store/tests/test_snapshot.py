"""FR-M08 快照与回滚: 手动/每日自动, 任意版本 ≤1 分钟恢复, 索引损坏自愈。"""
import time

DAY = 86400.0
NOW0 = time.mktime(time.strptime("2026-09-01 10:00:00", "%Y-%m-%d %H:%M:%S"))


def test_snapshot_and_rollback_within_budget(svc):
    """快照 → 继续写入 → 回滚: 数据恢复且版本单调递增, 耗时 ≤1 分钟。"""
    v0 = svc.db.version()
    svc.write_episode(utterance="before snapshot", salience=0.4, ts=NOW0)
    snap = svc.snapshot(note="before-bad-batch")
    assert snap["version"] > v0 and snap["counts"]["active"] == 1
    # "坏批次": 误写 3 条
    for i in range(3):
        svc.write_episode(utterance=f"bad write {i}", salience=0.4, ts=NOW0 + i)
    assert svc.episodic.counts()["active"] == 4
    out = svc.rollback(snap["version"])
    assert "error" not in out
    assert out["duration_ms"] < 60_000          # ≤1 分钟红线
    assert out["rolled_back_to"] == snap["version"]
    assert out["version"] > snap["version"]     # 版本单调递增
    assert svc.episodic.counts()["active"] == 1
    assert svc.episodic.all_rows()[0]["utterance"] == "before snapshot"


def test_rollback_rebuilds_searchable_index(svc):
    svc.write_episode(utterance="apple pie recipe", salience=0.4, ts=NOW0)
    snap = svc.snapshot()
    svc.write_episode(utterance="garbage noise", salience=0.4, ts=NOW0 + 1)
    svc.rollback(snap["version"])
    out = svc.recall("apple pie", k=3)
    assert any("apple pie recipe" == r["utterance"] for r in out["results"])
    assert not any("garbage" in r["utterance"] for r in out["results"])


def test_rollback_missing_version_404(svc):
    out = svc.rollback(999)
    assert "error" in out


def test_daily_auto_snapshot_once_per_day(svc):
    """每日自动快照: 同一天只做一次(后台任务逻辑)。"""
    day1 = svc.run_daily_jobs(ts=NOW0 + 8 * 3600)
    day1b = svc.run_daily_jobs(ts=NOW0 + 9 * 3600)  # 同日再跑
    assert "snapshot" in day1
    assert "snapshot" not in day1b
    snaps = svc.snapshots.list()
    assert len(snaps) == 1 and snaps[0]["note"] == "daily-auto"


def test_daily_job_decay_and_snapshot_together(svc):
    svc.write_episode(utterance="fading memory", salience=0.4, ts=NOW0)
    out = svc.run_daily_jobs(ts=NOW0 + 200 * DAY)  # 0.4*exp(-10)≈0 → 剪枝
    assert out["decay"]["pruned"]
    assert svc.episodic.counts()["cold"] == 1
    assert "snapshot" in out


def test_startup_rebuild_after_index_corruption(tmp_path):
    """FAISS 索引损坏 → 启动自检从 SQLite 原始数据重建(风险对策)。"""
    from conftest import make_svc
    svc = make_svc(tmp_path)
    try:
        for i in range(5):
            svc.write_episode(utterance=f"memory {i} about music", salience=0.5)
    finally:
        svc.close()
    vec = svc.cfg.vector_path()
    assert vec.exists()
    vec.write_bytes(b"CORRUPTED!!!")  # 模拟索引文件损坏
    svc2 = make_svc(tmp_path)
    try:
        counts = svc2.episodic.counts()
        assert counts["indexed"] == counts["active"] + counts["cold"]
        out = svc2.recall("memory music", k=3)
        assert out["results"]
    finally:
        svc2.close()
