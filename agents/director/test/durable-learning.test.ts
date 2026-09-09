import { test } from 'node:test';
import assert from 'node:assert/strict';
import { LearningDirector } from '../src/learning-director.ts';
import { validatePreviousDelivery, validateTurn } from '../src/durable-learning.ts';

test('durable planning only assesses completed delivery and resumes stored context', () => {
  const first = new LearningDirector().direct({session_id:'durable',utterance:'',detected_object:'milk',asr:1});
  const req = {session_id:'durable',utterance:'I want milk.',asr:1};
  const blocked = new LearningDirector().plan(req, {action:first.teaching_action, failures:0, touched:Date.now()}, false);
  assert.equal(blocked.assessment.target_reached, false);
  assert.equal(blocked.learning_loop.assessed_target, null);
  const completed = new LearningDirector().plan(req, {action:first.teaching_action, failures:0, touched:Date.now()}, true);
  assert.equal(completed.assessment.target_reached, true);
});

test('RPG speech turns cannot carry stale object context', () => {
  assert.throws(() => validateTurn({
    contract_version: '1.0',
    child_id: 'child',
    session_id: 'session',
    turn_id: 't2',
    previous_turn_id: 't1',
    device_id: 'simulator',
    input_kind: 'speech',
    utterance: 'I want milk.',
    asr: 0.98,
    emotion: null,
    detected_object: 'fridge',
    perception_event_id: 'speech-t2',
  }), /invalid_speech_turn/);
});

test('RPG planning waits for delivery and uses resume only for failed recovery', () => {
  const prior = (status: string) => ({
    delivery: { status },
    response: { rpg: { seed_id: 'milk_picnic' } },
  });

  assert.throws(
    () => validatePreviousDelivery(prior('planned'), 'speech'),
    /delivery_pending/,
  );
  assert.throws(
    () => validatePreviousDelivery(prior('failed'), 'speech'),
    /previous_delivery_not_completed/,
  );
  assert.doesNotThrow(() => validatePreviousDelivery(prior('failed'), 'resume'));
  assert.doesNotThrow(() => validatePreviousDelivery(prior('completed'), 'speech'));
});
