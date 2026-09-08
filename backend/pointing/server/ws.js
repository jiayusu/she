// 极简 RFC6455 WebSocket 服务端实现（零依赖）。
// 仅满足 FR-P10 需要的能力：/ws/crown 频道的连接、文本帧广播、ping/pong、close。
import crypto from 'node:crypto';
import { EventEmitter } from 'node:events';

const WS_GUID = '258EAFA5-E914-47DA-95CA-C5AB0DC85B11';
const MAX_FRAME = 1 << 20; // 1MB 上限，防异常帧

export function acceptKey(key) {
  return crypto.createHash('sha1').update(key + WS_GUID).digest('base64');
}

export function handshake(key) {
  return (
    'HTTP/1.1 101 Switching Protocols\r\n' +
    'Upgrade: websocket\r\n' +
    'Connection: Upgrade\r\n' +
    `Sec-WebSocket-Accept: ${acceptKey(key)}\r\n` +
    '\r\n'
  );
}

function encodeTextFrame(str) {
  const payload = Buffer.from(str, 'utf8');
  let header;
  if (payload.length < 126) {
    header = Buffer.from([0x81, payload.length]);
  } else if (payload.length < 65536) {
    header = Buffer.alloc(4);
    header[0] = 0x81;
    header[1] = 126;
    header.writeUInt16BE(payload.length, 2);
  } else {
    header = Buffer.alloc(10);
    header[0] = 0x81;
    header[1] = 127;
    header.writeBigUInt64BE(BigInt(payload.length), 2);
  }
  return Buffer.concat([header, payload]);
}

export class WsConnection extends EventEmitter {
  constructor(socket) {
    super();
    this.socket = socket;
    this.buf = Buffer.alloc(0);
    this.frag = null; // 分片累积
    this.closed = false;
    socket.on('data', (chunk) => this._onData(chunk));
    socket.on('close', () => this._finish());
    socket.on('error', () => this._finish());
    socket.setNoDelay(true);
  }

  _finish() {
    if (this.closed) return;
    this.closed = true;
    this.emit('close');
  }

  _onData(chunk) {
    this.buf = Buffer.concat([this.buf, chunk]);
    try {
      while (this._parseFrame()) { /* 逐帧解析 */ }
    } catch {
      this.close();
    }
    if (this.buf.length > MAX_FRAME) this.close();
  }

  _parseFrame() {
    const buf = this.buf;
    if (buf.length < 2) return false;
    const fin = (buf[0] & 0x80) !== 0;
    const opcode = buf[0] & 0x0f;
    const masked = (buf[1] & 0x80) !== 0;
    let len = buf[1] & 0x7f;
    let off = 2;
    if (len === 126) {
      if (buf.length < 4) return false;
      len = buf.readUInt16BE(2);
      off = 4;
    } else if (len === 127) {
      if (buf.length < 10) return false;
      len = Number(buf.readBigUInt64BE(2));
      off = 10;
    }
    if (len > MAX_FRAME) throw new Error('frame too large');
    const maskLen = masked ? 4 : 0;
    if (buf.length < off + maskLen + len) return false;
    let payload = buf.subarray(off + maskLen, off + maskLen + len);
    if (masked) {
      const mask = buf.subarray(off, off + 4);
      const un = Buffer.from(payload);
      for (let i = 0; i < un.length; i++) un[i] ^= mask[i % 4];
      payload = un;
    }
    this.buf = buf.subarray(off + maskLen + len);

    if (opcode === 0x8) { // close
      this._sendRaw(Buffer.from([0x88, 0x00]));
      this.socket.end();
      this._finish();
      return false;
    }
    if (opcode === 0x9) { // ping → pong
      this._sendRaw(Buffer.concat([Buffer.from([0x8a, payload.length]), payload]));
      return true;
    }
    if (opcode === 0xa) return true; // pong

    if (opcode === 0x1 || opcode === 0x2 || opcode === 0x0) {
      if (opcode === 0x0) {
        if (!this.frag) return true;
        this.frag.chunks.push(payload);
        if (fin) {
          const full = Buffer.concat(this.frag.chunks);
          this.frag = null;
          this.emit('message', full.toString('utf8'));
        }
      } else if (fin) {
        this.emit('message', payload.toString('utf8'));
      } else {
        this.frag = { chunks: [payload] };
      }
    }
    return true;
  }

  _sendRaw(buf) {
    if (this.closed || this.socket.destroyed) return;
    this.socket.write(buf);
  }

  send(text) {
    this._sendRaw(encodeTextFrame(String(text)));
  }

  close() {
    if (this.closed) return;
    this._sendRaw(Buffer.from([0x88, 0x00]));
    this.socket.end();
    this._finish();
  }
}
