"""Transactional learning history. No raw utterances; no automatic mastery promotion.

Rows reference the existing session deletion root. Existing erase/wipe operations
cascade without adding a second deletion implementation.
"""
import json
import re
import time
import uuid

from .db import dump

ID = re.compile(r"^[A-Za-z0-9_-]{1,80}$")
TARGETS = {"I want milk.", "I want water.", "I like apples.", "Open, please."}


def identity(value):
    if not isinstance(value, str) or not ID.fullmatch(value):
        raise ValueError("invalid_identity")
    return value


class LearningStore:
    def __init__(self, db, audit):
        self.db, self.audit = db, audit
        with db.lock:
            db.conn.executescript("""
                CREATE TABLE IF NOT EXISTS learning_turns (
                  session_id TEXT NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
                  turn_id TEXT NOT NULL, child_id TEXT NOT NULL, device_id TEXT NOT NULL,
                  revision INTEGER NOT NULL, request_hash TEXT NOT NULL,
                  response TEXT NOT NULL, created REAL NOT NULL,
                  command_id TEXT UNIQUE, device_session TEXT,
                  delivery_status TEXT NOT NULL DEFAULT 'planned', delivery_deadline REAL,
                  PRIMARY KEY(session_id, turn_id), UNIQUE(session_id, revision)
                );
                CREATE TABLE IF NOT EXISTS learning_evidence (
                  session_id TEXT NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
                  turn_id TEXT NOT NULL, child_id TEXT NOT NULL, target TEXT NOT NULL,
                  scaffold INTEGER NOT NULL, created REAL NOT NULL,
                  PRIMARY KEY(session_id, turn_id)
                );
                CREATE INDEX IF NOT EXISTS ix_learning_child ON learning_evidence(child_id, target);
            """)
            db.conn.commit()

    def _owner(self, child, session):
        identity(child), identity(session)
        row = self.db.q1("SELECT child_id FROM sessions WHERE session_id=?", (session,))
        if row and row["child_id"] != child:
            raise ValueError("session_owner")

    def _view(self, row):
        if not row:
            return None
        status = row["delivery_status"]
        if status == "issuing" and time.time() >= row["delivery_deadline"]:
            status = "expired"
        return {"turn_id": row["turn_id"], "device_id": row["device_id"],
                "request_hash": row["request_hash"], "response": json.loads(row["response"]),
                "created": row["created"], "revision": row["revision"],
                "delivery": {"status": status, "command_id": row["command_id"],
                             "device_session": row["device_session"]}}

    def read(self, child, session, turn=None):
        with self.db.lock:
            self._owner(child, session)
            latest = self.db.q1("SELECT * FROM learning_turns WHERE session_id=? ORDER BY revision DESC LIMIT 1", (session,))
            replay = self.db.q1("SELECT * FROM learning_turns WHERE session_id=? AND turn_id=?", (session, turn)) if turn else None
            return {"revision": latest["revision"] if latest else 0,
                    "latest": self._view(latest), "replay": self._view(replay),
                    "profile": self.profile(child)}

    def commit(self, b):
        child, session, turn, device = (identity(b[k]) for k in ("child_id", "session_id", "turn_id", "device_id"))
        fingerprint = b.get("request_hash", "")
        if not isinstance(fingerprint, str) or len(fingerprint) != 64:
            raise ValueError("invalid_request_hash")
        response = b.get("response", {})
        action = response.get("teaching_action", {})
        if action.get("target_expression") not in TARGETS or type(action.get("scaffold_level")) is not int or not 0 <= action["scaffold_level"] <= 6:
            raise ValueError("invalid_teaching_action")
        if len(dump(response)) > 24000 or "utterance" in response:
            raise ValueError("invalid_response")
        with self.db.tx() as conn:
            state = self.read(child, session, turn)
            if state["replay"]:
                if state["replay"]["request_hash"] != fingerprint:
                    raise ValueError("idempotency_conflict")
                return state["replay"]["response"]
            latest = state["latest"]
            if b.get("revision") != state["revision"] or b.get("previous_turn_id") != (latest["turn_id"] if latest else None):
                raise ValueError("stale_turn")
            if latest and latest["device_id"] != device:
                raise ValueError("device_mismatch")
            if latest and latest["delivery"]["status"] == "issuing":
                raise ValueError("delivery_pending")
            conn.execute("INSERT OR IGNORE INTO sessions(session_id,child_id) VALUES(?,?)", (session, child))
            assessment = response.get("assessment", {})
            assessed_target = response.get("learning_loop", {}).get("assessed_target")
            prior = latest["response"]["teaching_action"] if latest else {}
            evidence = bool(latest and latest["delivery"]["status"] == "completed"
                            and time.time() - latest["created"] < 900
                            and assessment.get("target_reached") is True
                            and isinstance(assessment.get("assessment_confidence"), (float, int))
                            and 0.8 <= assessment["assessment_confidence"] <= 1
                            and assessed_target == prior.get("target_expression"))
            if evidence:
                conn.execute("INSERT INTO learning_evidence VALUES(?,?,?,?,?,?)",
                             (session, turn, child, assessed_target, prior["scaffold_level"], time.time()))
            response = {**response, "turn_id": turn, "previous_turn_id": b.get("previous_turn_id"),
                        "persistence": {"status": "committed", "evidence_written": evidence},
                        "learning_memory": self.profile(child)}
            conn.execute("INSERT INTO learning_turns(session_id,turn_id,child_id,device_id,revision,request_hash,response,created) VALUES(?,?,?,?,?,?,?,?)",
                         (session, turn, child, device, state["revision"] + 1, fingerprint, dump(response), time.time()))
        self.audit.log("agent:director", "learning_commit", turn, f"revision={state['revision'] + 1} evidence={int(evidence)}")
        return response

    def claim(self, child, session, turn, device_session):
        identity(device_session)
        with self.db.tx() as conn:
            state = self.read(child, session, turn)
            row = state["replay"]
            if not row or state["latest"]["turn_id"] != turn:
                raise ValueError("stale_turn")
            if time.time() - row["created"] >= 900:
                raise ValueError("turn_expired")
            if row["delivery"]["status"] != "planned":
                return {"claimed": False, **row["delivery"]}
            command_id = str(uuid.uuid4())
            conn.execute("UPDATE learning_turns SET command_id=?,device_session=?,delivery_status='issuing',delivery_deadline=? WHERE session_id=? AND turn_id=?",
                         (command_id, device_session, time.time() + 5, session, turn))
        return {"claimed": True, "command_id": command_id, "status": "issuing"}

    def ack(self, command_id, device, device_session, status):
        if status not in ("completed", "failed"):
            raise ValueError("invalid_ack")
        with self.db.tx() as conn:
            row = conn.execute("SELECT * FROM learning_turns WHERE command_id=?", (command_id,)).fetchone()
            if not row or row["device_id"] != device or row["device_session"] != device_session:
                raise ValueError("ack_mismatch")
            if row["delivery_status"] == "issuing":
                status = status if time.time() < row["delivery_deadline"] else "expired"
                conn.execute("UPDATE learning_turns SET delivery_status=? WHERE command_id=?", (status, command_id))
            elif row["delivery_status"] != status:
                raise ValueError("ack_conflict")
        self.audit.log("service:gateway", "learning_delivery", command_id, status)
        return {"status": status}

    def profile(self, child):
        identity(child)
        rows = self.db.q("SELECT target, COUNT(*) AS n, MAX(created) AS latest, MIN(scaffold) AS support FROM learning_evidence WHERE child_id=? GROUP BY target", (child,))
        targets = [{"target": r["target"], "observations": r["n"],
                    "status": "REPEATED" if r["n"] > 1 else "OBSERVED_ONCE",
                    "best_scaffold": r["support"],
                    "review_due_at": r["latest"] + (1 if r["n"] == 1 else 3 if r["n"] == 2 else 7) * 86400}
                   for r in rows]
        return {"targets": targets, "review_targets": [r["target"] for r in targets if r["review_due_at"] <= time.time()],
                "mastery_promoted": False}
