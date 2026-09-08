// 主装配：把摄像头采集 / 手势源 / 检测器 / 语音 / 遥测 / 小智联动接到 PointingPipeline。
import { CONFIG } from './config.js';
import { PointingPipeline } from './pipeline.js';
import { CameraCapture } from './capture.js';
import { createHandSource } from './handsource.js';
import { createDetector } from './detector.js';
import { Speech } from './speech.js';
import { Telemetry } from './telemetry.js';
import { CrownLink } from './crown-ws.js';
import { DemoScene } from './scene.js';
import { templateReply } from './replies.js';

const $ = (id) => document.getElementById(id);
const els = {
  stage: $('stage'), video: $('video'), scene: $('scene-canvas'), overlay: $('overlay'),
  freeze: $('freeze'), status: $('status-text'), timing: $('timing'), bubble: $('bubble'),
  trigger: $('btn-trigger'), wake: $('chk-wake'), camDot: $('cam-dot'), wsDot: $('ws-dot'),
  debug: $('debug'),
  confirmCard: $('confirm-card'), confirmRound: $('confirm-round'),
  confirmTranscript: $('confirm-transcript'), confirmButtons: $('confirm-buttons'),
  selSource: $('sel-source'), selHand: $('sel-hand'), selDetector: $('sel-detector'),
  chkUpload: $('chk-upload'), chkMirror: $('chk-mirror'), chkDebug: $('chk-debug'),
};

const settings = {
  source: localStorage.getItem('p.source') || 'demo',
  hand: localStorage.getItem('p.hand') || 'auto',
  detector: localStorage.getItem('p.detector') || 'auto',
  uploadCrop: localStorage.getItem('p.uploadCrop') !== '0',
  mirror: localStorage.getItem('p.mirror') !== '0',
};
els.selSource.value = settings.source;
els.selHand.value = settings.hand;
els.selDetector.value = settings.detector;
els.chkUpload.checked = settings.uploadCrop;
els.chkMirror.checked = settings.mirror;

// ---------- UI 适配 ----------
const ui = {
  onCameraState(on) {
    els.camDot.textContent = on ? '摄像头工作中' : '摄像头已关闭';
    els.camDot.className = `dot ${on ? 'on live' : 'ok'}`;
  },
  onUtterance(text) {
    els.bubble.hidden = false;
    els.bubble.textContent = text;
  },
  onAnswerStart({ names, onPick }) {
    els.confirmCard.hidden = false;
    els.confirmTranscript.textContent = '（可语音回答，或点按钮）';
    els.confirmButtons.innerHTML = '';
    const mk = (label, cls, fn) => {
      const b = document.createElement('button');
      b.textContent = label;
      b.className = cls;
      b.onclick = () => fn();
      els.confirmButtons.appendChild(b);
    };
    if (names.length >= 2) {
      for (const n of names) mk(`是「${n}」`, 'opt', () => onPick('choice', n));
      mk('都不是', 'no', () => onPick('deny'));
    } else {
      mk('是 / 对', 'yes', () => onPick('affirm'));
      mk('不是', 'no', () => onPick('deny'));
    }
  },
  onTranscript(text) {
    els.confirmTranscript.textContent = `听到：${text}`;
  },
  onAnswerDone() {
    for (const b of els.confirmButtons.querySelectorAll('button')) b.disabled = true;
  },
  hideConfirm() {
    els.confirmCard.hidden = true;
  },
};

const speech = new Speech({ ui });
const telemetry = new Telemetry();
const camera = new CameraCapture({ ui });
const scene = new DemoScene(els.scene);
let handSource = null;
let detector = null;
let lastFrame = null;

// ---------- 资源加载（页面空闲时预热推理资源，不开启摄像头、不采集） ----------
async function loadProviders() {
  setStatus('正在加载手势/检测模型…');

  // ==============================
  // 手势源
  // ==============================
  try {
    if (settings.source === 'demo') {
      handSource =
        settings.hand === 'mediapipe'
          ? await createHandSource('mediapipe')
          : scene.hand;
    } else {
      // 真实摄像头模式：
      // auto 必须等价于 mediapipe
      // 禁止降级到 synthetic，否则“假手”与真人完全无关
      const handPref =
        settings.hand === 'synthetic'
          ? 'synthetic'
          : 'mediapipe';

      handSource =
        await createHandSource(handPref);

      if (!handSource) {
        throw new Error('MediaPipe Hands 初始化失败');
      }

      if (handSource.name === 'synthetic') {
        throw new Error(
          '真实摄像头模式禁止使用 SyntheticHandSource'
        );
      }
    }
  } catch (e) {
    console.error(
      '[hand] 真实手势初始化失败：',
      e
    );

    handSource = null;
  }

  // ==============================
  // 物体检测
  // ==============================
  try {
    detector =
      settings.source === 'demo'
        ? await createDetector(
            'static',
            scene
          )
        : await createDetector(
            settings.detector,
            null
          );
  } catch (e) {
    console.error(
      '[detector] 初始化失败：',
      e
    );

    detector = null;
  }

  const detName =
    detector
      ? detector.name === 'yolo'
        ? 'YOLOv8n'
        : detector.name === 'static'
          ? '场景内置'
          : detector.name
      : '无';

  const handName =
    handSource
      ? handSource.name === 'mediapipe'
        ? 'MediaPipe真实手'
        : handSource.name
      : '无';

  setStatus(
    `就绪：手势源=${handName}，检测器=${detName}`
  );
}

