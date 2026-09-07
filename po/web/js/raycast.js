// FR-P03 方向射线选物
// 手腕→食指根向量延长，与检出框求交：多交取最近（沿射线 t 最小）；
// 无交取离食指尖最近的框。全部在像素空间计算（归一化坐标会因宽高比失真）。
import { CONFIG } from './config.js';

export function toPxPt(p, dims) {
  return { x: p.x * dims.w, y: p.y * dims.h };
}

/**
 * 射线（原点 o，单位方向 d）与矩形 box{x,y,w,h} 求交（slab 法）。
 * @returns {{t:number,tExit:number}|null} t 为进入距离（≥0，原点在框内时 t=0），不交或仅在身后返回 null
 */
export function rayBoxIntersect(o, d, box, { forwardOnly = CONFIG.ray.forwardOnly } = {}) {
  let tmin = -Infinity;
  let tmax = Infinity;

  const axes = [
    { o: o.x, d: d.x, lo: box.x, hi: box.x + box.w },
    { o: o.y, d: d.y, lo: box.y, hi: box.y + box.h },
  ];
  for (const ax of axes) {
    if (Math.abs(ax.d) < 1e-9) {
      // 方向与该轴平行：原点不在 slab 内则无交
      if (ax.o < ax.lo || ax.o > ax.hi) return null;
      continue;
    }
    const t1 = (ax.lo - ax.o) / ax.d;
    const t2 = (ax.hi - ax.o) / ax.d;
    tmin = Math.max(tmin, Math.min(t1, t2));
    tmax = Math.min(tmax, Math.max(t1, t2));
  }
  if (tmax < tmin) return null;              // 错开
  if (tmax < 0) return null;                 // 交点全在身后
  const t = Math.max(tmin, 0);
  if (forwardOnly && tmin < 0 && tmax < 0) return null;
  return { t, tExit: tmax };
}

// 点到矩形的最短距离（用于"无交取离指尖最近框"）
export function distancePointToBox(p, box) {
  const dx = Math.max(box.x - p.x, 0, p.x - (box.x + box.w));
  const dy = Math.max(box.y - p.y, 0, p.y - (box.y + box.h));
  return Math.hypot(dx, dy);
}

function boxCenter(box) {
  return { x: box.x + box.w / 2, y: box.y + box.h / 2 };
}

/**
 * 射线选物，产出按优先级排序的候选列表。
 * @param {{from:{x,y},to:{x,y},tip:{x,y}}} direction 归一化坐标（gesture.direction）
 * @param {Array<{label,score,bbox:[x,y,w,h]}>} boxes 像素坐标检出框
 * @returns {{ranked, hits, rayUsed}}
 */
export function selectCandidates(direction, boxes, dims) {
  if (!direction || !Array.isArray(boxes) || boxes.length === 0) {
    return { ranked: [], hits: [], rayUsed: false };
  }
  const o = toPxPt(direction.from, dims);
  const to = toPxPt(direction.to, dims);
  const tip = toPxPt(direction.tip, dims);
  let dx = to.x - o.x;
  let dy = to.y - o.y;
  const len = Math.hypot(dx, dy);
  if (len < 1e-6) return { ranked: [], hits: [], rayUsed: false };
  dx /= len;
  dy /= len;

  const hits = [];
  const others = [];
  for (const box of boxes) {
    const rect = { x: box.bbox[0], y: box.bbox[1], w: box.bbox[2], h: box.bbox[3] };
    const hit = rayBoxIntersect(o, { x: dx, y: dy }, rect);
    if (hit) {
      hits.push({ box, ...hit });
    } else {
      others.push({ box, tipDist: distancePointToBox(tip, rect) });
    }
  }

  // 多交取最近；同距取分高
  hits.sort((a, b) => a.t - b.t || (b.box.score ?? 0) - (a.box.score ?? 0));
  others.sort((a, b) => a.tipDist - b.tipDist);

  const ranked = [...hits.map((h) => h.box), ...others.map((x) => x.box)];
  return {
    ranked,
    hits: hits.map(({ box, t }) => ({ box, t: +t.toFixed(1) })),
    rayUsed: hits.length > 0,
  };
}

// FR-P05 兜底：画面中心框选（手势 0 帧命中 / 无方向时使用）
export function centerFallback(boxes, dims) {
  if (!Array.isArray(boxes) || boxes.length === 0) return [];
  const c = { x: dims.w / 2, y: dims.h / 2 };
  return [...boxes].sort(
    (a, b) => distancePointToBox(c, { x: a.bbox[0], y: a.bbox[1], w: a.bbox[2], h: a.bbox[3] })
      - distancePointToBox(c, { x: b.bbox[0], y: b.bbox[1], w: b.bbox[2], h: b.bbox[3] })
  );
}
