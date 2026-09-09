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
RPG_ID = re.compile(r"^[A-Za-z0-9_.-]{1,120}$")
TARGETS = {
    "I want milk.", "I want water.", "I like apples.", "Open, please.",
    "I choose the red cup.", "Our picnic is ready.",
}

RPG_FIELDS = {
    "contract_version", "seed_id", "seed_version", "node_id", "phase",
    "world_revision", "inventory", "completed_nodes", "world_role",
    "confirmed_object", "feedback_id", "next_quest_id",
    "speech_act_evidence", "world_events",
}
RPG_EVIDENCE_FIELDS = {
    "evidence_id", "source_turn_id", "eliciting_action_id", "criterion_id",
    "act", "slots", "confidence", "context_supported",
    "scaffold_level_used", "quest_satisfied", "error_type",
}
RPG_PHASES = {
    "seeking_object", "confirming_object", "presenting", "awaiting_speech",
    "resolving", "paused", "delivery_failed", "completed",
}
RPG_OBJECTS = {
    "collect_milk": {"fridge"},
    "find_red_cup": {"table", "red_cup", "blue_cup"},
    "picnic_ready": set(),
}
RPG_PRESENTATION = {
    "collect_milk": {
        "world_role": "饮品保管员",
        "feedback_ids": (
            {f"collect_milk_s{level}" for level in range(7)} | {"milk_help"}
        ),
        "target_expression": "I want milk.",
    },
    "find_red_cup": {
        "world_role": "杯子管理员",
        "feedback_ids": (
            {f"find_red_cup_s{level}" for level in range(7)}
            | {"milk_ready", "red_cup_help"}
        ),
        "target_expression": "I choose the red cup.",
    },
    "picnic_ready": {
        "world_role": "野餐向导",
        "feedback_ids": (
            {f"picnic_ready_s{level}" for level in range(7)}
            | {"red_cup_ready", "picnic_complete", "picnic_pause"}
        ),
        "target_expression": "Our picnic is ready.",
    },
}
RPG_PROMPT_PREFIX = {
    "collect_milk": "collect_milk",
    "find_red_cup": "find_red_cup",
}
# Server-authoritative projection of the reviewed milk_picnic.v1 graph. It is
# deliberately finite; a new seed/version must add an explicit reviewed mapping.
RPG_STATES = {
    "collect_milk": {
        "revision": 1,
        "inventory": [],
        "completed_nodes": [],
        "next_quest_id": "collect_milk",
    },
    "find_red_cup": {
        "revision": 2,
        "inventory": ["milk_token"],
        "completed_nodes": ["collect_milk"],
        "next_quest_id": "find_red_cup",
    },
    "picnic_ready": {
        "revision": 4,
        "inventory": ["milk_token", "red_cup_token"],
        "completed_nodes": ["collect_milk", "find_red_cup", "picnic_ready"],
        "next_quest_id": None,
    },
}
RPG_TRANSITIONS = {
    ("collect_milk", "find_red_cup"): {
        "phase": "seeking_object",
        "criterion_id": "request_milk.v1",
        "act": "request_item",
        "slots": {"item": "milk"},
        "events": [
            {
                "kind": "virtual_item_granted",
                "from_node_id": "collect_milk",
                "to_node_id": "find_red_cup",
                "item_id": "milk_token",
            },
        ],
    },
    ("find_red_cup", "picnic_ready"): {
        "phase": "completed",
        "criterion_id": "select_red_cup.v1",
        "act": "select_item",
        "slots": {"item": "cup", "color": "red"},
        "events": [
            {
                "kind": "virtual_item_granted",
                "from_node_id": "find_red_cup",
                "to_node_id": "picnic_ready",
                "item_id": "red_cup_token",
            },
            {
                "kind": "quest_completed",
                "from_node_id": "picnic_ready",
                "to_node_id": "picnic_ready",
                "quest_id": "milk_picnic",
            },
        ],
    },
}


def identity(value):
    if not isinstance(value, str) or not ID.fullmatch(value):
        raise ValueError("invalid_identity")
    return value


def _invalid_rpg(reason):
    raise ValueError(f"invalid_rpg:{reason}")


def _rpg_id(value):
    return isinstance(value, str) and RPG_ID.fullmatch(value) is not None


