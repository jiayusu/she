// 手势源 Provider（FR-P02 的关键点来源）：
//   1) mediapipe  @mediapipe/tasks-vision HandLandmarker（CDN），仅对 5 帧逐帧推理，窗口外零计算
//   2) synthetic  演示合成手：指尖跟随指针位置，生成 21 关键点（走同一套 FR-P02 判定规则）
// 加载失败自动降级 → 返回 null（0 帧命中 → 中心框兜底，FR-P05/07）。
export class MediaPipeHandSource {
  constructor() {
    this.name = 'mediapipe';
    this.landmarker = null;
    this.lastTs = 0;
  }

  async init() {
    const vision = await import('https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.14/vision_bundle.mjs');
    const fileset = await vision.FilesetResolver.forVisionTasks(
      'https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.14/wasm'
    );
    const make = (delegate) => vision.HandLandmarker.createFromOptions(fileset, {
      baseOptions: {
        modelAssetPath: 'https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task',
        delegate,
      },
      runningMode: 'VIDEO',
      numHands: 1,
      minHandDetectionConfidence: 0.4,
      minHandPresenceConfidence: 0.4,
    });
    try {
      this.landmarker = await make('GPU');
    } catch {
      this.landmarker = await make('CPU');
    }
  }

  // frame.canvas → MediaPipe 21 关键点（归一化 + visibility），无手返回 null
  getLandmarks(frame, ts) {
    if (!this.landmarker) return null;
    if (ts <= this.lastTs) ts = this.lastTs + 1; // detectForVideo 要求时间戳单调递增
    this.lastTs = ts;
    const res = this.landmarker.detectForVideo(frame.canvas, ts);
    const hand = res.landmarks && res.landmarks[0];
    if (!hand || hand.length < 21) return null;
    return hand.map((p) => ({ x: p.x, y: p.y, visibility: p.visibility ?? 1 }));
  }
}

// 演示合成手：指尖在 pointer {x,y}（归一化），手腕在其右下，食指伸直、其余手指弯曲。
// 生成后交给 evaluateGesture 判定 —— 不绕过规则，只替代关键点来源。
export class SyntheticHandSource {
  constructor() {
    this.name = 'synthetic';
    this.pointer = { x: 0.5, y: 0.45 };
    this.tick = 0;
  }

  setPointer(nx, ny) {
    this.pointer = { x: Math.min(0.97, Math.max(0.03, nx)), y: Math.min(0.97, Math.max(0.03, ny)) };
  }

  // 归一化坐标下构造：指尖在 pointer 处，手腕在其右下；腕→食指根→指尖共线，
  // 保证 FR-P03 的"手腕→食指根"射线延长后正好指向孩子指的目标。
  buildLandmarks() {
    const jitter = () => (Math.random() - 0.5) * 0.006;
    const tip = { x: this.pointer.x + jitter(), y: this.pointer.y + jitter() };
    // 指向单位向量：从手（右下）指向指尖（左上）
    const u = { x: -0.621, y: -0.781 };
    const perp = { x: -u.y, y: u.x }; // 垂直方向（用于手指横向展开）
    const P = (base, alongT, sideT) => ({
      x: base.x + u.x * alongT + perp.x * sideT + jitter(),
      y: base.y + u.y * alongT + perp.y * sideT + jitter(),
      visibility: 0.96,
    });

    const wrist = { x: tip.x - u.x * 0.42, y: tip.y - u.y * 0.42 };
    const lm = new Array(21);
    lm[0] = P(wrist, 0, 0); // 腕

    // 食指（伸直）：MCP/PIP/DIP/TIP 全部落在 腕→指尖 直线上
    lm[5] = P(wrist, 0.25, -0.010);
    lm[6] = P(wrist, 0.33, -0.012);
    lm[7] = P(wrist, 0.38, -0.013);
    lm[8] = P(tip, 0, -0.014);

    // 中/无名/小指（弯曲：PIP 微伸出，DIP/TIP 回勾向掌心）
    const curled = (mcpId, sideT, len) => {
      lm[mcpId] = P(wrist, 0.17, sideT);
      lm[mcpId + 1] = P(wrist, 0.17 + len * 0.45, sideT * 1.06);
      lm[mcpId + 2] = P(wrist, 0.17 + len * 0.32, sideT * 0.8);
      lm[mcpId + 3] = P(wrist, 0.17 + len * 0.12, sideT * 0.6);
    };
    curled(9, 0.012, 0.16);
    curled(13, 0.038, 0.15);
    curled(17, 0.064, 0.12);

    // 拇指（不参与判定）
    lm[1] = P(wrist, 0.06, -0.055);
    lm[2] = P(wrist, 0.13, -0.085);
    lm[3] = P(wrist, 0.19, -0.10);
    lm[4] = P(wrist, 0.24, -0.11);
    return lm;
  }

  getLandmarks() {
    this.tick++;
    return this.buildLandmarks();
  }
}

export async function createHandSource(preference) {
  if (preference === 'synthetic') return new SyntheticHandSource();
  if (preference === 'mediapipe' || preference === 'auto') {
    const mp = new MediaPipeHandSource();
    try {
      await mp.init();
      return mp;
    } catch (e) {
      console.warn('[handsource] MediaPipe 加载失败，降级为合成手：', e.message);
      if (preference === 'mediapipe') return null;
      return new SyntheticHandSource();
    }
  }
  return null;
}
