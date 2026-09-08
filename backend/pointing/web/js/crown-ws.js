// FR-P10 小智联动：浏览器连 /ws/crown 监听"请拍照"指令；断线自动重连。
import { CONFIG } from './config.js';

export class CrownLink {
  constructor({ onPleasePhoto, onStatus } = {}) {
    this.onPleasePhoto = onPleasePhoto;
    this.onStatus = onStatus;
    this.retry = 0;
    this.closedByUser = false;
  }

  connect() {
    if (this.closedByUser) return;
    const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
    const url = `${proto}//${location.host}${CONFIG.api.crownWsPath}`;
    let ws;
    try {
      ws = new WebSocket(url);
    } catch {
      this._scheduleReconnect();
      return;
    }
    this.ws = ws;
    ws.onopen = () => {
      this.retry = 0;
      this.onStatus?.('connected');
    };
    ws.onmessage = (e) => {
      try {
        const msg = JSON.parse(e.data);
        if (msg.type === 'please_photo') this.onPleasePhoto?.(msg);
      } catch { /* 忽略非 JSON */ }
    };
    ws.onclose = () => {
      this.onStatus?.('disconnected');
      this._scheduleReconnect();
    };
    ws.onerror = () => {
      try { ws.close(); } catch { /* 忽略 */ }
    };
  }

  _scheduleReconnect() {
    if (this.closedByUser) return;
    const delay = Math.min(10000, 1000 * 2 ** this.retry++);
    setTimeout(() => this.connect(), delay);
  }

  close() {
    this.closedByUser = true;
    try { this.ws?.close(); } catch { /* 忽略 */ }
  }
}
