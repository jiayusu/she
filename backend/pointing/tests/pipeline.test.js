// 指向主流程测试（FR-P01/05/06/07）：分级选路、兜底链、隐私停流、埋点字段、无空响应。
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { PointingPipeline, gradeGestureFrames } from '../web/js/pipeline.js';
import { makeHand, poses, TEST_DIMS } from './helpers/handpose.js';

const BOXES = [
  { label: '杯子', score: 0.9, bbox: [240, 120, 90, 110] },   // 指向正中 → 射线命中且最近
  { label: '球', score: 0.8, bbox: [60, 300, 80, 80] },
];
const HAND = makeHand({ angleDeg: -90, wrist: [325, 400] });  // 指向上方，穿过杯子

function makeDeps(overrides = {}) {
  const d = {
    utterances: [],
    sessions: [],
    events: [],
    cameraOpenCount: 0,
    cameraCloseCount: 0,
    now: () => Date.now(),
    speak: async (text) => { d.utterances.push(text); return text; },
    openCamera: async () => { d.cameraOpenCount++; return { handle: 1 }; },
    captureBurst: async () => ({ list: [1, 2, 3, 4, 5].map(() => ({ ...TEST_DIMS })), captureStartDelayMs: 320 }),
    closeCamera: () => { d.cameraCloseCount++; },
    handLandmarks: () => HAND,
    detectObjects: async () => BOXES,
    privacy: { uploadCrop: false },
    apiSee: async () => ({ text: '这是杯子呀！王冠的小知识。', source: 'template' }),
    templateReply: (box) => ({ text: `本地模板：这是${box.label}呀！`, source: 'template-local' }),
    sendTelemetry: (s) => { d.sessions.push(s); },
    confirmSpeech: null, // 由 scriptConfirm 注入
    onEvent: (e) => d.events.push(e),
    ...overrides,
  };
  return d;
}

function scriptConfirm(answers) {
  const queue = [...answers];
  return {
    nameOf: (b) => b.label,
    askYesNo: async () => {},
    askPair: async () => {},
    getAnswer: async () => queue.shift() ?? { kind: 'timeout' },
  };
}

test('FR-P07 分级：≥3 帧轻确认 / 1-2 帧重确认 / 0 帧中心兜底', () => {
  assert.deepEqual(gradeGestureFrames(5), { mode: 'light', source: 'ray', hits: 5, total: 5 });
  assert.deepEqual(gradeGestureFrames(3), { mode: 'light', source: 'ray', hits: 3, total: 5 });
  assert.deepEqual(gradeGestureFrames(2), { mode: 'heavy', source: 'ray', hits: 2, total: 5 });
  assert.deepEqual(gradeGestureFrames(1), { mode: 'heavy', source: 'ray', hits: 1, total: 5 });
  assert.deepEqual(gradeGestureFrames(0), { mode: 'heavy', source: 'center', hits: 0, total: 5 });
});

test('正常链路：5 帧命中 → 射线选中杯子 → 轻确认 → /api/see 回应', async () => {
  const deps = makeDeps({ confirmSpeech: scriptConfirm([{ kind: 'affirm' }]) });
  const pipeline = new PointingPipeline(deps);
  const r = await pipeline.run('button');
  assert.equal(r.status, 'ok');
  assert.equal(r.outcome, 'confirmed');

  const s = deps.sessions[0];
  assert.equal(s.gestureHitFrames, 5);
  assert.equal(s.selectedLabel, '杯子');       // 射线第一候选
  assert.equal(s.selectedBy, 'ray');
  assert.equal(s.confirmStyle, 'light');
  assert.equal(s.confirmResult, 'affirm');
  assert.equal(s.corrections, 0);
  assert.equal(s.outcome, 'confirmed');
  assert.ok(s.triggerToCaptureMs >= 0);
  // FR-P06：窗口结束必须停流
  assert.equal(deps.cameraCloseCount, 1);
  assert.ok(deps.events.some((e) => e.type === 'camera-stopped'));
  assert.deepEqual(deps.utterances, ['这是杯子呀！王冠的小知识。']);
});

test('FR-P05：LLM(/api/see) 失败 → 本地模板回应，不空响应', async () => {
  const deps = makeDeps({
    confirmSpeech: scriptConfirm([{ kind: 'affirm' }]),
    apiSee: async () => { throw new Error('network down'); },
  });
  const pipeline = new PointingPipeline(deps);
  const r = await pipeline.run('button');
  assert.equal(r.outcome, 'confirmed');
  assert.equal(deps.sessions[0].apiSource, 'template-local');
  assert.ok(deps.utterances.every((t) => t && t.length > 0));
  assert.ok(deps.utterances[0].includes('杯子'));
});

