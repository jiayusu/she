// 指向会话主流程：FR-P01 触发采集 / FR-P04 确认话术 / FR-P05 全链路兜底 / FR-P06 窗口隐私 / FR-P07 分级
// 所有外部能力（摄像头、手势源、检测器、语音、API）均由 deps 注入 → 浏览器与单测共用同一套逻辑。
import { CONFIG } from './config.js';
import { selectCandidates, centerFallback } from './raycast.js';
import { evaluateGesture } from './gesture.js';

// FR-P07 手势置信度分级：5 帧中 ≥3 帧命中=轻确认；1-2 帧=重确认；0 帧=中心框兜底
export function gradeGestureFrames(hits, total = CONFIG.burst.frames) {
  if (hits >= 3) return { mode: 'light', source: 'ray', hits, total };
  if (hits >= 1) return { mode: 'heavy', source: 'ray', hits, total };
  return { mode: 'heavy', source: 'center', hits, total };
}

/**
 * FR-P04 确认话术状态机（≤2 轮，任何分支都有台词，不产生空响应）。
 * speech 适配器接口（由浏览器语音模块或测试脚本实现）：
 *   nameOf(box) → 展示名
 *   askYesNo(name, round) → Promise（说完"你是想问 X 吗"）
 *   askPair(a, b, round)  → Promise（说完"你是指 X 还是 Y"）
 *   getAnswer({names, timeoutMs}) → Promise<{kind:'affirm'|'deny'|'choice',name?}|{kind:'none'|'timeout'}>
 */
export class ConfirmFlow {
  constructor({ candidates, style, speech, maxRounds = CONFIG.confirm.maxRounds, onEvent = () => {} }) {
    this.candidates = candidates;
    this.style = style; // 'light' | 'heavy'
    this.speech = speech;
    this.maxRounds = maxRounds;
    this.onEvent = onEvent;
    this.corrections = 0;
    this.rounds = 0;
    this.autoPassed = false;
    this.lastAnswer = null;
  }

  async run() {
    const c = this.candidates;
    if (!c || c.length === 0) {
      return { type: 'exit', reason: 'no-candidate', meta: this._meta() };
    }
    if (this.style === 'heavy' && c.length >= 2) {
      const r = await this._pairFlow(c[0], c[1]);
      if (r) return r;
    } else {
      const r = await this._yesNoFlow();
      if (r) return r;
    }
    return { type: 'exit', reason: 'still-denied', meta: this._meta() };
  }

  // 轻/重确认共用的"是/不是"循环：肯定→选中；否定→第二候选再问；轮次耗尽→退出
  async _yesNoFlow() {
    let idx = 0;
    for (let round = 1; round <= this.maxRounds; round++) {
      const cand = this.candidates[idx];
      if (!cand) return null; // 没有更多候选 → 外层走优雅退出
      const name = this.speech.nameOf(cand);
      this.rounds = round;
      this.onEvent({ type: 'confirm-ask', round, name, style: this.style });
      await this.speech.askYesNo(name, round);

      // 轻确认第 1 轮：只等 2 秒，无否定即视为确认（快进路径）
      const timeoutMs =
        this.style === 'light' && round === 1 ? CONFIG.confirm.lightSilenceMs : CONFIG.confirm.heavyTimeoutMs;
      const ans = await this.speech.getAnswer({ names: [name], timeoutMs });
      this.lastAnswer = ans.kind;
      this.onEvent({ type: 'confirm-answer', round, answer: ans });

      if (ans.kind === 'affirm' || ans.kind === 'choice') {
        return { type: 'selected', box: ans.name ? this._byName(ans.name) || cand : cand, meta: this._meta() };
      }
      if (ans.kind === 'deny') {
        this.corrections++;
        idx++;
        continue;
      }
      // 超时/未识别：轻确认第 1 轮已视为确认；其余进入下一候选（换一个问，总轮次不变）
      if (this.style === 'light' && round === 1) {
        this.autoPassed = true;
        return { type: 'selected', box: cand, meta: this._meta() };
      }
      idx++;
    }
    return null;
  }