// ---------- 演示场景指针 ----------
for (const evt of ['pointermove', 'pointerdown']) {
  els.stage.addEventListener(evt, (e) => {
    if (settings.source !== 'demo') return;
    const rect = els.scene.getBoundingClientRect();
    scene.setPointerFromEvent(e.clientX, e.clientY, rect);
    scene.draw({ x: (e.clientX - rect.left) / rect.width * scene.canvas.width, y: (e.clientY - rect.top) / rect.height * scene.canvas.height });
  });
}

// ---------- Pipeline 依赖 ----------
const deps = {
  now: () => performance.now(),
  speak: (text) => speech.speak(text),
  privacy: { get uploadCrop() { return settings.uploadCrop; } },

  async openCamera() {
    if (settings.source === 'demo') {
      return { demo: true, startedAt: performance.now() };
    }
    return camera.open();
  },

  async captureBurst(cam, { count, intervalMs, deadline }) {
    if (cam.demo) {
      // 演示模式：从场景 canvas 取帧（合成手关键点在 handLandmarks 步骤生成）
      const list = [];
      const t0 = performance.now();
      for (let i = 0; i < count && performance.now() < deadline; i++) {
        const canvas = document.createElement('canvas');
        canvas.width = scene.canvas.width;
        canvas.height = scene.canvas.height;
        canvas.getContext('2d').drawImage(scene.canvas, 0, 0);
        list.push({ canvas, w: canvas.width, h: canvas.height });
        if (i < count - 1) {
          const remain = deadline - performance.now();
          if (remain <= 0) break;
          await new Promise((r) => setTimeout(r, Math.min(intervalMs, remain)));
        }
      }
      return { list, captureStartDelayMs: performance.now() - cam.startedAt };
    }
    const burst = await camera.captureBurst(cam, { count, intervalMs, deadline });
    // 视频首帧展示（镜像交给 CSS）
    els.video.srcObject = cam.stream;
    return burst;
  },

  closeCamera(cam) {
    if (cam.demo) return;
    els.video.srcObject = null;
    camera.close();
  },

  handLandmarks(frame, ts) {
    if (settings.source === 'demo') return scene.getLandmarks();
    return handSource ? handSource.getLandmarks(frame, ts) : null;
  },

  async detectObjects(frame) {
    if (!detector) return [];
    try {
      return await detector.detect(frame);
    } catch (e) {
      console.warn('[detector] 失败，按 0 框兜底：', e);
      return [];
    }
  },

  cropFrame(frame, box) {
    if (settings.source === 'demo') return null; // 演示场景不上传图像
    return camera.cropFrame(frame, box, CONFIG.privacy);
  },

  async apiSee(payload) {
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), CONFIG.api.seeTimeoutMs);
    try {
      const res = await fetch(CONFIG.api.seePath, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify(payload),
        signal: ctrl.signal,
      });
      if (!res.ok) throw new Error(`api see http ${res.status}`);
      const data = await res.json();
      if (!data.ok || !data.text) throw new Error('api see empty');
      return { text: data.text, source: data.source };
    } finally {
      clearTimeout(timer);
    }
  },

  templateReply(box) {
    return templateReply({ label: box.label });
  },

  sendTelemetry(session) {
    telemetry.send(session);
  },

  confirmSpeech: speech.confirmAdapter(),

  onEvent(evt) {
    handleEvent(evt);
  },
};

const pipeline = new PointingPipeline(deps);

// ---------- 事件 → UI ----------
function setStatus(text) {
  els.status.textContent = text;
}

