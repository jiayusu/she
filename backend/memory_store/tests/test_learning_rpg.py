from copy import deepcopy

import pytest

from memstore.service import MemoryService


def speech_evidence(turn, *, evidence_id, criterion_id="none.v1", act="none",
                    slots=None, satisfied=False,
                    eliciting_action_id="no_action", scaffold_level=2):
    return {
        "evidence_id": evidence_id,
        "source_turn_id": turn,
        "eliciting_action_id": eliciting_action_id,
        "criterion_id": criterion_id,
        "act": act,
        "slots": slots or {},
        "confidence": 0.95 if satisfied else 0,
        "context_supported": satisfied,
        "scaffold_level_used": scaffold_level,
        "quest_satisfied": satisfied,
        "error_type": None if satisfied else "no_completed_prompt",
    }


def initial_rpg(turn="t1"):
    return {
        "contract_version": "1.0",
        "seed_id": "milk_picnic",
        "seed_version": 1,
        "node_id": "collect_milk",
        "phase": "presenting",
        "world_revision": 1,
        "inventory": [],
        "completed_nodes": [],
        "confirmed_object": "fridge",
        "world_role": "饮品保管员",
        "feedback_id": "collect_milk_s2",
        "next_quest_id": "collect_milk",
        "speech_act_evidence": speech_evidence(
            turn, evidence_id=f"evidence-{turn}"
        ),
        "world_events": [],
    }


def milk_transition(turn="t2"):
    evidence = speech_evidence(
        turn,
        evidence_id=f"evidence-{turn}",
        criterion_id="request_milk.v1",
        act="request_item",
        slots={"item": "milk"},
        satisfied=True,
        eliciting_action_id="action-t1",
    )
    return {
        "contract_version": "1.0",
        "seed_id": "milk_picnic",
        "seed_version": 1,
        "node_id": "find_red_cup",
        "phase": "seeking_object",
        "world_revision": 2,
        "inventory": ["milk_token"],
        "completed_nodes": ["collect_milk"],
        "confirmed_object": None,
        "world_role": "杯子管理员",
        "feedback_id": "milk_ready",
        "next_quest_id": "find_red_cup",
        "speech_act_evidence": evidence,
        "world_events": [{
            "event_id": "event-milk",
            "kind": "virtual_item_granted",
            "base_revision": 1,
            "resulting_revision": 2,
            "source_evidence_id": evidence["evidence_id"],
            "from_node_id": "collect_milk",
            "to_node_id": "find_red_cup",
            "item_id": "milk_token",
        }],
    }


def cup_prompt(turn="t3"):
    return {
        "contract_version": "1.0",
        "seed_id": "milk_picnic",
        "seed_version": 1,
        "node_id": "find_red_cup",
        "phase": "presenting",
        "world_revision": 2,
        "inventory": ["milk_token"],
        "completed_nodes": ["collect_milk"],
        "confirmed_object": "table",
        "world_role": "杯子管理员",
        "feedback_id": "find_red_cup_s1",
        "next_quest_id": "find_red_cup",
        "speech_act_evidence": speech_evidence(
            turn,
            evidence_id=f"evidence-{turn}",
            eliciting_action_id="action-t2",
        ),
        "world_events": [],
    }


def picnic_transition(turn="t4"):
    evidence = speech_evidence(
        turn,
        evidence_id=f"evidence-{turn}",
        criterion_id="select_red_cup.v1",
        act="select_item",
        slots={"item": "cup", "color": "red"},
        satisfied=True,
        eliciting_action_id="action-t3",
        scaffold_level=1,
    )
    return {
        "contract_version": "1.0",
        "seed_id": "milk_picnic",
        "seed_version": 1,
        "node_id": "picnic_ready",
        "phase": "completed",
        "world_revision": 4,
        "inventory": ["milk_token", "red_cup_token"],
        "completed_nodes": ["collect_milk", "find_red_cup", "picnic_ready"],
        "confirmed_object": None,
        "world_role": "野餐向导",
        "feedback_id": "red_cup_ready",
        "next_quest_id": None,
        "speech_act_evidence": evidence,
        "world_events": [
            {
                "event_id": "event-red-cup",
                "kind": "virtual_item_granted",
                "from_node_id": "find_red_cup",
                "to_node_id": "picnic_ready",
                "item_id": "red_cup_token",
                "base_revision": 2,
                "resulting_revision": 3,
                "source_evidence_id": evidence["evidence_id"],
            },
            {
                "event_id": "event-picnic-complete",
                "kind": "quest_completed",
                "from_node_id": "picnic_ready",
                "to_node_id": "picnic_ready",
                "quest_id": "milk_picnic",
                "base_revision": 3,
                "resulting_revision": 4,
                "source_evidence_id": evidence["evidence_id"],
            },
        ],
    }


