import pytest
from memstore.service import MemoryService


def commit(svc, turn="t1", previous=None, revision=0):
    return svc.learning.commit({
        "child_id": "synthetic", "session_id": "lesson", "turn_id": turn,
        "device_id": "simulator", "previous_turn_id": previous,
        "request_hash": turn.ljust(64, "0"), "revision": revision,
        "response": {"teaching_action": {"target_expression": "I want milk.", "scaffold_level": 2},
                     "assessment": {"target_reached": True, "assessment_confidence": 1},
                     "learning_loop": {"assessed_target": "I want milk.", "failed_attempts": 0}},
    })


def test_replay_conflict_and_revision(svc):
    first = commit(svc)
    assert commit(svc) == first
    with pytest.raises(ValueError, match="stale_turn"):
        commit(svc, "t2")
    assert svc.learning.read("synthetic", "lesson")["revision"] == 1


def test_only_completed_action_produces_evidence(svc):
    commit(svc)
    commit(svc, "t2", "t1", 1)
    assert svc.learning.profile("synthetic")["targets"] == []
    claim = svc.learning.claim("synthetic", "lesson", "t2", "device-session")
    assert claim["claimed"] is True
    assert svc.learning.claim("synthetic", "lesson", "t2", "device-session")["claimed"] is False
    svc.learning.ack(claim["command_id"], "simulator", "device-session", "completed")
    commit(svc, "t3", "t2", 2)
    assert svc.learning.profile("synthetic")["targets"][0]["status"] == "OBSERVED_ONCE"
    commit(svc, "t3", "t2", 2)
    assert svc.learning.profile("synthetic")["targets"][0]["observations"] == 1


def test_restart_and_existing_erasure_cascade(cfg):
    svc = MemoryService(cfg)
    commit(svc)
    claim = svc.learning.claim("synthetic", "lesson", "t1", "device-session")
    svc.learning.ack(claim["command_id"], "simulator", "device-session", "completed")
    commit(svc, "t2", "t1", 1)
    svc.close()
    svc = MemoryService(cfg)
    try:
        assert svc.learning.read("synthetic", "lesson")["revision"] == 2
        assert svc.learning.profile("synthetic")["targets"][0]["observations"] == 1
        svc.erase("synthetic")
        assert svc.learning.read("synthetic", "lesson")["revision"] == 0
        assert svc.learning.profile("synthetic")["targets"] == []
    finally:
        svc.close()


def test_identity_ack_and_expired_delivery(svc):
    commit(svc)
    with pytest.raises(ValueError, match="session_owner"):
        svc.learning.read("another", "lesson")
    claim = svc.learning.claim("synthetic", "lesson", "t1", "device-session")
    with pytest.raises(ValueError, match="ack_mismatch"):
        svc.learning.ack(claim["command_id"], "other", "device-session", "completed")
    with svc.db.tx() as conn:
        conn.execute("UPDATE learning_turns SET delivery_deadline=0")
    svc.learning.ack(claim["command_id"], "simulator", "device-session", "completed")
    assert svc.learning.read("synthetic", "lesson")["latest"]["delivery"]["status"] == "expired"


def test_pending_delivery_prevents_advancing_and_failed_delivery_is_not_evidence(svc):
    commit(svc)
    claim = svc.learning.claim("synthetic", "lesson", "t1", "device-session")
    with pytest.raises(ValueError, match="delivery_pending"):
        commit(svc, "t2", "t1", 1)
    svc.learning.ack(claim["command_id"], "simulator", "device-session", "failed")
    commit(svc, "t2", "t1", 1)
    assert svc.learning.profile("synthetic")["targets"] == []


def test_concurrent_retries_create_one_turn(svc):
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _: commit(svc), range(16)))
    assert all(r == results[0] for r in results)
    assert svc.db.q1("SELECT COUNT(*) AS n FROM learning_turns")["n"] == 1


def test_due_review_is_derived_without_promoting_mastery(svc):
    commit(svc)
    claim = svc.learning.claim("synthetic", "lesson", "t1", "device-session")
    svc.learning.ack(claim["command_id"], "simulator", "device-session", "completed")
    commit(svc, "t2", "t1", 1)
    with svc.db.tx() as conn:
        conn.execute("UPDATE learning_evidence SET created=0")
    profile = svc.learning.profile("synthetic")
    assert profile["review_targets"] == ["I want milk."]
    assert profile["mastery_promoted"] is False
