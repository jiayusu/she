// FR-P02 指向手势判定
// 规则：食指伸直 + 其余手指弯曲 + 手腕可见（21 关键点向量夹角，尺度不变，不依赖绝对坐标）
// 放宽档（PRD §8）：食指+中指并伸也算指向，残余误差由确认话术吸收。
import { CONFIG } from './config.js';

// MediaPipe Hands 21 关键点：0 腕；每指 [MCP, PIP, DIP, TIP]
const FINGERS = {
  index: [5, 6, 7, 8],
  middle: [9, 10, 11, 12],
  ring: [13, 14, 15, 16],
  pinky: [17, 18, 19, 20],
};

export function toPx(p, dims) {
  return { x: p.x * dims.w, y: p.y * dims.h };
}

export function dist2d(a, b) {
  return Math.hypot(a.x - b.x, a.y - b.y);
}

// PIP 关节夹角（度）：mcp→pip 与 dip→pip 两向量夹角，伸直≈180°，弯曲<90°
export function fingerPipAngle(lms, ids, dims) {
  const a = toPx(lms[ids[0]], dims); // MCP
  const b = toPx(lms[ids[1]], dims); // PIP（顶点）
  const c = toPx(lms[ids[2]], dims); // DIP
  const v1 = { x: a.x - b.x, y: a.y - b.y };
  const v2 = { x: c.x - b.x, y: c.y - b.y };
  const denom = Math.hypot(v1.x, v1.y) * Math.hypot(v2.x, v2.y);
  if (denom < 1e-6) return 180;
  const cos = Math.min(1, Math.max(-1, (v1.x * v2.x + v1.y * v2.y) / denom));
  return (Math.acos(cos) * 180) / Math.PI;
}

// 指尖离腕比例 = dist(TIP, 腕) / dist(MCP, 腕)：伸直≈2+，回勾≈1 以下，尺度不变
export function tipRatio(lms, ids, dims) {
  const wrist = toPx(lms[0], dims);
  const mcp = toPx(lms[ids[0]], dims);
  const tip = toPx(lms[ids[3]], dims);
  const base = dist2d(mcp, wrist);
  if (base < 1e-6) return 0;
  return dist2d(tip, wrist) / base;
}

function fingerState(lms, ids, dims, opts) {
  const angle = fingerPipAngle(lms, ids, dims);
  const ratio = tipRatio(lms, ids, dims);
  return {
    angle,
    ratio,
    extended: angle >= opts.extendedAngle && ratio >= opts.extendedRatio,
    curled: angle <= opts.curledAngle || ratio <= opts.curledRatio,
  };
}

/**
 * @param {Array<{x,y,visibility?}>} lms 21 关键点（归一化坐标）
 * @param {{w:number,h:number}} dims 帧像素尺寸（用于纵横比校正）
 * @returns 判定结果，无效输入返回 null
 */
export function evaluateGesture(lms, dims, opts = CONFIG.gesture) {
  if (!lms || lms.length < 21 || !dims || !dims.w || !dims.h) return null;
  const wrist = lms[0];
  if ((wrist.visibility ?? 1) < opts.wristMinVis) {
    return { isPointing: false, strict: false, relaxed: false, reason: 'wrist_invisible' };
  }
  if ((lms[5].visibility ?? 1) < opts.mcpMinVis) {
    return { isPointing: false, strict: false, relaxed: false, reason: 'hand_invisible' };
  }

  const wristPx = toPx(wrist, dims);
  const mcpPx = toPx(lms[5], dims);
  const diag = Math.hypot(dims.w, dims.h);
  const span = dist2d(wristPx, mcpPx) / diag;
  if (span < opts.minHandSpan) {
    return { isPointing: false, strict: false, relaxed: false, reason: 'hand_too_small' };
  }

  const st = {
    index: fingerState(lms, FINGERS.index, dims, opts),
    middle: fingerState(lms, FINGERS.middle, dims, opts),
    ring: fingerState(lms, FINGERS.ring, dims, opts),
    pinky: fingerState(lms, FINGERS.pinky, dims, opts),
  };

  // 严格指向：食指伸直 + 中/无名/小指弯曲（拇指不约束）
  const strict = st.index.extended && st.middle.curled && st.ring.curled && st.pinky.curled;
  // 放宽指向：食指+中指并伸 + 无名/小指弯曲（整个巴掌伸过去不算：无名小指仍伸直）
  const relaxed =
    opts.allowRelaxed &&
    !strict &&
    st.index.extended &&
    st.middle.extended &&
    st.ring.curled &&
    st.pinky.curled;

  const isPointing = Boolean(strict || relaxed);

  // 置信度：食指越直 + 其余越弯 → 分越高（用于 5 帧里挑最佳帧）
  const idxStraight = Math.min(1, Math.max(0, (st.index.angle - 110) / 70));
  const othersCurled =
    (st.middle.curled ? 1 : 0.25) * 0.4 + (st.ring.curled ? 1 : 0.25) * 0.35 + (st.pinky.curled ? 1 : 0.25) * 0.25;
  const confidence = isPointing ? +(0.55 * idxStraight + 0.45 * othersCurled).toFixed(3) : 0;

  // FR-P03 方向向量：手腕(0) → 食指根(5)，延长线即指向（归一化坐标）
  return {
    isPointing,
    strict,
    relaxed: isPointing && !strict,
    confidence,
    reason: isPointing ? (strict ? 'strict_point' : 'relaxed_point') : 'not_pointing',
    angles: {
      index: +st.index.angle.toFixed(1),
      middle: +st.middle.angle.toFixed(1),
      ring: +st.ring.angle.toFixed(1),
      pinky: +st.pinky.angle.toFixed(1),
    },
    direction: {
      from: { x: lms[0].x, y: lms[0].y },      // 手腕
      to: { x: lms[5].x, y: lms[5].y },        // 食指根
      tip: { x: lms[8].x, y: lms[8].y },       // 食指尖
    },
    landmarks: lms,
  };
}
