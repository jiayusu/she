// 全局配置：所有阈值集中于此，便于自采儿童数据后校正（PRD §8 风险对策）
export const CONFIG = {
  // FR-P01：5 帧突发采集；触发→开始采帧 ≤1s
  burst: {
    frames: 5,
    intervalMs: 70,
    triggerWarnMs: 1000,   // 超过此值记入埋点（验收 ≤1s）
  },
  // FR-P06：指向窗口 2s 超时自动关摄像头（事件驱动，非持续采集）
  window: {
    timeoutMs: 2000,
  },
  // FR-P02：手势判定阈值（角度制，尺度不变，只依赖向量夹角）
  gesture: {
    extendedAngle: 140,    // 手指伸直：PIP 关节夹角 ≥140°
    extendedRatio: 1.3,    // 伸直手指指尖离腕比例下限（指尖距/掌根距）
    curledAngle: 110,      // 手指弯曲：PIP 夹角 ≤110°
    curledRatio: 1.15,     // 弯曲指尖回勾比例上限
    wristMinVis: 0.5,      // 手腕可见（MediaPipe visibility）
    mcpMinVis: 0.4,
    minHandSpan: 0.05,     // 最小手部跨度（防噪声小框），相对画面对角线
    allowRelaxed: true,    // 放宽一档：食指+中指并伸也算指向（PRD §8）
    strictThumb: false,    // 不约束拇指（儿童指认拇指常翘起，放宽提高召回）
  },
  // FR-P04 / FR-P07：确认话术
  confirm: {
    lightSilenceMs: 2000,  // 轻确认：2 秒无否定视为确认（快进路径，PRD §8）
    heavyTimeoutMs: 6000,  // 重确认每轮等待
    maxRounds: 2,          // 确认轮次 ≤2
  },
  // FR-P03：射线
  ray: {
    forwardOnly: true,     // 只取手腕前方交点（t>0）
  },
  // 物体检测
  detect: {
    scoreThresh: 0.35,
    iouThresh: 0.45,
    maxBoxes: 5,
    inputSize: 640,        // YOLOv8 letterbox 输入
  },
  // FR-P05：0 框兜底重试次数
  aimRetry: 2,
  // 隐私（PRD §5）：帧只在内存，不落盘不上传原图；仅上传所选裁切区域且可关
  privacy: {
    uploadCrop: true,
    cropMaxSize: 512,
    cropMargin: 0.15,
    cropQuality: 0.7,
  },
  api: {
    seePath: '/api/see',
    statsPath: '/admin/pointing-stats',
    crownPressPath: '/crown/press',
    crownWsPath: '/ws/crown',
    seeTimeoutMs: 6000,
  },
};

// FR-P04：孩子任意中文肯定/否定表达都能识别（词表可继续扩充）
export const AFFIRM_WORDS = [
  '是', '是的', '是呀', '是啊', '是啦', '是滴', '是的是的', '是了',
  '对', '对的', '对呀', '对啊', '对啦', '对对', '对的对的', '答对了', '没错', '不错',
  '嗯', '嗯嗯', '嗯呐', '嗯对', '嗯好',
  '好', '好的', '好呀', '好啊', '好耶', '好啦',
  '想', '我想', '想知道', '我想知道', '就是它', '就是这个', '就是那个',
  '点点头', 'yes', 'yeah', 'yep', 'ok', 'okay',
];

export const DENY_WORDS = [
  '不是', '不是的', '不是呀', '不是啦', '不是这个', '不是它', '不是那个',
  '不对', '不对不对', '错了', '错了呀', '不对哦',
  '没有', '没', '不', '不不', '别', '不想要', '不想', '不想知道', '换一个', '换换',
  'no', 'nope',
];

// 肯定/否定解析：所有词一起做"最长匹配优先"（"没错"必须先于"错"、"不是"先于"是"），
// 同长时否定优先。命中否定 → deny；否则说出候选名 → choice；再否则命中肯定 → affirm。
export function parseAnswer(rawText, { names = [] } = {}) {
  const text = normalizeAnswer(rawText);
  if (!text) return { kind: 'none' };

  const tokens = [
    ...DENY_WORDS.map((w) => ({ w, kind: 'deny' })),
    ...AFFIRM_WORDS.map((w) => ({ w, kind: 'affirm' })),
  ].sort((a, b) => b.w.length - a.w.length); // 稳定排序：同长保持否定在前

  let affirmToken = null;
  for (const { w, kind } of tokens) {
    if (!text.includes(w)) continue;
    if (kind === 'deny') return { kind: 'deny', token: w };
    if (!affirmToken) affirmToken = w; // 最长肯定词
    break;
  }

  for (const name of names) {
    if (name && text.includes(stripName(name))) return { kind: 'choice', name };
  }
  if (affirmToken) return { kind: 'affirm', token: affirmToken };
  return { kind: 'none' };
}

function normalizeAnswer(text) {
  return String(text || '')
    .toLowerCase()
    .replace(/[\s,，。.！!？?？、~～·…—\-']/g, '')
    .trim();
}

function stripName(name) {
  // 候选名如"红色的东西"匹配核心词即可
  return String(name || '').replace(/东西|那个|这个/g, '');
}