test('FR-P05：0 帧命中 → 中心框兜底 + 重确认（非指向不误触发选物）', async () => {
  const deps = makeDeps({
    handLandmarks: () => poses.fist(),
    confirmSpeech: scriptConfirm([{ kind: 'choice', name: '杯子' }]),
  });
  const pipeline = new PointingPipeline(deps);
  const r = await pipeline.run('voice');
  assert.equal(r.outcome, 'confirmed');
  const s = deps.sessions[0];
  assert.equal(s.gestureHitFrames, 0);
  assert.equal(s.selectedBy, 'center');
  // 中心兜底：杯子框中心 (285,175) 距画面中心 (320,240) 最近
  assert.equal(s.selectedLabel, '杯子');
  assert.equal(s.confirmStyle, 'heavy'); // 兜底不静默放行
});

test('FR-P05：检出 0 框 → "再对准一点"重试 → 仍 0 框 → 优雅收尾', async () => {
  const deps = makeDeps({
    detectObjects: async () => [],
    confirmSpeech: scriptConfirm([]),
  });
  const pipeline = new PointingPipeline(deps);
  const r = await pipeline.run('button');
  assert.equal(r.outcome, 'no-object');
  assert.ok(deps.utterances.some((t) => t.includes('再对准一点')));
  assert.ok(deps.utterances.at(-1).includes('再试一次'));
  // 每次重试都是新窗口：开 3 次、关 3 次（FR-P06）
  assert.equal(deps.cameraOpenCount, 3);
  assert.equal(deps.cameraCloseCount, 3);
});

test('FR-P05：摄像头打不开 → 有台词的兜底，不报错不空白', async () => {
  const deps = makeDeps({
    openCamera: async () => { throw new Error('NotAllowedError'); },
  });
  const pipeline = new PointingPipeline(deps);
  const r = await pipeline.run('button');
  assert.equal(r.outcome, 'camera-fallback');
  assert.ok(deps.utterances[0].includes('摄像头'));
});

test('确认被连续否定 → 优雅退出台词', async () => {
  const deps = makeDeps({ confirmSpeech: scriptConfirm([{ kind: 'deny' }, { kind: 'deny' }]) });
  const pipeline = new PointingPipeline(deps);
  const r = await pipeline.run('button');
  assert.equal(r.outcome, 'exit');
  assert.ok(deps.utterances.at(-1).includes('别的东西'));
  assert.equal(deps.sessions[0].corrections, 2);
});

test('FR-P01/06：采帧延迟入埋点；3/5 帧命中走轻确认，crown 触发可走通全链', async () => {
  let toggle = false;
  const deps = makeDeps({
    handLandmarks: () => { toggle = !toggle; return toggle ? HAND : poses.fist(); }, // 5 帧中 3 帧命中
    confirmSpeech: scriptConfirm([{ kind: 'choice', name: '球' }]),
  });
  const pipeline = new PointingPipeline(deps);
  const r = await pipeline.run('crown');
  assert.equal(r.outcome, 'confirmed');
  const s = deps.sessions[0];
  assert.equal(s.gestureHitFrames, 3);
  assert.equal(s.confirmStyle, 'light'); // 3 帧 → 轻确认
  assert.equal(s.selectedLabel, '球');
  assert.equal(s.trigger, 'crown');
});

test('并发防重入：会话进行中再次触发返回 busy', async () => {
  let release;
  const gate = new Promise((res) => { release = res; });
  const deps = makeDeps({
    confirmSpeech: scriptConfirm([{ kind: 'affirm' }]),
    captureBurst: async () => { await gate; return { list: [{ w: 640, h: 640 }], captureStartDelayMs: 10 }; },
  });
  const pipeline = new PointingPipeline(deps);
  const p1 = pipeline.run('button');
  const p2 = await pipeline.run('button');
  assert.equal(p2.status, 'busy');
  release();
  const r1 = await p1;
  assert.equal(r1.status, 'ok');
});

test('任何路径无空响应：异常也会说一句话', async () => {
  const deps = makeDeps({
    captureBurst: async () => { throw new Error('boom'); },
  });
  const pipeline = new PointingPipeline(deps);
  const r = await pipeline.run('button');
  assert.equal(r.status, 'error');
  assert.ok(deps.utterances.length >= 1);
  assert.ok(deps.utterances.every((t) => t && t.length > 0));
});