def _validate_rpg_evidence(value, turn=None):
    if not isinstance(value, dict) or set(value) != RPG_EVIDENCE_FIELDS:
        _invalid_rpg("evidence_shape")
    for key in ("evidence_id", "source_turn_id", "eliciting_action_id",
                "criterion_id"):
        if not _rpg_id(value[key]):
            _invalid_rpg("evidence_id")
    if turn is not None and value["source_turn_id"] != turn:
        _invalid_rpg("evidence_turn")
    if value["act"] not in ("request_item", "select_item", "none"):
        _invalid_rpg("evidence_act")
    if not isinstance(value["slots"], dict):
        _invalid_rpg("evidence_slots")
    allowed_slots = {"item": {"milk", "water", "cup"},
                     "color": {"red", "blue"}}
    if (set(value["slots"]) - set(allowed_slots)
            or any(not isinstance(slot_value, str)
                   or slot_value not in allowed_slots[slot]
                   for slot, slot_value in value["slots"].items())):
        _invalid_rpg("evidence_slots")
    if value["act"] == "request_item" and set(value["slots"]) != {"item"}:
        _invalid_rpg("request_slots")
    if value["act"] == "select_item" and set(value["slots"]) != {"item", "color"}:
        _invalid_rpg("select_slots")
    if value["act"] == "none" and value["slots"]:
        _invalid_rpg("none_slots")
    confidence = value["confidence"]
    if (isinstance(confidence, bool)
            or not isinstance(confidence, (int, float))
            or not 0 <= confidence <= 1):
        _invalid_rpg("evidence_confidence")
    if type(value["context_supported"]) is not bool:
        _invalid_rpg("evidence_context")
    if (type(value["scaffold_level_used"]) is not int
            or not 0 <= value["scaffold_level_used"] <= 6):
        _invalid_rpg("evidence_scaffold")
    if type(value["quest_satisfied"]) is not bool:
        _invalid_rpg("quest_satisfied")
    if value["act"] == "none" and value["quest_satisfied"]:
        _invalid_rpg("none_satisfied")
    if value["error_type"] not in (
            None, "low_confidence", "wrong_slot", "unmatched",
            "no_completed_prompt"):
        _invalid_rpg("evidence_error")
    return value


def _validate_rpg_state(value, turn=None):
    if not isinstance(value, dict) or set(value) != RPG_FIELDS:
        _invalid_rpg("state_shape")
    if value["contract_version"] != "1.0":
        _invalid_rpg("contract_version")
    if value["seed_id"] != "milk_picnic" or type(value["seed_version"]) is not int \
            or value["seed_version"] != 1:
        _invalid_rpg("story_seed")
    if not _rpg_id(value["node_id"]):
        _invalid_rpg("node")
    expected = RPG_STATES.get(value["node_id"])
    if expected is None:
        _invalid_rpg("node")
    if not isinstance(value["phase"], str) or value["phase"] not in RPG_PHASES:
        _invalid_rpg("phase")
    if ((value["node_id"] == "picnic_ready")
            != (value["phase"] == "completed")):
        _invalid_rpg("completed_phase")
    if (type(value["world_revision"]) is not int
            or value["world_revision"] != expected["revision"]):
        _invalid_rpg("world_revision")
    for field in ("inventory", "completed_nodes", "next_quest_id"):
        if value[field] != expected[field]:
            _invalid_rpg(field)
    confirmed_object = value["confirmed_object"]
    if (confirmed_object is not None
            and confirmed_object not in RPG_OBJECTS[value["node_id"]]):
        _invalid_rpg("confirmed_object")
    if (value["phase"] in (
            "presenting", "awaiting_speech", "resolving", "delivery_failed")
            and confirmed_object is None):
        _invalid_rpg("missing_confirmed_object")
    if (value["phase"] in (
            "seeking_object", "confirming_object", "completed")
            and confirmed_object is not None):
        _invalid_rpg("unexpected_confirmed_object")
    presentation = RPG_PRESENTATION[value["node_id"]]
    if (value["world_role"] != presentation["world_role"]
            or value["feedback_id"] not in presentation["feedback_ids"]):
        _invalid_rpg("presentation_id")
    if value["next_quest_id"] is not None and not _rpg_id(value["next_quest_id"]):
        _invalid_rpg("next_quest")
    evidence = _validate_rpg_evidence(value["speech_act_evidence"], turn)
    if not isinstance(value["world_events"], list) or len(value["world_events"]) > 2:
        _invalid_rpg("world_events")
    return value["node_id"], value["world_revision"], evidence


def _validate_rpg_action(action, value):
    if not isinstance(action, dict) or not _rpg_id(action.get("action_id")):
        _invalid_rpg("action_shape")
    node = value["node_id"]
    presentation = RPG_PRESENTATION[node]
    if (action.get("node_id") != node
            or action.get("phase") != value["phase"]
            or action.get("world_role") != value["world_role"]
            or action.get("feedback_id") != value["feedback_id"]
            or action.get("story_action") != f"rpg:{value['feedback_id']}"
            or action.get("target_expression")
            != presentation["target_expression"]):
        _invalid_rpg("action_reference")
    prompt_prefix = f"{node}_s"
    feedback_id = value["feedback_id"]
    is_prompt = (feedback_id.startswith(prompt_prefix)
                 and feedback_id[-1:] in "0123456")
    if is_prompt:
        if (action.get("prompt_id") != feedback_id
                or action.get("teaching_action")
                not in ("ask", "prompt", "reinvite")
                or action.get("scaffold_level") != int(feedback_id[-1])):
            _invalid_rpg("action_prompt")
    else:
        if action.get("prompt_id") is not None:
            _invalid_rpg("action_prompt")
        action_kind = action.get("teaching_action")
        if feedback_id in ("milk_ready", "red_cup_ready"):
            if action_kind != "advance_story":
                _invalid_rpg("action_feedback")
        elif action_kind not in ("explore", "pause"):
            _invalid_rpg("action_feedback")


