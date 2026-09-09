// Synthetic device only. No microphone, camera, or physical board access.
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { randomUUID } from 'node:crypto';
const require = createRequire(new URL('../backend/device_gateway/package.json', import.meta.url));
const WebSocket = require('ws');
const base = process.env.SHE_SMOKE_URL ?? 'http://127.0.0.1:8081';
const id = `synthetic-${randomUUID()}`;
const identity = {child_id:id,session_id:id,device_id:id};
let sequence = 0, commands = 0;
const ws = new WebSocket(`${base.replace(/^http/,'ws')}/v1/device/session`);
await new Promise((resolve,reject)=>{ws.once('open',resolve);ws.once('error',reject);});
function event(type,payload) {
  ws.send(JSON.stringify({event_id:randomUUID(),contract_version:'1.0',device_id:id,session_id:id,
    sequence:sequence++,occurred_at:new Date().toISOString(),type,payload}));
}
ws.on('message',data=>{
  const value = JSON.parse(String(data));
  if(value.type==='speak') {
    commands++;
    event('command_ack',{command_id:value.command_id,status:'completed',error_code:null});
  }
});
async function call(path,body,status=200) {
  const response = await fetch(`${base}${path}`,{method:body?'POST':'GET',
    headers:{'content-type':'application/json'},body:body?JSON.stringify(body):undefined});
  const value = await response.json();
  assert.equal(response.status,status,JSON.stringify(value));
  return value;
}
async function state() {return call(`/v1/learning/state?${new URLSearchParams({child_id:id,session_id:id})}`);}
try {
  const accepted = new Promise(resolve=>ws.once('message',resolve));
  event('hello',{runtime_version:'learning-smoke',capabilities:['simulator']});
  await accepted;
  const firstReq = {...identity,turn_id:'t1',previous_turn_id:null,utterance:'',detected_object:'milk',asr:1};
  const [a,b] = await Promise.all([call('/v1/learning/direct',firstReq),call('/v1/learning/direct',firstReq)]);
  assert.deepEqual(a,b);
  assert.equal(a.persistence.evidence_written,false);
  await call('/v1/learning/direct',{...firstReq,utterance:'changed synthetic request'},409);
  await call('/v1/learning/direct',{...firstReq,turn_id:'stale'},409);
  const delivery = {child_id:id,session_id:id,turn_id:'t1'};
  await Promise.all([call('/v1/learning/execute',delivery,202),call('/v1/learning/execute',delivery,202)]);
  for(let i=0;i<40;i++) {
    if((await state()).latest.delivery.status==='completed') break;
    await new Promise(resolve=>setTimeout(resolve,100));
  }
  assert.equal((await state()).latest.delivery.status,'completed');
  assert.equal(commands,1);
  const nextReq = {...identity,turn_id:'t2',previous_turn_id:'t1',utterance:'I want milk.',asr:1};
  const next = await call('/v1/learning/direct',nextReq);
  assert.equal(next.assessment.target_reached,true);
  assert.equal(next.persistence.evidence_written,true);
  assert.equal(next.learning_memory.targets[0].observations,1);
  assert.deepEqual(await call('/v1/learning/direct',nextReq),next);
  const unplayed = await call('/v1/learning/direct',{...nextReq,turn_id:'t3',previous_turn_id:'t2'});
  assert.equal(unplayed.persistence.evidence_written,false);
  assert.equal(unplayed.learning_loop.assessed_target,null);
  assert.equal((await state()).profile.targets[0].observations,1);
  console.log(JSON.stringify({result:'Learning smoke passed',child_id:id,session_id:id,
    checks:['concurrent replay','conflict','stale turn','single playback','completed ACK','evidence once','unplayed exclusion']}));
} finally {ws.close();}
