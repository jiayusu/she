"""Erase privacy boundary: no recoverable child content survives deletion."""
import json
from pathlib import Path

from conftest import make_svc


def test_erase_forgets_every_cached_session_for_only_the_requested_child(tmp_path):
    svc = make_svc(tmp_path)
    try:
        svc.working_push("a-session-1", "alpha secret", child_id="child-a")
        svc.working_push("a-session-2", "another alpha secret", child_id="child-a")
        svc.working_push("b-session", "beta stays", child_id="child-b")

        svc.erase("child-a")

        assert svc.working.items("a-session-1") == []
        assert svc.working.items("a-session-2") == []
        assert [turn["text"] for turn in svc.working.items("b-session")] == [
            "beta stays"
        ]
    finally:
        svc.close()


def test_erase_purge_all_forgets_every_cached_session(tmp_path):
    svc = make_svc(tmp_path)
    try:
        svc.working_push("a-session", "alpha secret", child_id="child-a")
        svc.working_push("b-session", "beta secret", child_id="child-b")

        svc.erase("any", purge_all=True)

        assert svc.working.items("a-session") == []
        assert svc.working.items("b-session") == []
    finally:
        svc.close()


def test_erase_manifest_contains_only_opaque_deletion_metadata(tmp_path):
    svc = make_svc(tmp_path)
    secret = "PRIVATE CHILD UTTERANCE 8421"
    try:
        svc.write_episode(
            utterance=secret,
            scene="private bedroom",
            child_id="child-a",
            salience=0.9,
            mirror_salience=True,
            push_working=True,
            session_id="private-session",
        )
        svc.whitelist_add(
            "opaque-reference-1",
            "private parent reason",
            content="private whitelist content",
            child_id="child-a",
        )
        with svc.db.tx() as conn:
            conn.execute(
                "INSERT INTO procedural(child_id,name,trigger,action) VALUES(?,?,?,?)",
                ("child-a", "private task", '{"phrase":"secret trigger"}',
                 '{"text":"secret action"}'),
            )

        out = svc.erase("child-a")
        manifest_text = Path(out["manifest"]).read_text(encoding="utf-8")
        rows = [json.loads(line) for line in manifest_text.splitlines()]

        assert secret not in manifest_text
        for private_value in (
            "private bedroom",
            "private parent reason",
            "private whitelist content",
            "private task",
            "secret trigger",
            "secret action",
        ):
            assert private_value not in manifest_text
        forbidden_keys = {
            "utterance", "content", "text", "scene", "name", "reason",
            "trigger", "action", "edges",
        }
        assert rows
        assert all(not (forbidden_keys & row.keys()) for row in rows)
        assert all({"type", "id", "erase_job", "child_id", "requested_by",
                    "deadline_ts", "purpose"} <= row.keys() for row in rows)
    finally:
        svc.close()


def test_write_audit_records_metadata_without_original_child_text(tmp_path):
    svc = make_svc(tmp_path)
    episode_secret = "EPISODE SECRET 6103"
    working_secret = "WORKING SECRET 9207"
    recall_secret = "RECALL SECRET 7724"
    try:
        svc.write_episode(utterance=episode_secret, actor="agent:route")
        svc.working_push("session-a", working_secret, actor="agent:engine")
        svc.recall(recall_secret, actor="agent:ahai")

        entries = svc.audit.query(limit=20)
        audit_text = json.dumps(entries, ensure_ascii=False)
        assert episode_secret not in audit_text
        assert working_secret not in audit_text
        assert recall_secret not in audit_text
        assert {"ep_write", "working_push", "recall"} <= {
            row["action"] for row in entries
        }

        jsonl_text = "\n".join(
            path.read_text(encoding="utf-8")
            for path in svc.cfg.audit_dir().glob("*.jsonl")
        )
        assert episode_secret not in jsonl_text
        assert working_secret not in jsonl_text
        assert recall_secret not in jsonl_text
    finally:
        svc.close()


def test_erase_removes_all_snapshots_that_could_restore_deleted_child(tmp_path):
    svc = make_svc(tmp_path)
    try:
        svc.write_episode(utterance="alpha secret", child_id="child-a")
        svc.write_episode(utterance="beta stays", child_id="child-b")
        snapshot = svc.snapshot(note="contains-child-a")
        snapshot_path = Path(snapshot["path"])
        assert snapshot_path.exists()

        out = svc.erase("child-a")

        assert out["stats"]["snapshots"] == 1
        assert svc.snapshots.list() == []
        assert not snapshot_path.exists()
        assert "error" in svc.rollback(snapshot["version"])
        assert svc.episodic.all_rows(child_id="child-a") == []
        assert [row["utterance"] for row in
                svc.episodic.all_rows(child_id="child-b")] == ["beta stays"]
    finally:
        svc.close()