def _validate_rpg_event(value, expected, base_revision, resulting_revision,
                        evidence_id):
    if not isinstance(value, dict):
        _invalid_rpg("event_shape")
    payload_key = "item_id" if expected["kind"] == "virtual_item_granted" else "quest_id"
    fields = {
        "event_id", "kind", "base_revision", "resulting_revision",
        "source_evidence_id", "from_node_id", "to_node_id", payload_key,
    }
    if set(value) != fields or not _rpg_id(value["event_id"]):
        _invalid_rpg("event_shape")
    for field in ("kind", "from_node_id", "to_node_id", payload_key):
        if value[field] != expected[field]:
            _invalid_rpg("event_payload")
    if (type(value["base_revision"]) is not int
            or type(value["resulting_revision"]) is not int
            or value["base_revision"] != base_revision
            or value["resulting_revision"] != resulting_revision):
        _invalid_rpg("event_revision")
    if value["source_evidence_id"] != evidence_id:
        _invalid_rpg("event_evidence")


def validate_rpg_transition(value, previous, turn, previous_action=None,
                            previous_delivery=None):
    node, revision, evidence = _validate_rpg_state(value, turn)
    events = value["world_events"]
    if previous is None:
        if (node != "collect_milk" or revision != 1 or events
                or evidence["quest_satisfied"]
                or evidence["eliciting_action_id"] != "no_action"):
            _invalid_rpg("initial_state")
        return

    previous_node, previous_revision, _ = _validate_rpg_state(previous)
    if (not isinstance(previous_action, dict)
            or not _rpg_id(previous_action.get("action_id"))
            or evidence["eliciting_action_id"] != previous_action["action_id"]
            or evidence["scaffold_level_used"]
            != previous_action.get("scaffold_level")):
        _invalid_rpg("eliciting_action")
    if node == previous_node:
        if revision != previous_revision or events or evidence["quest_satisfied"]:
            _invalid_rpg("non_transition")
        return

    transition = RPG_TRANSITIONS.get((previous_node, node))
    if transition is None:
        _invalid_rpg("transition")
    if (not isinstance(previous_delivery, dict)
            or previous_delivery.get("status") != "completed"):
        _invalid_rpg("transition_delivery")
    if (previous["phase"] not in ("presenting", "awaiting_speech")
            or previous["confirmed_object"] is None):
        _invalid_rpg("transition_object_context")
    expected_prompt = (
        f"{RPG_PROMPT_PREFIX[previous_node]}_s"
        f"{previous_action.get('scaffold_level')}"
    )
    if (previous_action.get("teaching_action")
            not in ("ask", "prompt", "reinvite")
            or previous_action.get("prompt_id") != expected_prompt
            or previous_action.get("feedback_id") != expected_prompt
            or previous.get("feedback_id") != expected_prompt):
        _invalid_rpg("transition_prompt")
    if revision != previous_revision + len(transition["events"]):
        _invalid_rpg("transition_revision")
    if (evidence["quest_satisfied"] is not True
            or value["phase"] != transition["phase"]
            or evidence["criterion_id"] != transition["criterion_id"]
            or evidence["act"] != transition["act"]
            or evidence["slots"] != transition["slots"]
            or evidence["context_supported"] is not True
            or evidence["confidence"] < 0.8
            or evidence["error_type"] is not None):
        _invalid_rpg("transition_evidence")
    if len(events) != len(transition["events"]):
        _invalid_rpg("transition_events")
    for offset, (event, expected) in enumerate(
            zip(events, transition["events"])):
        _validate_rpg_event(
            event,
            expected,
            previous_revision + offset,
            previous_revision + offset + 1,
            evidence["evidence_id"],
        )


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
        if not isinstance(response, dict):
            raise ValueError("invalid_response")
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
            latest_response = latest["response"] if latest else {}
            latest_has_rpg = "rpg" in latest_response
            if "rpg" in response:
                validate_rpg_transition(
                    response["rpg"],
                    latest_response["rpg"] if latest_has_rpg else None,
                    turn,
                    latest_response.get("teaching_action")
                    if latest_has_rpg else None,
                    latest.get("delivery") if latest_has_rpg else None,
                )
                _validate_rpg_action(action, response["rpg"])
            elif latest_has_rpg:
                _invalid_rpg("missing_state")
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
