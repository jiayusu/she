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
    sendEvent('command_ack', {
      command_id: value.command_id,
      status: 'completed',
      error_code: null,
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

function turn(turn_id, previous_turn_id, input_kind, fields) {
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

async function state() {
  return call(`/v1/rpg/state?${new URLSearchParams({
    child_id: identityId,
    session_id: identityId,
  })}`);
}

async function executeAndWait(turn_id) {
  await call('/v1/learning/execute', {
    child_id: identityId,
    session_id: identityId,
    turn_id,
  }, 202);
  for (let attempt = 0; attempt < 40; attempt++) {
    const snapshot = await state();
    if (snapshot.turn_id === turn_id && snapshot.delivery_status === 'completed') return snapshot;
    await new Promise((resolve) => setTimeout(resolve, 100));
  }
  throw new Error(`delivery_timeout:${turn_id}`);
}

try {
  const helloAccepted = new Promise((resolve) => ws.once('message', resolve));
  sendEvent('hello', { runtime_version: 'rpg-smoke', capabilities: ['simulator'] });
  await helloAccepted;

  const fridge = await call('/v1/rpg/direct', turn('t1', null, 'object_observed', {
    detected_object: 'fridge',
  }));
  assert.equal(fridge.rpg.node_id, 'collect_milk');
  assert.equal(fridge.rpg.phase, 'presenting');
  assert.equal(fridge.rpg.world_revision, 1);
  assert.equal((await executeAndWait('t1')).quest.phase, 'awaiting_speech');

  const milk = await call('/v1/rpg/direct', turn('t2', 't1', 'speech', {
    utterance: 'Milk!',
    asr: 0.97,
  }));
  assert.equal(milk.rpg.speech_act_evidence.quest_satisfied, true);
  assert.deepEqual(milk.rpg.inventory, ['milk_token']);
  assert.equal(milk.rpg.node_id, 'find_red_cup');
  assert.equal(milk.rpg.world_revision, 2);
  await executeAndWait('t2');

  const table = await call('/v1/rpg/direct', turn('t3', 't2', 'object_observed', {
    detected_object: 'table',
  }));
  assert.equal(table.rpg.node_id, 'find_red_cup');
  assert.equal(table.rpg.phase, 'presenting');
  assert.equal((await executeAndWait('t3')).quest.phase, 'awaiting_speech');

  const cup = await call('/v1/rpg/direct', turn('t4', 't3', 'speech', {
    utterance: 'Red cup!',
    asr: 0.98,
  }));
  assert.equal(cup.rpg.speech_act_evidence.quest_satisfied, true);
  assert.equal(cup.rpg.phase, 'completed');
  assert.equal(cup.rpg.world_revision, 4);
  assert.deepEqual(cup.rpg.inventory, ['milk_token', 'red_cup_token']);
  const completed = await executeAndWait('t4');
  assert.equal(completed.quest.phase, 'completed');
  assert.equal(completed.quest.next_quest_id, null);
  assert.equal(speakCommands, 4);

  console.log(JSON.stringify({
    result: 'Embodied Language RPG smoke passed',
    child_id: identityId,
    session_id: identityId,
    world_revision: completed.quest.world_revision,
    checks: [
      'fridge object gate',
      'completed prompt gate',
      'milk Speech Act transition',
      'table object gate',
      'red-cup Speech Act transition',
      'quest completion',
      'single playback per turn',
      'safe quest projection',
    ],
  }));
} finally {
  ws.close();
}
