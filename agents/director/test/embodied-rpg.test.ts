import { test } from 'node:test';
import assert from 'node:assert/strict';
import { LearningDirector, type SessionTurn } from '../src/learning-director.ts';
import type { DirectRequest, DirectResponse } from '../src/types.ts';

function objectTurn(
  turnId: string,
  previousTurnId: string | null,
  detectedObject: 'fridge' | 'table' | 'red_cup' | 'blue_cup',
): DirectRequest {
  return {
    contract_version: '1.0',
    session_id: 'rpg-session',
    turn_id: turnId,
    previous_turn_id: previousTurnId,
    device_id: 'simulator',
    input_kind: 'object_observed',
    utterance: '',
    asr: null,
    emotion: null,
    detected_object: detectedObject,
    perception_event_id: `perception-${turnId}`,
  };
}

function speechTurn(
  turnId: string,
  previousTurnId: string,
  utterance: string,
  asr = 0.98,
): DirectRequest {
  return {
    contract_version: '1.0',
    session_id: 'rpg-session',
    turn_id: turnId,
    previous_turn_id: previousTurnId,
    device_id: 'simulator',
    input_kind: 'speech',
    utterance,
    asr,
    emotion: null,
    detected_object: null,
    perception_event_id: `speech-${turnId}`,
  };
}

function prior(response: DirectResponse, touched = Date.now()): SessionTurn {
  assert.ok(response.rpg);
  return {
    action: response.teaching_action,
    failures: response.learning_loop.failed_attempts,
    touched,
    rpg: response.rpg,
  };
}

test('reviewed speech acts advance the finite milk picnic world atomically', () => {
  const director = new LearningDirector();
  const fridge = director.plan(objectTurn('t1', null, 'fridge'), undefined, false);
  assert.equal(fridge.rpg?.phase, 'presenting');
  assert.equal(fridge.rpg?.confirmed_object, 'fridge');
  assert.equal(fridge.teaching_action.prompt_id, 'collect_milk_s2');

  const milk = director.plan(
    speechTurn('t2', 't1', 'I want milk.'),
    prior(fridge),
    true,
  );
  assert.equal(milk.rpg?.node_id, 'find_red_cup');
  assert.equal(milk.rpg?.world_revision, 2);
  assert.deepEqual(milk.rpg?.inventory, ['milk_token']);
  assert.equal(milk.rpg?.confirmed_object, null);
  assert.equal(milk.rpg?.world_events[0]?.kind, 'virtual_item_granted');

  const cup = director.plan(
    objectTurn('t3', 't2', 'table'),
    prior(milk),
    true,
  );
  assert.equal(cup.rpg?.phase, 'presenting');
  assert.equal(cup.rpg?.confirmed_object, 'table');
  assert.equal(cup.scaffold_level, 1);
  assert.equal(cup.teaching_action.prompt_id, 'find_red_cup_s1');

  const complete = director.plan(
    speechTurn('t4', 't3', 'I choose the red cup.'),
    prior(cup),
    true,
  );
  assert.equal(complete.rpg?.phase, 'completed');
  assert.equal(complete.rpg?.world_revision, 4);
  assert.deepEqual(complete.rpg?.inventory, ['milk_token', 'red_cup_token']);
  assert.equal(complete.rpg?.world_events.length, 2);
});

test('a short prompted form changes quest state but is not promoted as full-expression evidence', () => {
  const director = new LearningDirector();
  const fridge = director.plan(objectTurn('t1', null, 'fridge'), undefined, false);
  const milk = director.plan(speechTurn('t2', 't1', 'milk'), prior(fridge), true);

  assert.equal(milk.rpg?.speech_act_evidence.quest_satisfied, true);
  assert.equal(milk.rpg?.node_id, 'find_red_cup');
  assert.equal(milk.assessment.target_reached, false);
  assert.equal(milk.teaching_action.memory_policy, 'no_write');
});

