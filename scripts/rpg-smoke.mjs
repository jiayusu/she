// Synthetic device only. No microphone, camera, physical object, or RDK X5 access.
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { randomUUID } from 'node:crypto';

const require = createRequire(new URL('../backend/device_gateway/package.json', import.meta.url));
const WebSocket = require('ws');
const base = process.env.SHE_SMOKE_URL ?? 'http://127.0.0.1:8080';
const identityId = `rpg-${randomUUID()}`;
const identity = { child_id: identityId, session_id: identityId, device_id: identityId };
let sequence = 0;
let speakCommands = 0;
const ackStatuses = [];
const spokenCommands = [];

const ws = new WebSocket(`${base.replace(/^http/, 'ws')}/v1/device/session`);
await new Promise((resolve, reject) => {
  ws.once('open', resolve);
  ws.once('error', reject);
});

function sendEvent(type, payload) {
  ws.send(JSON.stringify({
    event_id: randomUUID(),
    contract_version: '1.0',
    device_id: identityId,
    session_id: identityId,
    sequence: sequence++,
    occurred_at: new Date().toISOString(),
    type,
    payload,
  }));
}

ws.on('message', (data) => {
  const value = JSON.parse(String(data));
  if (value.type === 'speak') {
    speakCommands++;
    const status = ackStatuses.shift() ?? 'completed';
    spokenCommands.push({ command_id: value.command_id, status });
    sendEvent('command_ack', {
      command_id: value.command_id,
      status,
      error_code: status === 'failed' ? 'synthetic_speak_failure' : null,
    });
  }
});

async function call(path, body, expectedStatus = 200) {
  const response = await fetch(`${base}${path}`, {
    method: body === undefined ? 'GET' : 'POST',
    headers: { 'content-type': 'application/json' },
    ...(body === undefined ? {} : { body: JSON.stringify(body) }),
  });
  const value = await response.json();
  assert.equal(response.status, expectedStatus, JSON.stringify(value));
  return value;
}

function turn(turn_id, previous_turn_id, input_kind, fields = {}) {
  return {
    contract_version: '1.0',
    ...identity,
    turn_id,
    previous_turn_id,
    input_kind,
    utterance: '',
    asr: null,
    emotion: null,
    detected_object: null,
    perception_event_id: `event-${turn_id}`,
    ...fields,
  };
}

async function state(turn_id) {
  const query = {
    child_id: identityId,
    session_id: identityId,
    ...(turn_id === undefined ? {} : { turn_id }),
  };
  return call(`/v1/rpg/state?${new URLSearchParams(query)}`);
}

async function executeAndWait(turn_id, {
  ackStatus = 'completed',
  duplicate = false,
} = {}) {
  const before = speakCommands;
  ackStatuses.push(ackStatus);
  const request = {
    child_id: identityId,
    session_id: identityId,
    turn_id,
  };
  if (duplicate) {
    await Promise.all([
      call('/v1/learning/execute', request, 202),
      call('/v1/learning/execute', request, 202),
    ]);
  } else {
    await call('/v1/learning/execute', request, 202);
  }
  for (let attempt = 0; attempt < 40; attempt++) {
    const snapshot = await state();
    if (snapshot.turn_id === turn_id && snapshot.delivery_status === ackStatus) {
      assert.equal(speakCommands - before, 1, `speak_count:${turn_id}`);
      return snapshot;
    }
    await new Promise((resolve) => setTimeout(resolve, 100));
  }
  throw new Error(`delivery_timeout:${turn_id}:${ackStatus}`);
}

async function assertCompletedExecuteReplay(turn_id) {
  const before = speakCommands;
  const delivery = await call('/v1/learning/execute', {
    child_id: identityId,
    session_id: identityId,
    turn_id,
  }, 202);
  assert.equal(delivery.status, 'completed');
  assert.equal(speakCommands, before, `duplicate_speak:${turn_id}`);
}

