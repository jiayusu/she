// FR-P08 埋点回流：每次指向记录 {手势帧数, 选中框, 确认结果, 纠正次数} → POST /admin/pointing-stats。
// 上报失败进队列，下次触发时重试（仅统计数据，不含任何图像）。
import { CONFIG } from './config.js';

const RETRY_KEY = 'pointing-stats-retry';

export class Telemetry {
  constructor() {
    this.queue = this._loadQueue();
  }

  _loadQueue() {
    try {
      return JSON.parse(localStorage.getItem(RETRY_KEY) || '[]');
    } catch {
      return [];
    }
  }

  _saveQueue() {
    try {
      localStorage.setItem(RETRY_KEY, JSON.stringify(this.queue.slice(-50)));
    } catch { /* 隐私模式等场景忽略 */ }
  }

  send(session) {
    const record = {
      ...session,
      ua: navigator.userAgent,
      landmarks: undefined,
    };
    this.queue.push(record);
    this._flush();
  }

  async _flush() {
    while (this.queue.length) {
      const rec = this.queue[0];
      try {
        const res = await fetch(CONFIG.api.statsPath, {
          method: 'POST',
          headers: { 'content-type': 'application/json' },
          body: JSON.stringify(rec),
          keepalive: true,
        });
        if (!res.ok) throw new Error(`http ${res.status}`);
        this.queue.shift();
        this._saveQueue();
      } catch {
        this._saveQueue(); // 服务端不在/断网：留待下次
        break;
      }
    }
  }
}
