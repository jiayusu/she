// FR-P03 射线选物测试：多交取最近、无交取离指尖最近、身后不取、中心兜底。
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { rayBoxIntersect, selectCandidates, centerFallback, distancePointToBox } from '../web/js/raycast.js';

const DIMS = { w: 640, h: 480 };

function dir(from, to) {
  return { from, to, tip: to };
}

test('slab 求交：命中与未命中', () => {
  const o = { x: 320, y: 432 };
  const d = { x: 0, y: -1 };
  const hit = rayBoxIntersect(o, d, { x: 280, y: 100, w: 80, h: 80 });
  assert.ok(hit);
  assert.equal(hit.t, 432 - 180); // 进入框下边缘
  assert.equal(rayBoxIntersect(o, d, { x: 100, y: 300, w: 80, h: 80 }), null);
});

test('原点在框内：t=0 命中', () => {
  const hit = rayBoxIntersect({ x: 320, y: 140 }, { x: 1, y: 0 }, { x: 280, y: 100, w: 80, h: 80 });
  assert.ok(hit);
  assert.equal(hit.t, 0);
});

test('平行且不在 slab 内：无交', () => {
  assert.equal(rayBoxIntersect({ x: 50, y: 50 }, { x: 1, y: 0 }, { x: 280, y: 100, w: 80, h: 80 }), null);
});

test('多交取最近（沿射线 t 升序）', () => {
  const boxes = [
    { label: '远', score: 0.9, bbox: [300, 0, 40, 60] },     // 命中 t=372
    { label: '近', score: 0.5, bbox: [280, 100, 80, 80] },   // 命中 t=252
    { label: '偏', score: 0.8, bbox: [100, 300, 80, 80] },   // 不交
  ];
  const { ranked, hits, rayUsed } = selectCandidates(
    dir({ x: 0.5, y: 0.9 }, { x: 0.5, y: 0.7 }), boxes, DIMS
  );
  assert.equal(rayUsed, true);
  assert.equal(hits.length, 2);
  assert.equal(ranked[0].label, '近'); // 分数低但更近 → 排第一
  assert.equal(ranked[1].label, '远');
  assert.equal(ranked[2].label, '偏');
});

test('无交 → 取离食指尖最近的框', () => {
  const boxes = [
    { label: '近尖', score: 0.6, bbox: [340, 250, 60, 50] },
    { label: '远尖', score: 0.9, bbox: [40, 40, 60, 50] },
  ];
  const { ranked, rayUsed } = selectCandidates(
    dir({ x: 0.5, y: 0.9 }, { x: 0.5, y: 0.7 }), boxes, DIMS
  );
  assert.equal(rayUsed, false);
  assert.equal(ranked[0].label, '近尖');
});

test('只取前方交点：目标在手腕身后不命中（改由指尖距离兜底排序）', () => {
  // 指向上方，但框在手腕下方（身后）
  const boxes = [{ label: '身后', score: 0.9, bbox: [280, 440, 80, 38] }];
  const { hits, ranked, rayUsed } = selectCandidates(
    dir({ x: 0.5, y: 0.9 }, { x: 0.5, y: 0.7 }), boxes, DIMS
  );
  assert.equal(hits.length, 0);
  assert.equal(rayUsed, false);
  assert.equal(ranked[0].label, '身后');
});

test('零方向（length≈0）不抛错，回退空候选', () => {
  const { ranked, rayUsed } = selectCandidates(
    dir({ x: 0.5, y: 0.5 }, { x: 0.5, y: 0.5 }), [{ label: 'x', bbox: [0, 0, 10, 10] }], DIMS
  );
  assert.equal(rayUsed, false);
  assert.deepEqual(ranked, []);
});

test('centerFallback：离画面中心最近的框优先', () => {
  const boxes = [
    { label: '角落', bbox: [0, 0, 60, 60] },
    { label: '中央', bbox: [280, 200, 80, 80] },
  ];
  const ranked = centerFallback(boxes, DIMS);
  assert.equal(ranked[0].label, '中央');
  assert.equal(centerFallback([], DIMS).length, 0);
});

test('distancePointToBox：内部点距离 0', () => {
  assert.equal(distancePointToBox({ x: 10, y: 10 }, { x: 0, y: 0, w: 20, h: 20 }), 0);
  assert.equal(distancePointToBox({ x: 30, y: 10 }, { x: 0, y: 0, w: 20, h: 20 }), 10);
});