test('completed quest steps keep support withdrawn across an exploration detour', () => {
  const director = new LearningDirector();
  const fridge = director.plan(objectTurn('t1', null, 'fridge'), undefined, false);
  const milk = director.plan(
    speechTurn('t2', 't1', 'I want milk.'),
    prior(fridge),
    true,
  );
  const detour = director.plan(
    objectTurn('t3', 't2', 'fridge'),
    prior(milk),
    true,
  );
  assert.equal(detour.rpg?.phase, 'confirming_object');

  const table = director.plan(
    objectTurn('t4', 't3', 'table'),
    prior(detour),
    true,
  );
  assert.equal(table.scaffold_level, 1);
  assert.equal(table.teaching_action.prompt_id, 'find_red_cup_s1');
});

test('speech cannot advance without a delivered prompt and confirmed object context', () => {
  const director = new LearningDirector();
  const fridge = director.plan(objectTurn('t1', null, 'fridge'), undefined, false);
  const undelivered = director.plan(
    speechTurn('t2', 't1', 'I want milk.'),
    prior(fridge),
    false,
  );
  assert.equal(undelivered.rpg?.node_id, 'collect_milk');
  assert.equal(undelivered.rpg?.world_events.length, 0);
  assert.equal(undelivered.rpg?.speech_act_evidence.error_type, 'no_completed_prompt');

  const noObject = director.plan(
    speechTurn('t3', 't2', 'I want milk.'),
    undefined,
    true,
  );
  assert.equal(noObject.rpg?.phase, 'seeking_object');
  assert.equal(noObject.rpg?.world_events.length, 0);
});

test('wrong slots and uncertain ASR never produce world events', () => {
  const director = new LearningDirector();
  const fridge = director.plan(objectTurn('t1', null, 'fridge'), undefined, false);
  const water = director.plan(speechTurn('t2', 't1', 'I want water.'), prior(fridge), true);
  assert.equal(water.rpg?.speech_act_evidence.error_type, 'wrong_slot');
  assert.equal(water.rpg?.world_events.length, 0);

  const uncertain = director.plan(speechTurn('t3', 't1', 'I want milk.', 0.4), prior(fridge), true);
  assert.equal(uncertain.rpg?.speech_act_evidence.error_type, 'low_confidence');
  assert.equal(uncertain.rpg?.world_events.length, 0);
});

test('pause preserves confirmed context and explicit resume replays a reviewed prompt', () => {
  const director = new LearningDirector();
  const fridge = director.plan(objectTurn('t1', null, 'fridge'), undefined, false);
  const paused = director.plan(
    { ...speechTurn('t2', 't1', 'I want milk.'), emotion: -0.9 },
    prior(fridge),
    true,
  );
  assert.equal(paused.rpg?.phase, 'paused');
  assert.equal(paused.rpg?.confirmed_object, 'fridge');
  assert.equal(paused.rpg?.world_events.length, 0);

  const resumed = director.plan({
    ...objectTurn('t3', 't2', 'fridge'),
    input_kind: 'resume',
    detected_object: null,
  }, prior(paused), true);
  assert.equal(resumed.rpg?.phase, 'presenting');
  assert.equal(resumed.rpg?.confirmed_object, 'fridge');
  assert.equal(resumed.teaching_action.teaching_action, 'ask');
});

test('durable RPG state survives the in-memory session TTL', () => {
  let now = 0;
  const director = new LearningDirector({ now: () => now, sessionTtlMs: 10 });
  const fridge = director.plan(objectTurn('t1', null, 'fridge'), undefined, false);
  now = 100;
  const durablePrior = { ...prior(fridge, 0), persistent: true };
  const milk = director.plan(
    speechTurn('t2', 't1', 'I want milk.'),
    durablePrior,
    true,
  );

  assert.equal(milk.rpg?.node_id, 'find_red_cup');
  assert.equal(milk.rpg?.world_revision, 2);
});

test('deterministic IDs are stable for an idempotent plan replay', () => {
  const director = new LearningDirector();
  const request = objectTurn('t1', null, 'fridge');
  const first = director.plan(request, undefined, false);
  const replay = director.plan(request, undefined, false);

  assert.equal(replay.teaching_action.action_id, first.teaching_action.action_id);
  assert.equal(
    replay.rpg?.speech_act_evidence.evidence_id,
    first.rpg?.speech_act_evidence.evidence_id,
  );
});