def commit(svc, turn, rpg, *, previous=None, revision=0, include_rpg=True,
           action_patch=None):
    targets = {
        "collect_milk": "I want milk.",
        "find_red_cup": "I choose the red cup.",
        "picnic_ready": "Our picnic is ready.",
    }
    prompt_prefix = f"{rpg['node_id']}_s"
    is_prompt = (
        rpg["feedback_id"].startswith(prompt_prefix)
        and rpg["feedback_id"][-1:] in "0123456"
    )
    prompt_id = rpg["feedback_id"] if is_prompt else None
    scaffold_level = int(prompt_id[-1]) if prompt_id else 2
    if is_prompt:
        action_kind = "ask"
    elif rpg["feedback_id"] in {"milk_ready", "red_cup_ready"}:
        action_kind = "advance_story"
    else:
        action_kind = "explore"
    action = {
        "action_id": f"action-{turn}",
        "target_expression": targets[rpg["node_id"]],
        "scaffold_level": scaffold_level,
        "teaching_action": action_kind,
        "feedback_id": rpg["feedback_id"],
        "node_id": rpg["node_id"],
        "phase": rpg["phase"],
        "world_role": rpg["world_role"],
        "story_action": f"rpg:{rpg['feedback_id']}",
    }
    if is_prompt:
        action["prompt_id"] = prompt_id
    if action_patch:
        action.update(action_patch)
    response = {
        "teaching_action": action,
        "assessment": {},
        "learning_loop": {},
    }
    if include_rpg:
        response["rpg"] = rpg
    return svc.learning.commit({
        "child_id": "synthetic",
        "session_id": "rpg-lesson",
        "turn_id": turn,
        "device_id": "simulator",
        "previous_turn_id": previous,
        "request_hash": turn.ljust(64, "0"),
        "revision": revision,
        "response": response,
    })


def complete_delivery(svc, turn):
    claim = svc.learning.claim(
        "synthetic", "rpg-lesson", turn, "device-session"
    )
    assert claim["claimed"] is True
    result = svc.learning.ack(
        claim["command_id"], "simulator", "device-session", "completed"
    )
    assert result["status"] == "completed"


def advance_to_cup_prompt(svc):
    commit(svc, "t1", initial_rpg("t1"))
    complete_delivery(svc, "t1")
    commit(svc, "t2", milk_transition("t2"), previous="t1", revision=1)
    complete_delivery(svc, "t2")
    commit(svc, "t3", cup_prompt("t3"), previous="t2", revision=2)
    complete_delivery(svc, "t3")


def test_rpg_state_is_persisted_and_restored_from_latest_response(svc):
    commit(svc, "t1", initial_rpg("t1"))
    complete_delivery(svc, "t1")
    second = commit(
        svc, "t2", milk_transition("t2"), previous="t1", revision=1
    )

    state = svc.learning.read("synthetic", "rpg-lesson")
    assert state["latest"]["response"]["rpg"] == second["rpg"]
    assert state["latest"]["response"]["rpg"]["node_id"] == "find_red_cup"


def test_rpg_transition_restores_authoritative_state_after_restart(cfg):
    svc = MemoryService(cfg)
    commit(svc, "t1", initial_rpg("t1"))
    complete_delivery(svc, "t1")
    svc.close()

    svc = MemoryService(cfg)
    try:
        second = commit(
            svc, "t2", milk_transition("t2"), previous="t1", revision=1
        )
        assert second["rpg"]["node_id"] == "find_red_cup"
        assert second["rpg"]["inventory"] == ["milk_token"]
    finally:
        svc.close()


def test_first_rpg_decision_cannot_skip_the_seed_start(svc):
    with pytest.raises(ValueError, match="invalid_rpg"):
        commit(svc, "t1", milk_transition("t1"))


def test_rpg_state_cannot_be_omitted_after_the_story_starts(svc):
    commit(svc, "t1", initial_rpg("t1"))

    with pytest.raises(ValueError, match="invalid_rpg:missing_state"):
        commit(
            svc,
            "t2",
            initial_rpg("t2"),
            previous="t1",
            revision=1,
            include_rpg=False,
        )


def test_rpg_transition_requires_completed_previous_delivery(svc):
    commit(svc, "t1", initial_rpg("t1"))

    with pytest.raises(ValueError, match="invalid_rpg:transition_delivery"):
        commit(
            svc, "t2", milk_transition("t2"), previous="t1", revision=1
        )