function handleEvent(evt) {
  switch (evt.type) {
    case 'window-open':
      ui.hideConfirm();
      els.freeze.hidden = true;
      setStatus(settings.source === 'demo' ? '演示采集中…' : '正在看，把小手指过去…');
      els.trigger.disabled = true;
      break;
    case 'camera-stopped':
      ui.onCameraState(false);
      if (settings.source !== 'demo') setStatus('摄像头已关闭 ✓ 分析刚拍到的画面…');
      break;
    case 'camera-failed':
      setStatus('摄像头不可用，可切换到“演示场景”');
      break;
    case 'gesture':
      setStatus(`手势命中 ${evt.hits}/${evt.results.length} 帧`);
      break;
    case 'frame':
      showFreeze(evt.frame);
      break;
    case 'candidates':
      drawOverlay(evt.landmarks, evt.candidates, 0);
      break;
    case 'confirm-ask':
      els.confirmRound.textContent = `（第 ${evt.round} 轮）`;
      if (evt.name) setStatus(`确认：你是想问「${evt.name}」吗？`);
      if (evt.pair) setStatus(`确认：${evt.pair[0]} 还是 ${evt.pair[1]}？`);
      break;
    case 'confirm-answer':
      ui.hideConfirm();
      break;
    case 'selected':
      setStatus(`已选「${evt.box.label}」，请王冠回答…`);
      break;
    case 'aim-retry':
      setStatus('没看清物件，请再对准一点');
      break;
    case 'api-failed':
      setStatus('网络不佳，用本地小故事回答');
      break;
    case 'session-end':
      els.trigger.disabled = false;
      lastFrame = null;
      setStatus(`本轮结束（${evt.session.outcome ?? '完成'}），再指一次吧`);
      wakeResume();
      break;
    default:
      break;
  }
  debugLog(evt);
}

function showFreeze(frame) {
  if (!frame) return;
  els.freeze.width = frame.canvas.width;
  els.freeze.height = frame.canvas.height;
  els.freeze.getContext('2d').drawImage(frame.canvas, 0, 0);
  els.freeze.hidden = false;
  lastFrame = frame;
}

// ---------- 叠加层绘制（射线 + 框 + 指尖） ----------
function drawOverlay(landmarks, boxes, primaryIdx) {
  const canvas = els.overlay;
  const rect = els.stage.getBoundingClientRect();
  const dpr = window.devicePixelRatio || 1;
  canvas.width = Math.round(rect.width * dpr);
  canvas.height = Math.round(rect.height * dpr);
  const ctx = canvas.getContext('2d');
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  const W = rect.width;
  const H = rect.height;
  ctx.clearRect(0, 0, W, H);

  const frameW = lastFrame ? lastFrame.w : 640;
  const frameH = lastFrame ? lastFrame.h : 480;
  const sx = W / frameW;
  const sy = H / frameH;

  // 检出框
  (boxes || []).forEach((b, i) => {
    const [x, y, w, h] = b.bbox;
    const primary = i === primaryIdx;
    ctx.lineWidth = primary ? 4 : 2.5;
    ctx.strokeStyle = primary ? '#ff6f61' : 'rgba(67,181,129,0.9)';
    ctx.strokeRect(x * sx, y * sy, w * sx, h * sy);
    ctx.font = `${primary ? 15 : 12}px sans-serif`;
    const label = `${b.label} ${(b.score ?? 0).toFixed(2)}`;
    const tw = ctx.measureText(label).width + 10;
    ctx.fillStyle = primary ? 'rgba(255,111,97,0.95)' : 'rgba(67,181,129,0.85)';
    ctx.fillRect(x * sx, y * sy - 18, tw, 18);
    ctx.fillStyle = '#fff';
    ctx.fillText(label, x * sx + 5, y * sy - 4);
  });

  // 手腕→食指根 射线
  if (landmarks) {
    const wrist = landmarks[0];
    const mcp = landmarks[5];
    const tip = landmarks[8];
    const x1 = wrist.x * frameW * sx;
    const y1 = wrist.y * frameH * sy;
    const x2 = mcp.x * frameW * sx;
    const y2 = mcp.y * frameH * sy;
    const dx = x2 - x1;
    const dy = y2 - y1;
    const len = Math.hypot(dx, dy) || 1;
    const ext = Math.max(W, H) * 1.2 / len;
    ctx.strokeStyle = 'rgba(255,180,71,0.95)';
    ctx.lineWidth = 3;
    ctx.setLineDash([10, 8]);
    ctx.beginPath();
    ctx.moveTo(x1, y1);
    ctx.lineTo(x1 + dx * ext, y1 + dy * ext);
    ctx.stroke();
    ctx.setLineDash([]);
    // 关键点
    const dot = (px, py, color, r = 6) => {
      ctx.fillStyle = color;
      ctx.beginPath();
      ctx.arc(px, py, r, 0, Math.PI * 2);
      ctx.fill();
    };
    dot(x1, y1, '#ffb347');          // 腕
    dot(x2, y2, '#ff8a3d');          // 食指根
    dot(tip.x * frameW * sx, tip.y * frameH * sy, '#ff6f61', 8); // 指尖
  }
}