try {
  const helloAccepted = new Promise((resolve) => ws.once('message', resolve));
  sendEvent('hello', { runtime_version: 'rpg-smoke', capabilities: ['simulator'] });
  await helloAccepted;

  // The same turn is a pure replay, and duplicate delivery emits one speak only.
  const fridgeTurn = turn('t1', null, 'object_observed', {
    detected_object: 'fridge',
  });
  const fridge = await call('/v1/rpg/direct', fridgeTurn);
  assert.equal(fridge.rpg.node_id, 'collect_milk');
  assert.equal(fridge.rpg.phase, 'presenting');
  assert.equal(fridge.rpg.confirmed_object, 'fridge');
  assert.equal(fridge.rpg.world_revision, 1);
  const fridgeRevision = (await state()).learning_revision;
  assert.deepEqual(await call('/v1/rpg/direct', fridgeTurn), fridge);
  assert.equal((await state()).learning_revision, fridgeRevision);
  const fridgeReady = await executeAndWait('t1', { duplicate: true });
  assert.equal(fridgeReady.quest.phase, 'awaiting_speech');
  assert.equal(fridgeReady.quest.confirmed_object, 'fridge');
  await assertCompletedExecuteReplay('t1');

  // Low-confidence ASR neither advances the world nor counts as a failed attempt.
  const uncertain = await call('/v1/rpg/direct', turn('t2', 't1', 'speech', {
    utterance: 'I want milk.',
    asr: 0.4,
  }));
  assert.equal(uncertain.rpg.speech_act_evidence.error_type, 'low_confidence');
  assert.equal(uncertain.rpg.speech_act_evidence.quest_satisfied, false);
  assert.equal(uncertain.learning_loop.failed_attempts, 0);
  assert.equal(uncertain.rpg.node_id, 'collect_milk');
  assert.equal(uncertain.rpg.world_revision, 1);
  assert.deepEqual(uncertain.rpg.inventory, []);
  assert.deepEqual(uncertain.rpg.world_events, []);
  await executeAndWait('t2');

  // A confident wrong slot still cannot mutate the world. Fail its speak ACK.
  const water = await call('/v1/rpg/direct', turn('t3', 't2', 'speech', {
    utterance: 'I want water.',
    asr: 0.98,
  }));
  assert.equal(water.rpg.speech_act_evidence.error_type, 'wrong_slot');
  assert.equal(water.rpg.speech_act_evidence.quest_satisfied, false);
  assert.equal(water.learning_loop.failed_attempts, 1);
  assert.equal(water.rpg.node_id, 'collect_milk');
  assert.equal(water.rpg.world_revision, 1);
  assert.deepEqual(water.rpg.inventory, []);
  assert.deepEqual(water.rpg.world_events, []);
  const failedPrompt = await executeAndWait('t3', { ackStatus: 'failed' });
  assert.equal(failedPrompt.delivery_status, 'failed');
  assert.equal(failedPrompt.quest.phase, 'delivery_failed');
  assert.equal(failedPrompt.quest.world_revision, 1);

  // Failed delivery closes the normal input gate. Only an explicit resume may recover.
  const rejectedSpeech = await call('/v1/rpg/direct', turn('t4', 't3', 'speech', {
    utterance: 'I want milk.',
    asr: 0.98,
  }), 409);
  assert.equal(rejectedSpeech.error.code, 'previous_delivery_not_completed');

  const resumedPrompt = await call('/v1/rpg/direct', turn('t4', 't3', 'resume'));
  assert.equal(resumedPrompt.rpg.node_id, 'collect_milk');
  assert.equal(resumedPrompt.rpg.phase, 'presenting');
  assert.equal(resumedPrompt.rpg.confirmed_object, 'fridge');
  assert.equal(resumedPrompt.rpg.world_revision, 1);
  assert.deepEqual(resumedPrompt.rpg.world_events, []);
  await executeAndWait('t4');

  // The milk Speech Act advances exactly once, even when the same direct turn is replayed.
  const milkTurn = turn('t5', 't4', 'speech', {
    utterance: 'I want milk.',
    asr: 0.97,
  });
  const milk = await call('/v1/rpg/direct', milkTurn);
  assert.equal(milk.rpg.speech_act_evidence.quest_satisfied, true);
  assert.equal(milk.rpg.node_id, 'find_red_cup');
  assert.equal(milk.rpg.phase, 'seeking_object');
  assert.equal(milk.rpg.world_revision, 2);
  assert.deepEqual(milk.rpg.inventory, ['milk_token']);
  assert.equal(milk.rpg.world_events.length, 1);
  const milkEventId = milk.rpg.world_events[0].event_id;
  const milkLearningRevision = (await state()).learning_revision;
  const milkReplay = await call('/v1/rpg/direct', milkTurn);
  assert.deepEqual(milkReplay, milk);
  assert.equal(milkReplay.rpg.world_events[0].event_id, milkEventId);
  assert.equal((await state()).learning_revision, milkLearningRevision);

  // If transition feedback fails, resume replays the same feedback without a second event.
  const failedTransition = await executeAndWait('t5', {
    ackStatus: 'failed',
    duplicate: true,
  });
  assert.equal(failedTransition.delivery_status, 'failed');
  assert.equal(failedTransition.quest.phase, 'seeking_object');
  assert.equal(failedTransition.quest.world_revision, 2);
  assert.deepEqual(failedTransition.quest.inventory, ['milk_token']);

  const resumedTransition = await call('/v1/rpg/direct', turn('t6', 't5', 'resume'));
  assert.equal(resumedTransition.teaching_action.teaching_action, 'advance_story');
  assert.equal(
    resumedTransition.teaching_action.feedback_id,
    milk.teaching_action.feedback_id,
  );
  assert.equal(resumedTransition.rpg.feedback_id, milk.rpg.feedback_id);
  assert.equal(resumedTransition.rpg.node_id, 'find_red_cup');
  assert.equal(resumedTransition.rpg.phase, 'seeking_object');
  assert.equal(resumedTransition.rpg.world_revision, 2);
  assert.deepEqual(resumedTransition.rpg.inventory, ['milk_token']);
  assert.deepEqual(resumedTransition.rpg.world_events, []);
  await executeAndWait('t6');

  // A blue-cup observation and choice are embodied context, not a valid red-cup transition.
  const blueCup = await call('/v1/rpg/direct', turn('t7', 't6', 'object_observed', {
    detected_object: 'blue_cup',
  }));
  assert.equal(blueCup.rpg.node_id, 'find_red_cup');
  assert.equal(blueCup.rpg.phase, 'presenting');
  assert.equal(blueCup.rpg.confirmed_object, 'blue_cup');
  assert.equal(blueCup.rpg.world_revision, 2);
  assert.deepEqual(blueCup.rpg.inventory, ['milk_token']);
  assert.deepEqual(blueCup.rpg.world_events, []);
  await executeAndWait('t7');

  const blueChoice = await call('/v1/rpg/direct', turn('t8', 't7', 'speech', {
    utterance: 'I choose the blue cup.',
    asr: 0.98,
  }));
  assert.equal(blueChoice.rpg.speech_act_evidence.error_type, 'wrong_slot');
  assert.equal(blueChoice.rpg.speech_act_evidence.quest_satisfied, false);
  assert.equal(blueChoice.rpg.node_id, 'find_red_cup');
  assert.equal(blueChoice.rpg.world_revision, 2);
  assert.deepEqual(blueChoice.rpg.inventory, ['milk_token']);
  assert.deepEqual(blueChoice.rpg.world_events, []);
  await executeAndWait('t8');

  // Reconfirm the intended physical context, then complete through the red-cup act.
  const redCup = await call('/v1/rpg/direct', turn('t9', 't8', 'object_observed', {
    detected_object: 'red_cup',
  }));
  assert.equal(redCup.rpg.node_id, 'find_red_cup');
  assert.equal(redCup.rpg.phase, 'presenting');
  assert.equal(redCup.rpg.confirmed_object, 'red_cup');
  assert.equal(redCup.rpg.world_revision, 2);
  assert.deepEqual(redCup.rpg.world_events, []);
  const redCupReady = await executeAndWait('t9');
  assert.equal(redCupReady.quest.phase, 'awaiting_speech');

  const complete = await call('/v1/rpg/direct', turn('t10', 't9', 'speech', {
    utterance: 'I choose the red cup.',
    asr: 0.98,
  }));
  assert.equal(complete.rpg.speech_act_evidence.quest_satisfied, true);
  assert.equal(complete.rpg.phase, 'completed');
  assert.equal(complete.rpg.world_revision, 4);
  assert.deepEqual(complete.rpg.inventory, ['milk_token', 'red_cup_token']);
  assert.equal(complete.rpg.world_events.length, 2);
  const completed = await executeAndWait('t10');
  assert.equal(completed.quest.phase, 'completed');
  assert.equal(completed.quest.next_quest_id, null);

  assert.equal(speakCommands, 10);
  assert.equal(spokenCommands.length, 10);
  assert.equal(spokenCommands.filter(({ status }) => status === 'failed').length, 2);
  assert.equal(ackStatuses.length, 0);

  console.log(JSON.stringify({
    result: 'Embodied Language RPG smoke passed',
    child_id: identityId,
    session_id: identityId,
    world_revision: completed.quest.world_revision,
    checks: [
      'same-turn direct replay',
      'duplicate execute single playback',
      'low-ASR no-failure gate',
      'wrong-water no-transition gate',
      'failed prompt delivery projection',
      'normal-input rejection after failed delivery',
      'explicit prompt resume',
      'single world event on direct replay',
      'failed transition-feedback replay without new event',
      'blue-cup no-transition gate',
      'red-cup Speech Act completion',
      'safe quest projection',
    ],
  }));
} finally {
  ws.close();
}
