import { test } from 'node:test';
import assert from 'node:assert/strict';
import { LearningDirector } from '../src/learning-director.ts';

test('durable planning only assesses completed delivery and resumes stored context', () => {
  const first = new LearningDirector().direct({session_id:'durable',utterance:'',detected_object:'milk',asr:1});
  const req = {session_id:'durable',utterance:'I want milk.',asr:1};
  const blocked = new LearningDirector().plan(req, {action:first.teaching_action, failures:0, touched:Date.now()}, false);
  assert.equal(blocked.assessment.target_reached, false);
  assert.equal(blocked.learning_loop.assessed_target, null);
  const completed = new LearningDirector().plan(req, {action:first.teaching_action, failures:0, touched:Date.now()}, true);
  assert.equal(completed.assessment.target_reached, true);
});
