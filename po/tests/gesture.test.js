// FR-P02 手势判定测试：自采数据 unavailable 时，用合成姿态集验证角度规则的召回/误触发性状。
// 验收口径（PRD）：指向召回 ≥90%；非指向伸手误触发 ≤5% —— 合成集上应 0 漏检 0 误报，
// 真实儿童数据上线后再用同口径回归。
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { evaluateGesture } from '../web/js/gesture.js';
import { makeHand, poses, TEST_DIMS } from './helpers/handpose.js';

test('指向姿态：不同方向/位置/尺度全部命中（召回 100%）', () => {
  const angles = [-90, -60, -30, 0, 30, 60, 90, 150, -150];
  let hit = 0;
  let total = 0;
  for (const angleDeg of angles) {
    for (const scale of [130, 160, 210]) {
      for (const wrist of [[320, 520], [150, 300], [480, 420]]) {
        total++;
        const g = evaluateGesture(makeHand({ angleDeg, scale, wrist }), TEST_DIMS);
        if (g?.isPointing && g.strict) hit++;
        else assert.fail(`应判定为指向: angle=${angleDeg} scale=${scale} wrist=${wrist} → ${g?.reason}`);
      }
    }
  }
  assert.equal(hit / total, 1);
});

test('放宽档：食指+中指并伸也算指向（relaxed 标记）', () => {
  const g = evaluateGesture(poses.relaxedPoint(), TEST_DIMS);
  assert.equal(g.isPointing, true);
  assert.equal(g.strict, false);
  assert.equal(g.relaxed, true);
});

test('非指向伸手不触发（误报 0）', () => {
  // 拳头：食指也弯
  assert.equal(evaluateGesture(poses.fist(), TEST_DIMS).isPointing, false);
  // 整个巴掌伸过去：其余手指不弯（严格与放宽都不满足）
  assert.equal(evaluateGesture(poses.openPalm(), TEST_DIMS).isPointing, false);
  // 伸手拿杯子：食指半弯（PIP ~135°），不直也不算指向
  assert.equal(evaluateGesture(poses.reachGrab(), TEST_DIMS).isPointing, false);
  const g = evaluateGesture(poses.reachGrab(), TEST_DIMS);
  assert.equal(g.reason, 'not_pointing');
});

test('手腕不可见 / 手太小：拒绝判定（防噪声）', () => {
  const hidden = makeHand({ visibility: 0.3 });
  const g1 = evaluateGesture(hidden, TEST_DIMS);
  assert.equal(g1.isPointing, false);
  assert.equal(g1.reason, 'wrist_invisible');

  const tiny = makeHand({ scale: 70 });
  const g2 = evaluateGesture(tiny, TEST_DIMS);
  assert.equal(g2.isPointing, false);
  assert.equal(g2.reason, 'hand_too_small');
});

test('非法输入返回 null', () => {
  assert.equal(evaluateGesture(null, TEST_DIMS), null);
  assert.equal(evaluateGesture(makeHand().slice(0, 10), TEST_DIMS), null);
  assert.equal(evaluateGesture(makeHand(), { w: 0, h: 0 }), null);
});

test('输出方向向量：腕(0)→食指根(5)，并带指尖(FR-P03 输入)', () => {
  const g = evaluateGesture(makeHand({ angleDeg: -90, wrist: [320, 520] }), TEST_DIMS);
  assert.ok(g.direction);
  assert.equal(g.direction.from.x, 320 / 640);
  assert.equal(g.direction.from.y, 520 / 640);
  assert.equal(g.direction.to.y, (520 - 0.35 * 150) / 640);
  assert.ok(g.direction.tip.y < g.direction.to.y); // 指尖在食指根前方
});

test('置信度：严格指向 > 放宽指向；非指向为 0', () => {
  const strict = evaluateGesture(poses.pointing(), TEST_DIMS);
  const relaxed = evaluateGesture(poses.relaxedPoint(), TEST_DIMS);
  const none = evaluateGesture(poses.openPalm(), TEST_DIMS);
  assert.ok(strict.confidence > relaxed.confidence);
  assert.equal(none.confidence, 0);
});