  // 重确认（1-2 帧命中）：双候选"你是指 A 还是 B？"；含糊/否定 → 重问一轮 → 仍不明 → 退出
  async _pairFlow(a, b) {
    const nameA = this.speech.nameOf(a);
    const nameB = this.speech.nameOf(b);
    for (let round = 1; round <= this.maxRounds; round++) {
      this.rounds = round;
      this.onEvent({ type: 'confirm-ask', round, pair: [nameA, nameB], style: 'pair' });
      await this.speech.askPair(nameA, nameB, round);
      const ans = await this.speech.getAnswer({ names: [nameA, nameB], timeoutMs: CONFIG.confirm.heavyTimeoutMs });
      this.lastAnswer = ans.kind;
      this.onEvent({ type: 'confirm-answer', round, answer: ans });
      if (ans.kind === 'choice') {
        const box = this._byName(ans.name);
        if (box) return { type: 'selected', box, meta: this._meta() };
        return { type: 'selected', box: a, meta: this._meta() };
      }
      if (ans.kind === 'affirm') continue; // "是"但没说哪个 → 再问一轮
      if (ans.kind === 'deny') {
        this.corrections++;
        continue; // 双候选已含第二候选，否定 → 重问一轮澄清
      }
    }
    return null;
  }

  _byName(name) {
    return this.candidates.find((c) => this.speech.nameOf(c) === name) || null;
  }

  _meta() {
    return {
      rounds: this.rounds, corrections: this.corrections, style: this.style,
      autoPassed: this.autoPassed, lastAnswer: this.lastAnswer,
    };
  }
}

/**
 * 指向会话编排。
 * deps:
 *   now()                                    毫秒时钟
 *   speak(text) → Promise                    念台词（TTS+UI，测试中收集）
 *   openCamera() → handle                    打开摄像头（失败抛错）
 *   captureBurst(handle, {count, intervalMs, deadline}) → {list:[{canvas,w,h}], captureStartDelayMs}
 *   closeCamera(handle)                      立即停流（FR-P06）
 *   handLandmarks(frame, ts) → landmarks|null  手势源（MediaPipe / 合成 / null）
 *   detectObjects(frame) → Promise<boxes>    检测器（YOLO/演示）
 *   cropFrame(frame, box) → dataURL|null     裁切所选框（隐私：仅裁切区域）
 *   apiSee(payload) → Promise<{text,source}> /api/see
 *   templateReply(box) → {text,source}       LLM 失败的本地模板（FR-P05）
 *   sendTelemetry(session)                   FR-P08 埋点
 *   confirmSpeech                            ConfirmFlow 适配器
 *   onEvent(evt)                             UI 事件流
 */
export class PointingPipeline {
  constructor(deps) {
    this.deps = deps;
    this.busy = false;
  }

  emit(evt) {
    try { this.deps.onEvent?.(evt); } catch { /* UI 事件不得影响主流程 */ }
  }

  async run(trigger = 'button') {
    if (this.busy) {
      this.emit({ type: 'busy' });
      return { status: 'busy' };
    }
    this.busy = true;
    const session = { ts: new Date().toISOString(), trigger, gestureHitFrames: 0, gestureTotalFrames: 0 };
    try {
      const outcome = await this._run(session);
      session.outcome = outcome;
      return { status: 'ok', outcome, session };
    } catch (err) {
      // FR-P05：任何异常也不允许空响应
      session.outcome = 'error';
      session.error = String(err && err.message || err);
      this.emit({ type: 'error', message: session.error });
      await this.deps.speak('哎呀，王冠走神了，我们再来一次吧！');
      return { status: 'error', session };
    } finally {
      this.busy = false;
      try { this.deps.sendTelemetry?.(session); } catch { /* 埋点失败不影响流程 */ }
      this.emit({ type: 'session-end', session });
    }
  }

