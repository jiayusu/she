"""FR-M05 遗忘剪枝(EMA 衰减+白名单物理隔离) / FR-M06 再巩固恢复。"""
import math
import time

DAY = 86400.0
NOW0 = time.mktime(time.strptime("2026-09-01 10:00:00", "%Y-%m-%d %H:%M:%S"))


def test_ema_decay_and_prune(svc):
    """低显著性按 EMA 衰减, 低于阈值剪除 → 冷存储 + 剪枝日志可审计。"""
    svc.write_episode(utterance="random chat about weather", salience=0.5,
                      ts=NOW0)
    # 60 天后: 0.5 * exp(-0.05*60) ≈ 0.0249 < 0.05 → 剪除
    out = svc.lifecycle.decay_pass(ts=NOW0 + 60 * DAY)
    assert len(out["pruned"]) == 1
    counts = svc.episodic.counts()
    assert counts["active"] == 0 and counts["cold"] == 1
    logs = svc.audit.query(action="prune")
    assert len(logs) == 1 and "episode:1" in logs[0]["target"]
    assert svc.metrics.snapshot()["counters"]["prune_count"] == 1


def test_ema_partial_decay_then_touch(svc):
    """未到阈值的记忆衰减但不剪除; 再提及(touch)可回血。"""
    # 0.78 < 白名单阈值 0.8, 参与衰减: 0.78*exp(-0.5)≈0.473
    svc.write_episode(utterance="medium memory", salience=0.78, ts=NOW0)
    svc.lifecycle.decay_pass(ts=NOW0 + 10 * DAY)
    row = svc.episodic.all_rows()[0]
    assert 0.45 < row["salience"] < 0.5
    assert svc.episodic.counts()["cold"] == 0


def test_whitelist_never_pruned_3year(svc):
    """验收: 白名单 3 年模拟零丢失(逐日衰减 1095 步)。"""
    svc.write_episode(utterance="milestone: first English sentence!", salience=1.0,
                      kind="milestone", ts=NOW0, ref_id="mw-milestone")
    assert svc.salience.whitelist_has("mw-milestone")
    for d in range(1, 3 * 365 + 1):  # 3 年逐日衰减
        svc.lifecycle.decay_pass(ts=NOW0 + d * DAY)
    counts = svc.episodic.counts()
    assert counts["active"] == 1 and counts["cold"] == 0      # 零丢失
    assert svc.salience.whitelist_items()[0]["ref_id"] == "mw-milestone"
    assert svc.audit.query(action="prune") == []              # 从未被剪


def test_whitelist_flag_row_exempt(svc):
    """whitelisted=1 的情景行同样豁免剪枝(双保险)。"""
    svc.write_episode(utterance="star moment", salience=0.9, ts=NOW0)
    svc.lifecycle.decay_pass(ts=NOW0 + 400 * DAY)
    assert svc.episodic.counts()["active"] == 1


def test_manual_whitelist_only_grows(svc):
    """白名单只增不删: 无删除接口, 人工可增。"""
    svc.whitelist_add("mw-manual-1", "家长标记: 第一首会唱的歌", actor="parent")
    svc.whitelist_add("mw-manual-1", "重复添加幂等")
    items = svc.salience.whitelist_items()
    assert len(items) == 1
    assert items[0]["source"] == "manual"
    # 服务上不存在任何删除白名单的公开方法
    assert not hasattr(svc, "whitelist_remove")
    assert not hasattr(svc.salience, "whitelist_remove")


def test_reconsolidation_restore_and_boost(svc):
    """FR-M06: 已剪除记忆被重新提及 → 冷存储恢复并加权。"""
    svc.write_episode(utterance="we made a paper boat", salience=0.5, ts=NOW0)
    svc.lifecycle.decay_pass(ts=NOW0 + 90 * DAY)               # 剪除
    assert svc.episodic.counts() == {"active": 0, "cold": 1, "indexed": 1}
    # 孩子: "之前那个纸船…" → 召回命中冷存储, 自动恢复
    out = svc.recall("paper boat", k=3)
    assert out["restored"], "冷存储命中应触发再巩固"
    counts = svc.episodic.counts()
    assert counts["active"] == 1 and counts["cold"] == 0
    row = svc.episodic.get(out["restored"][0]["id"])
    assert row["reconsolidated"] == 1
    assert row["salience"] > 0.5                                # 加权恢复
    assert svc.audit.query(action="reconsolidate")


def test_reconsolidation_content_intact(svc):
    """恢复后内容与向量检索均完好。"""
    svc.write_episode(utterance="painted a blue whale", salience=0.4, ts=NOW0)
    svc.lifecycle.decay_pass(ts=NOW0 + 120 * DAY)
    svc.recall("blue whale", k=2)
    out = svc.recall("painted whale", k=2)
    assert any("painted a blue whale" == r["utterance"] for r in out["results"])
