// 测试辅助：合成 21 关键点手部模型（像素空间构造 → 归一化）。
// 用真实的角度几何生成"伸直/弯曲/半伸"手指，保证 evaluateGesture 的夹角判定可被验证。

export const TEST_DIMS = { w: 640, h: 640 };

function rot(v, deg) {
  const r = (deg * Math.PI) / 180;
  return { x: v.x * Math.cos(r) - v.y * Math.sin(r), y: v.x * Math.sin(r) + v.y * Math.cos(r) };
}

// 从 start 沿 dir 逐节生长，turnDegs 为每节相对上一节的转折角（0=共线伸直）
function chain(start, dir, lens, turnDegs, scale) {
  const pts = [start];
  let d = dir;
  let p = start;
  for (let i = 0; i < lens.length; i++) {
    d = rot(d, turnDegs[i]);
    p = { x: p.x + d.x * lens[i] * scale, y: p.y + d.y * lens[i] * scale };
    pts.push(p);
  }
  return pts; // [MCP, PIP, DIP, TIP]
}

const MODE_TURNS = {
  straight: [0, 0, 0],    // PIP 夹角 180°
  half: [45, 50, 20],     // PIP 夹角 ~135°：既不满足伸直(≥140)也不满足弯曲(≤110)
  curled: [100, 110, 60], // PIP 夹角 ~80°，指尖回勾
};

/**
 * @param {object} o
 *  - angleDeg 指向方向角（屏幕坐标，-90=向上）
 *  - scale    掌长像素
 *  - wrist    [x,y]
 *  - index/middle/ring/pinky: 'straight' | 'half' | 'curled'
 *  - visibility 关键点可见度
 * @returns {Array<{x,y,visibility}>} 21 归一化关键点
 */
export function makeHand({
  angleDeg = -90,
  scale = 150,
  wrist = [320, 520],
  index = 'straight',
  middle = 'curled',
  ring = 'curled',
  pinky = 'curled',
  visibility = 0.97,
} = {}) {
  const dir = rot({ x: 1, y: 0 }, angleDeg);
  const perp = { x: -dir.y, y: dir.x };
  const at = (along, side) => ({
    x: wrist[0] + dir.x * along * scale + perp.x * side * scale,
    y: wrist[1] + dir.y * along * scale + perp.y * side * scale,
  });

  const lm = new Array(21);
  lm[0] = at(0, 0); // 腕

  // 拇指（判定不依赖）
  lm[1] = at(0.10, -0.10);
  lm[2] = at(0.20, -0.15);
  lm[3] = at(0.28, -0.18);
  lm[4] = at(0.34, -0.20);

  const fingers = { index, middle, ring, pinky };
  const sideOff = { index: -0.10, middle: -0.02, ring: 0.06, pinky: 0.14 };
  const lens = { index: [0.30, 0.22, 0.18], middle: [0.32, 0.24, 0.20], ring: [0.30, 0.22, 0.18], pinky: [0.24, 0.17, 0.14] };
  const mcpIds = { index: 5, middle: 9, ring: 13, pinky: 17 };

  for (const [name, mode] of Object.entries(fingers)) {
    const mcp = at(0.35, sideOff[name]);
    const pts = chain(mcp, dir, lens[name], MODE_TURNS[mode], scale);
    [0, 1, 2, 3].forEach((i) => { lm[mcpIds[name] + i] = pts[i]; });
  }

  return lm.map((p) => ({ x: p.x / TEST_DIMS.w, y: p.y / TEST_DIMS.h, visibility }));
}

// 常用姿态快捷方式
export const poses = {
  pointing: (o = {}) => makeHand({ ...o }),
  relaxedPoint: (o = {}) => makeHand({ ...o, middle: 'straight' }),
  fist: (o = {}) => makeHand({ ...o, index: 'curled', middle: 'curled', ring: 'curled', pinky: 'curled' }),
  openPalm: (o = {}) =>
    makeHand({ ...o, index: 'straight', middle: 'straight', ring: 'straight', pinky: 'straight' }),
  reachGrab: (o = {}) => makeHand({ ...o, index: 'half', middle: 'curled', ring: 'curled', pinky: 'curled' }),
};