def test_rpg_transition_rejects_failed_previous_delivery(svc):
    commit(svc, "t1", initial_rpg("t1"))
    claim = svc.learning.claim(
        "synthetic", "rpg-lesson", "t1", "device-session"
    )
    svc.learning.ack(
        claim["command_id"], "simulator", "device-session", "failed"
    )

    with pytest.raises(ValueError, match="invalid_rpg:transition_delivery"):
        commit(
            svc, "t2", milk_transition("t2"), previous="t1", revision=1
        )


def test_rpg_transition_requires_confirmed_object_prompt_context(svc):
    seeking = initial_rpg("t1")
    seeking["phase"] = "seeking_object"
    seeking["confirmed_object"] = None
    seeking["feedback_id"] = "milk_help"
    commit(svc, "t1", seeking)
    complete_delivery(svc, "t1")

    with pytest.raises(
            ValueError, match="invalid_rpg:transition_object_context"):
        commit(
            svc, "t2", milk_transition("t2"), previous="t1", revision=1
        )


def test_rpg_state_rejects_mismatched_action_references(svc):
    with pytest.raises(ValueError, match="invalid_rpg:action_prompt"):
        commit(
            svc,
            "t1",
            initial_rpg("t1"),
            action_patch={"prompt_id": "find_red_cup_s2"},
        )


@pytest.mark.parametrize("mutation", [
    lambda rpg: rpg.update(node_id="picnic_ready"),
    lambda rpg: rpg.update(world_revision=3),
    lambda rpg: rpg.update(inventory=["milk_token", "red_cup_token"]),
    lambda rpg: rpg.update(completed_nodes=["collect_milk", "picnic_ready"]),
    lambda rpg: rpg.update(confirmed_object="table"),
    lambda rpg: rpg.update(phase="presenting"),
    lambda rpg: rpg["speech_act_evidence"].update(quest_satisfied=False),
    lambda rpg: rpg["speech_act_evidence"].update(context_supported=False),
    lambda rpg: rpg["speech_act_evidence"].update(eliciting_action_id="forged"),
    lambda rpg: rpg["speech_act_evidence"].update(scaffold_level_used=4),
    lambda rpg: rpg["speech_act_evidence"].update(confidence=0.7),
    lambda rpg: rpg["world_events"][0].update(base_revision=0),
    lambda rpg: rpg["world_events"][0].update(resulting_revision=4),
    lambda rpg: rpg["world_events"][0].update(source_evidence_id="forged"),
])
def test_rpg_transition_rejects_jump_forgery_and_unlinked_evidence(svc, mutation):
    commit(svc, "t1", initial_rpg("t1"))
    complete_delivery(svc, "t1")
    candidate = milk_transition("t2")
    mutation(candidate)

    with pytest.raises(ValueError, match="invalid_rpg"):
        commit(svc, "t2", candidate, previous="t1", revision=1)


def test_rpg_final_transition_is_atomic_and_same_turn_replay_is_idempotent(svc):
    advance_to_cup_prompt(svc)
    final_rpg = picnic_transition("t4")

    first = commit(svc, "t4", final_rpg, previous="t3", revision=3)
    replay = commit(
        svc, "t4", deepcopy(final_rpg), previous="t3", revision=3
    )

    assert replay == first
    assert first["rpg"]["world_revision"] == 4
    assert len(first["rpg"]["world_events"]) == 2
    assert svc.db.q1(
        "SELECT COUNT(*) AS n FROM learning_turns WHERE session_id=?",
        ("rpg-lesson",),
    )["n"] == 4


def test_rpg_final_transition_requires_token_and_completion_events(svc):
    advance_to_cup_prompt(svc)
    incomplete = picnic_transition("t4")
    incomplete["world_events"].pop()

    with pytest.raises(ValueError, match="invalid_rpg"):
        commit(svc, "t4", incomplete, previous="t3", revision=3)


def test_rpg_final_transition_requires_completed_phase(svc):
    advance_to_cup_prompt(svc)
    incomplete = picnic_transition("t4")
    incomplete["phase"] = "paused"

    with pytest.raises(ValueError, match="invalid_rpg"):
        commit(svc, "t4", incomplete, previous="t3", revision=3)


def test_erase_session_cascade_removes_persisted_rpg_state(svc):
    commit(svc, "t1", initial_rpg("t1"))

    svc.erase("synthetic")

    state = svc.learning.read("synthetic", "rpg-lesson")
    assert state["revision"] == 0
    assert state["latest"] is None
    assert svc.db.q1("SELECT COUNT(*) AS n FROM learning_turns")["n"] == 0
