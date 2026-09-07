"""FR-M04 巩固管线: KG 热更新衔接 / 发音评估闸门 / 冲突待审队列 / outbox 重推。"""
from conftest import make_svc


def test_consolidate_memories_to_kg(tmp_path, kg):
    """巩固批次走 KG runtime-consolidate, KG 版本+1。"""
    svc = make_svc(tmp_path, kg_url=kg.url)
    try:
        ep1 = svc.write_episode(utterance="milk and cup on the table",
                                scene="breakfast", assess=90)
        out = svc.consolidate({
            "child_id": "child-001",
            "memories": [{"scene": "breakfast", "words": ["milk", "cup"],
                          "assess": 88, "episode_ids": [ep1["id"]]},
                         {"scene": "breakfast", "words": ["milk", "cup"],
                          "assess": 91, "episode_ids": [ep1["id"]]}],
            "threshold": 2})
        assert out["promoted"] >= 1
        assert out["kg_versions"], "KG 版本应 +1"
        assert kg.calls[-1]["path"] == "/kg/runtime-consolidate"
        assert out["queued"] is False
    finally:
        svc.close()


def test_consolidate_edges_to_kg(tmp_path, kg):
    svc = make_svc(tmp_path, kg_url=kg.url)
    try:
        out = svc.consolidate({
            "edges": [{"head": "apple", "rel": "IsA", "tail": "fruit",
                       "assess": 92}]})
        assert kg.calls[-1]["path"] == "/kg/edges:batch"
        assert kg.calls[-1]["payload"]["source"] == "memory-consolidate"
        assert out["promoted"] == 1
    finally:
        svc.close()


def test_pronunciation_gate_blocks_wrong_words(tmp_path, kg):
    """风险对策: 孩子说错的词(assess 低于阈值)不得固化进 KG。"""
    svc = make_svc(tmp_path, kg_url=kg.url)
    try:
        out = svc.consolidate({
            "edges": [{"head": "wong", "rel": "IsA", "tail": "fruit",
                       "assess": 55}]})
        assert out["promoted"] == 0
        assert out["rejected"][0]["reason"] == "assess_below_gate"
        assert not kg.calls, "低分词不应触达 KG"
        # 无 assess 字段时保守放行(Agent 侧 FR-G06 已过滤), 闸门只拦"明确不合格"
        out2 = svc.consolidate({"edges": [{"head": "cup", "rel": "RelatedTo",
                                           "tail": "milk"}]})
        assert out2["promoted"] == 1
    finally:
        svc.close()


def test_conflicts_into_pending_queue(tmp_path, kg):
    """KG 返回的冲突边镜像进待审队列, 可人工 resolve。"""
    kg.conflicts_to_return = [{
        "id": 7, "head": "apple", "rel": "HasProperty", "tail": "cold",
        "kind": "contradiction", "detail": "已有 apple HasProperty hot"}]
    svc = make_svc(tmp_path, kg_url=kg.url)
    try:
        out = svc.consolidate({"edges": [{"head": "apple", "rel": "HasProperty",
                                          "tail": "cold", "assess": 95}]})
        assert len(out["conflicts"]) == 1
        rows = svc.consolidator.conflicts("open")
        assert len(rows) == 1 and rows[0]["kg_conflict_id"] == 7
        kg.conflicts_to_return = []
        res = svc.consolidator.resolve(rows[0]["id"], accept=False)
        assert res["action"] == "delete"
        assert svc.consolidator.conflicts("open") == []
    finally:
        svc.close()


def test_kg_down_outbox_then_flush(tmp_path, kg):
    """KG 不可达 → 批次入 outbox 不丢失; 恢复后 flush 重推成功。"""
    svc = make_svc(tmp_path, kg_url=kg.url)
    try:
        kg.down = True
        out = svc.consolidate({"memories": [{"scene": "park", "words": ["slide"],
                                             "assess": 85}]})
        assert out["queued"] is True
        kg.down = False
        res = svc.consolidator.flush()
        assert res["sent"] == 1 and res["failed"] == 0
        assert kg.calls[-1]["path"] == "/kg/runtime-consolidate"
    finally:
        svc.close()


def test_consolidation_ledger_records_child(tmp_path, kg):
    """回流台账记录孩子归属与 KG 版本(72h 删除合规依据)。"""
    svc = make_svc(tmp_path, kg_url=kg.url)
    try:
        svc.consolidate({"child_id": "child-007",
                         "edges": [{"head": "dog", "rel": "IsA", "tail": "animal",
                                    "assess": 90}]})
        rows = svc.db.q("SELECT * FROM consolidation_ledger")
        assert len(rows) == 1
        assert rows[0]["child_id"] == "child-007"
        assert rows[0]["kg_version"] == 2
    finally:
        svc.close()