function clearOverlay() {
  const canvas = els.overlay;
  canvas.getContext('2d').clearRect(0, 0, canvas.width, canvas.height);
}

// ---------- 调试面板 ----------
let debugLines = [];
function debugLog(evt) {
  if (!els.chkDebug.checked) return;
  const safe = { ...evt };
  if (safe.frame) safe.frame = `[canvas ${safe.frame.w}x${safe.frame.h}]`;
  if (safe.landmarks) safe.landmarks = '[21 landmarks]';
  if (safe.results) safe.results = `[${safe.results.length} frames]`;
  if (safe.session) safe.session = { outcome: safe.session.outcome };
  debugLines.push(JSON.stringify(safe, (k, v) => (v instanceof HTMLCanvasElement ? '[canvas]' : v)));
  if (debugLines.length > 40) debugLines = debugLines.slice(-40);
  els.debug.textContent = debugLines.join('\n');
}
els.chkDebug.onchange = () => {
  els.debug.hidden = !els.chkDebug.checked;
  if (!els.chkDebug.checked) debugLines = [];
};

// ---------- 触发（FR-P01） ----------
async function trigger(source) {
  // 会话期间暂停语音唤醒，避免和确认 ASR 抢麦克风
  if (els.wake.checked) speech.stopWake();
  const r = await pipeline.run(source);
  if (r.status === 'busy') setStatus('上一轮还没结束，稍等一下哦');
  return r;
}
els.trigger.onclick = () => trigger('button');

// 语音唤醒（FR-P01 "那是什么"）
els.wake.onchange = async () => {
  if (els.wake.checked) {
    const ok = await speech.startWake(() => trigger('voice'));
    if (!ok) {
      setStatus('此浏览器不支持语音唤醒，改用按钮触发');
      els.wake.checked = false;
    }
  } else {
    speech.stopWake();
  }
};
function wakeResume() {
  if (els.wake.checked) speech.startWake(() => trigger('voice'));
}

// ---------- 小智联动（FR-P10） ----------
const crown = new CrownLink({
  onPleasePhoto: () => {
    els.wsDot.textContent = '收到设备指令';
    trigger('crown');
  },
  onStatus: (s) => {
    els.wsDot.textContent = s === 'connected' ? '小智已连接' : '小智未连接';
    els.wsDot.className = `dot ${s === 'connected' ? 'ws-on' : 'off'}`;
  },
});
crown.connect();

// ---------- 设置联动 ----------
function saveSettings() {
  localStorage.setItem('p.source', settings.source);
  localStorage.setItem('p.hand', settings.hand);
  localStorage.setItem('p.detector', settings.detector);
  localStorage.setItem('p.uploadCrop', settings.uploadCrop ? '1' : '0');
  localStorage.setItem('p.mirror', settings.mirror ? '1' : '0');
}

function applySource() {
  const demo = settings.source === 'demo';
  els.scene.hidden = !demo;
  els.video.hidden = demo;
  els.stage.classList.toggle('mirror', !demo && settings.mirror);
  scene.draw();
  clearOverlay();
  els.freeze.hidden = true;
  loadProviders();
}

els.selSource.onchange = () => {
  settings.source = els.selSource.value;
  saveSettings();
  applySource();
};
els.selHand.onchange = () => {
  settings.hand = els.selHand.value;
  saveSettings();
  loadProviders();
};
els.selDetector.onchange = () => {
  settings.detector = els.selDetector.value;
  saveSettings();
  loadProviders();
};
els.chkUpload.onchange = () => {
  settings.uploadCrop = els.chkUpload.checked;
  saveSettings();
};
els.chkMirror.onchange = () => {
  settings.mirror = els.chkMirror.checked;
  els.stage.classList.toggle('mirror', settings.source !== 'demo' && settings.mirror);
  saveSettings();
};

// 页面隐藏立即停流（隐私兜底）
document.addEventListener('visibilitychange', () => {
  if (document.hidden) camera.close();
});
window.addEventListener('beforeunload', () => camera.close());

// ---------- 启动 ----------
applySource();
// 有真实摄像头权限意愿时仍默认演示场景；媒体管道在后台预载（不采集）
loadProviders();
