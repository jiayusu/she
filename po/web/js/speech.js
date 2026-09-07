// 浏览器语音：TTS（王冠说话）+ ASR（听孩子回答）+ FR-P04 确认话术适配器。
// ASR 不可用（iOS 旧版/无网络/未授权）时自动降级为按钮作答，任何路径都有回应。
import { parseAnswer, CONFIG } from './config.js';

export class Speech {
  constructor({ ui } = {}) {
    this.ui = ui;
    this.wakeListener = null;
  }

  get ttsAvailable() {
    return typeof window !== 'undefined' && 'speechSynthesis' in window;
  }

  pickVoice() {
    if (!this.ttsAvailable) return null;
    const voices = window.speechSynthesis.getVoices();
    return (
      voices.find((v) => /zh[-_]CN/i.test(v.lang) && /female|女|Xiaoxiao|Tingting/i.test(v.name)) ||
      voices.find((v) => /^zh/i.test(v.lang)) ||
      null
    );
  }

  // 念出台词并返回；同时把文本透出给 UI 气泡
  async speak(text) {
    this.ui?.onUtterance?.(text);
    if (!this.ttsAvailable) return text;
    return new Promise((resolve) => {
      try {
        window.speechSynthesis.cancel();
        const u = new SpeechSynthesisUtterance(text);
        u.lang = 'zh-CN';
        u.rate = 0.95;
        u.pitch = 1.1;
        const v = this.pickVoice();
        if (v) u.voice = v;
        let done = false;
        const finish = () => {
          if (!done) { done = true; resolve(text); }
        };
        u.onend = finish;
        u.onerror = finish;
        window.speechSynthesis.speak(u);
        // 合成器偶发不触发 onend，兜底定时
        setTimeout(finish, Math.max(3000, text.length * 260));
      } catch {
        resolve(text);
      }
    });
  }

  get asrAvailable() {
    return typeof window !== 'undefined' &&
      Boolean(window.SpeechRecognition || window.webkitSpeechRecognition);
  }

  // 听一句作答：ASR + 屏幕按钮 + 超时，三者谁先到用谁。
  // 返回 {kind:'affirm'|'deny'|'choice', name?} | {kind:'none'} | {kind:'timeout'}
  listenAnswer({ names = [], timeoutMs = CONFIG.confirm.heavyTimeoutMs } = {}) {
    return new Promise((resolve) => {
      let settled = false;
      const finish = (r) => {
        if (settled) return;
        settled = true;
        clearTimeout(timer);
        this._stopAsr();
        this.ui?.onAnswerDone?.();
        resolve(r);
      };
      const timer = setTimeout(() => finish({ kind: 'timeout' }), timeoutMs);

      // 按钮通道（永远可用，兜底）
      this.ui?.onAnswerStart?.({
        names,
        onPick: (kind, name) => finish(name ? { kind: 'choice', name } : { kind }),
      });

      // 语音通道
      if (this.asrAvailable) {
        try {
          const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
          const rec = new SR();
          this._rec = rec;
          rec.lang = 'zh-CN';
          rec.interimResults = true;
          rec.continuous = false;
          rec.maxAlternatives = 1;
          rec.onresult = (e) => {
            let text = '';
            for (let i = e.resultIndex; i < e.results.length; i++) {
              text += e.results[i][0].transcript;
            }
            this.ui?.onTranscript?.(text);
            if (!e.results[e.results.length - 1]?.isFinal) return;
            const parsed = parseAnswer(text, { names });
            if (parsed.kind === 'affirm' || parsed.kind === 'deny') finish(parsed);
            if (parsed.kind === 'choice') finish(parsed);
            // none：孩子说了别的，继续听到超时
          };
          rec.onerror = () => { /* 保留按钮/超时路径 */ };
          rec.onend = () => { /* 听完一轮即止，由 finish 负责收尾 */ };
          rec.start();
        } catch {
          this._rec = null;
        }
      }
    });
  }

  _stopAsr() {
    try { this._rec?.stop(); } catch { /* 忽略 */ }
    this._rec = null;
  }

  // 语音唤醒（FR-P01 "那是什么"）：仅在家长打开开关时运行，会话期间自动暂停
  async startWake(onWake) {
    if (!this.asrAvailable) return false;
    this.stopWake();
    let stopped = false;
    const rec = new (window.SpeechRecognition || window.webkitSpeechRecognition)();
    rec.lang = 'zh-CN';
    rec.continuous = true;
    rec.interimResults = false;
    rec.onresult = (e) => {
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const text = e.results[i][0].transcript || '';
        if (/那是什么|这是什么|那系什么|这系什么/.test(text)) {
          onWake();
          return;
        }
      }
    };
    rec.onerror = () => { /* 授权失败则按钮触发 */ };
    rec.onend = () => { if (!stopped) { try { rec.start(); } catch { /* 稍后重试 */ } } };
    try {
      rec.start();
      this.wakeListener = { rec, stop: () => { stopped = true; try { rec.stop(); } catch { /* 忽略 */ } } };
      return true;
    } catch {
      return false;
    }
  }

  stopWake() {
    this.wakeListener?.stop();
    this.wakeListener = null;
  }

  // FR-P04 确认话术适配器（供 PointingPipeline 使用）
  confirmAdapter() {
    return {
      nameOf: (box) => box.label || '这个东西',
      askYesNo: async (name, round) => {
        const text = round === 1 ? `你是想问${name}吗？` : `那${name}是不是你想问的呀？`;
        await this.speak(text);
      },
      askPair: async (a, b, round) => {
        const text = round === 1 ? `你是指${a}还是${b}呢？` : `再告诉我一次，是${a}还是${b}呀？`;
        await this.speak(text);
      },
      getAnswer: ({ names, timeoutMs }) => this.listenAnswer({ names, timeoutMs }),
    };
  }
}
