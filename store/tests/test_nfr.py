"""非功能: 统一审计(3 年保留) / 崩溃恢复 ≤2s / 72h 删除合规 / 埋点。"""
import json
import time

from conftest import make_svc

DAY = 86400.0
NOW0 = time.mktime(time.strptime("2026-09-01 10:00:00", "%Y-%m-%d %H:%M:%S"))


# ---------------------------------------------------------------- 审计
def test_audit_covers_all_stores(svc):
    """谁写入/何时/内容摘要: 写入/召回/剪枝/快照全留痕。"""
    svc.write_episode(utterance="hello world", actor="agent:route",
                      session_id="s1")
    svc.recall("hello", actor="agent:ahai")
    svc.snapshot(actor="parent")
    svc.working_push("s1", "push text", actor="agent:engine")
    entries = svc.audit.query(limit=50)
    actors = {e["actor"] for e in entries}
    actions = {e["action"] for e in entries}
    assert {"agent:route", "agent:ahai", "parent", "agent:engine"} <= actors
    assert {"ep_write", "recall", "snapshot", "working_push"} <= actions
    write = next(e for e in entries if e["action"] == "ep_write")
    assert "hello world" in write["summary"]


def test_audit_jsonl_daily_file(svc):
    svc.write_episode(utterance="jsonl audit row")
    files = list(svc.cfg.audit_dir().glob("*.jsonl"))
    assert files, "按天 JSONL 审计文件应存在"
    rows = [json.loads(line) for line in files[0].read_text(encoding="utf-8").splitlines()]
    assert any(r["action"] == "ep_write" for r in rows)


def test_audit_retention_3_years(svc):
    """审计保留 3 年: 更早的条目被清理, 近期保留(表+文件)。"""
    svc.write_episode(utterance="recent row")
    old_iso = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(NOW0 - 4 * 365 * DAY))
    with svc.db.tx() as conn:
        conn.execute("INSERT INTO audit_log(ts, actor, action, target, summary) "
                     "VALUES(?,?,?,?,?)", (old_iso, "system", "ep_write", "old", "old"))
    removed = svc.audit.enforce_retention()
    assert removed >= 1
    assert all("old" not in e["summary"] for e in svc.audit.query(limit=200))
    assert any("recent row" in e["summary"] for e in svc.audit.query(limit=200))


# ---------------------------------------------------------------- 崩溃恢复 ≤2s
def test_crash_recovery_under_2s(tmp_path):
    """服务重启后 session 状态从情景库重建 ≤2s(含 5000 条情景压力)。"""
    svc = make_svc(tmp_path)
    try:
        now = time.time()
        for i in range(5000):
            svc.write_episode(utterance=f"dialogue turn {i}",
                              session_id=f"s-{i % 50}",
                              ts=now - (5000 - i) * 0.1)
    finally:
        svc.close()
    svc2 = make_svc(tmp_path)  # 模拟重启(重新打开同一数据目录)
    try:
        state = svc2.session_recover("s-7")
        assert state["rebuilt"] == 10
        assert state["recovered_ms"] < 2000, f"恢复耗时 {state['recovered_ms']}ms"
        assert state["turns"], "恢复出的工作记忆不应为空"
        assert state["script_state"] == {}
    finally:
        svc2.close()


def test_crash_recovery_keeps_script_state(tmp_path):
    svc = make_svc(tmp_path)
    try:
        svc.session_state("s-a", script_state={"plot": "朝会", "act": 3}, chapter=4)
        svc.write_episode(utterance="morning roll call", session_id="s-a")
    finally:
        svc.close()
    svc2 = make_svc(tmp_path)
    try:
        state = svc2.session_recover("s-a")
        assert state["script_state"] == {"plot": "朝会", "act": 3}
        assert state["chapter"] == 4
        assert state["turns"][-1]["text"] == "morning roll call"
    finally:
        svc2.close()


# ---------------------------------------------------------------- 删除合规
def test_erase_child_data_72h_with_manifest(tmp_path, kg):
    """家长删除: 五库+回流数据物理清除, 产出微调数据集剔除清单, KG 侧删除推送。"""
    svc = make_svc(tmp_path, kg_url=kg.url)
    try:
        svc.write_episode(utterance="child data A", child_id="child-a",
                          salience=0.9)  # 自动进白名单, 顺带覆盖白名单清除路径
        svc.write_episode(utterance="child data B", child_id="child-b")
        svc.consolidate({"child_id": "child-a",
                         "edges": [{"head": "apple", "rel": "IsA", "tail": "fruit",
                                    "assess": 90}]})
        assert svc.salience.whitelist_items(child_id="child-a")
        out = svc.erase("child-a", requested_by="parent")
        assert out["status"] == "completed"
        assert out["deadline_ts"] - out["duration_ms"] / 1000 > 0  # deadline 在未来
        assert out["stats"]["episodes"] == 1
        assert not svc.episodic.all_rows(child_id="child-a")
        assert svc.episodic.all_rows(child_id="child-b")      # 其他孩子不受影响
        assert svc.db.q("SELECT * FROM consolidation_ledger WHERE child_id='child-a'") == []
        manifest = [json.loads(line)
                    for line in open(out["manifest"], encoding="utf-8")]
        assert manifest and all(m["purpose"] == "fine_tune_dataset_removal"
                                for m in manifest)
        assert any(m["type"] == "whitelist" for m in manifest)
        # KG 收到删除指令
        del_calls = [c for c in kg.calls if c["payload"].get("source") == "erase"]
        assert del_calls and del_calls[0]["payload"]["edges"][0]["op"] == "del"
    finally:
        svc.close()


def test_erase_purge_all(tmp_path):
    svc = make_svc(tmp_path)
    try:
        for child in ("a", "b"):
            svc.write_episode(utterance=f"data {child}", child_id=child)
        svc.salience.add(content="buffer row", salience=0.5)
        out = svc.erase("any", purge_all=True)
        assert out["stats"]["episodes"] == 2
        assert svc.episodic.counts()["active"] == 0
        assert svc.salience.count() == 0
        assert svc.audit.query(action="erase")  # 审计保留(合规证明)
        jobs = svc.erasure.jobs()
        assert jobs[0]["status"] == "completed"
    finally:
        svc.close()


# ---------------------------------------------------------------- 埋点
def test_metrics_names_per_prd(svc):
    """§8: ep_write / recall_hit(k, latency) / prune_count / consolidate_edges /
    snapshot_ok。"""
    svc.write_episode(utterance="metric probe")
    svc.recall("probe")
    svc.snapshot()
    snap = svc.metrics.snapshot()
    counters = snap["counters"]
    assert "ep_write" in counters
    assert "recall_hit" in counters and "recall_total" in counters
    assert "snapshot_ok" in counters
    assert "ep_write_ms" in snap["latency_ms"]
    assert "recall_ms" in snap["latency_ms"]
    assert "recall_k" in snap["latency_ms"]     # recall_hit(k, latency)
    before = svc.metrics.snapshot()["counters"].get("prune_count", 0)
    svc.write_episode(utterance="fading", salience=0.4, ts=NOW0)
    out = svc.lifecycle.decay_pass(ts=NOW0 + 100 * DAY)
    assert any(p["utterance"] == "fading" for p in out["pruned"])
    assert svc.metrics.snapshot()["counters"]["prune_count"] >= before + 1