  async _run(session) {
    const deps = this.deps;
    const t0 = deps.now();
    this.emit({ type: 'window-open' });

    // FR-P05：摄像头失败兜底
    let cam;
    try {
      cam = await deps.openCamera();
      this.emit({ type: 'camera-open' });
    } catch (err) {
      session.outcome = 'camera-fallback';
      this.emit({ type: 'camera-failed', message: String(err && err.message || err) });
      await deps.speak('我暂时找不到摄像头，先用听的方式陪我玩吧！');
      return 'camera-fallback';
    }

    // FR-P01 5 帧突发采集 + FR-P06 2 秒硬超时关流
    // 超时从"流真正打开"起算（慢设备打开耗时不应吃掉全部采集窗口），隐私上界不变：流生存 ≤2s
    const deadline = (cam && cam.startedAt ? cam.startedAt : t0) + CONFIG.window.timeoutMs;
    let burst;
    try {
      burst = await deps.captureBurst(cam, {
        count: CONFIG.burst.frames,
        intervalMs: CONFIG.burst.intervalMs,
        deadline,
      });
      session.triggerToCaptureMs = Math.round(burst.captureStartDelayMs);
      if (session.triggerToCaptureMs > CONFIG.burst.triggerWarnMs) {
        session.triggerToCaptureSlow = true;
      }
    } finally {
      // 无论成功失败，窗口结束立即停流（隐私验收：窗口外摄像头流必须 stop）
      try { deps.closeCamera(cam); } catch { /* 忽略 */ }
      this.emit({ type: 'camera-stopped', atMs: Math.round(deps.now() - t0) });
    }
    session.windowDurationMs = Math.round(deps.now() - t0);

    const frames = burst.list;
    if (!frames.length) {
      await deps.speak('我还没看清楚呢，再指一次好吗？');
      return 'no-frame';
    }

    // FR-P02：逐帧手势判定（事件驱动，仅这 5 帧，窗口外零计算）
    const ts = deps.now();
    const gestureResults = frames.map((f, i) => evaluateGesture(deps.handLandmarks(f, ts + i), f));
    const hits = gestureResults.filter((g) => g && g.isPointing);
    session.gestureHitFrames = hits.length;
    session.gestureTotalFrames = gestureResults.length;
    session.gestureRelaxed = hits.some((g) => g.relaxed);
    this.emit({ type: 'gesture', results: gestureResults, hits: hits.length });

    // 选最佳帧（手势置信度最高；无手势用中间帧）跑物体检测
    let bestIdx = 0;
    let bestScore = -1;
    gestureResults.forEach((g, i) => {
      const s = g ? g.confidence : -1;
      if (s > bestScore) { bestScore = s; bestIdx = i; }
    });
    if (bestScore < 0) bestIdx = Math.floor(frames.length / 2);
    const bestFrame = frames[bestIdx];
    this.emit({ type: 'frame', frame: bestFrame, index: bestIdx });

    // FR-P05：0 框 → "再对准一点"，最多重试 aimRetry 次（每次都是新的短窗口）
    let boxes = await deps.detectObjects(bestFrame);
    for (let i = 0; i < CONFIG.aimRetry && (!boxes || boxes.length === 0); i++) {
      this.emit({ type: 'aim-retry', attempt: i + 1 });
      await deps.speak('再对准一点，用小手指一指你想问的东西～');
      const cam2 = await deps.openCamera();
      let burst2;
      try {
        burst2 = await deps.captureBurst(cam2, {
          count: CONFIG.burst.frames,
          intervalMs: CONFIG.burst.intervalMs,
          deadline: deps.now() + CONFIG.window.timeoutMs,
        });
      } finally {
        try { deps.closeCamera(cam2); } catch { /* 忽略 */ }
        this.emit({ type: 'camera-stopped' });
      }
      if (!burst2.list.length) break;
      const g2 = burst2.list.map((f, j) => evaluateGesture(deps.handLandmarks(f, deps.now() + j), f));
      const h2 = g2.filter((g) => g && g.isPointing);
      if (h2.length > hits.length) {
        session.gestureHitFrames = h2.length;
        this.emit({ type: 'gesture', results: g2, hits: h2.length });
      }
      const bi = g2.reduce((acc, g, j) => ((g && g.confidence) > ((g2[acc] && g2[acc].confidence) || -1) ? j : acc), 0);
      boxes = await deps.detectObjects(burst2.list[bi]);
      if (boxes && boxes.length) { Object.assign(bestFrame, burst2.list[bi]); bestIdx = bi; }
    }
    if (!boxes || boxes.length === 0) {
      await deps.speak('王冠还没看清东西呢，我们等一下再试一次吧！');
      return 'no-object';
    }

    // FR-P03/FR-P07：按分级选候选
    const grade = gradeGestureFrames(hits.length);
    const dir = hits.length ? bestGestureDirection(hits) : null;
    const dims = { w: bestFrame.w, h: bestFrame.h };
    let candidates = [];
    let selectedBy = 'center';
    if (grade.source === 'ray' && dir) {
      const sel = selectCandidates(dir, boxes, dims);
      candidates = sel.ranked;
      selectedBy = sel.rayUsed ? 'ray' : 'tip-nearest';
    }
    if (!candidates.length) {
      candidates = centerFallback(boxes, dims);
      selectedBy = 'center';
    }
    session.selectedBy = selectedBy;
    session.candidates = candidates.map((b) => ({
      label: b.label, score: b.score, bbox: b.bbox,
    }));
    this.emit({ type: 'candidates', candidates, selectedBy, landmarks: bestGestureLandmarks(hits) });

    // FR-P04：确认话术（分级决定轻/重）
    const flow = new ConfirmFlow({
      candidates,
      style: grade.mode,
      speech: deps.confirmSpeech,
      onEvent: (e) => this.emit(e),
    });
    const result = await flow.run();
    Object.assign(session, result.meta && {
      confirmRounds: result.meta.rounds,
      corrections: result.meta.corrections,
      confirmStyle: result.meta.style,
      autoPassed: result.meta.autoPassed,
    });

    if (result.type === 'exit') {
      // PRD 关键流程：仍否定 → 优雅退出（有台词，非空响应）
      session.confirmResult = `exit:${result.meta.lastAnswer || result.reason}`;
      await deps.speak('那我们一起看看别的东西吧！');
      return 'exit';
    }

    const chosen = result.box;
    session.selectedIndex = candidates.indexOf(chosen);
    session.selectedLabel = chosen.label;
    session.selectedBox = chosen.bbox;
    session.confirmResult = result.meta.autoPassed ? 'timeout-auto' : 'affirm';
    this.emit({ type: 'selected', box: chosen });

    // 进视觉模块 /api/see 生成回应；失败 → 模板回应（FR-P05）
    let reply;
    const tSee = deps.now();
    try {
      const crop = deps.privacy?.uploadCrop ? deps.cropFrame?.(bestFrame, chosen) : null;
      reply = await deps.apiSee({
        image: crop || null,
        level: 'kid',
        bbox_hint: { x: chosen.bbox[0], y: chosen.bbox[1], w: chosen.bbox[2], h: chosen.bbox[3], label: chosen.label },
        session_id: session.ts,
      });
      session.apiSource = reply.source;
    } catch (err) {
      this.emit({ type: 'api-failed', message: String(err && err.message || err) });
      reply = deps.templateReply(chosen);
      session.apiSource = 'template-local';
    }
    session.seeLatencyMs = Math.round(deps.now() - tSee);
    await deps.speak(reply.text);
    return 'confirmed';
  }
}

function bestGestureDirection(hits) {
  const best = [...hits].sort((a, b) => b.confidence - a.confidence)[0];
  return best ? best.direction : null;
}

function bestGestureLandmarks(hits) {
  const best = [...hits].sort((a, b) => b.confidence - a.confidence)[0];
  return best ? best.landmarks : null;
}
