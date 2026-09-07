// FR-P01 摄像头拉起 + 5 帧突发采集；FR-P06 窗口硬超时停流（事件驱动，窗口外零采集零计算）。
// 帧只进内存 canvas，不落盘。

export class CameraCapture {
  constructor({ ui } = {}) {
    this.ui = ui;
    this.stream = null;
  }

  async open() {
    if (!navigator.mediaDevices?.getUserMedia) {
      throw new Error('getUserMedia unsupported');
    }
    // 后摄取景（拍物件），失败回退前摄
    let stream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: 'environment', width: { ideal: 640 }, height: { ideal: 480 } },
        audio: false,
      });
    } catch {
      stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
    }
    this.stream = stream;
    this.ui?.onCameraState?.(true);
    return { stream, startedAt: performance.now() };
  }

  /**
   * 5 帧突发采集。deadline 为绝对时刻（performance.now() 基准），到点强制返回已采到的帧。
   * @returns {{list:Array<{canvas,w,h}>, captureStartDelayMs:number}}
   */
  async captureBurst(cam, { count = 5, intervalMs = 70, deadline = Infinity } = {}) {
    const video = document.createElement('video');
    video.srcObject = cam.stream;
    video.muted = true;
    video.playsInline = true;
    await video.play();
    await this._waitReady(video);

    const list = [];
    const t0 = performance.now();
    const captureStartDelayMs = t0 - cam.startedAt;
    for (let i = 0; i < count && performance.now() < deadline; i++) {
      const canvas = document.createElement('canvas');
      canvas.width = video.videoWidth || 640;
      canvas.height = video.videoHeight || 480;
      const ctx = canvas.getContext('2d', { willReadFrequently: true });
      ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
      list.push({ canvas, w: canvas.width, h: canvas.height, capturedAt: performance.now() - t0 });
      if (i < count - 1) {
        const remain = deadline - performance.now();
        if (remain <= 0) break;
        await new Promise((r) => setTimeout(r, Math.min(intervalMs, remain)));
      }
    }
    video.srcObject = null;
    return { list, captureStartDelayMs };
  }

  _waitReady(video) {
    if (video.readyState >= 2 && video.videoWidth > 0) return Promise.resolve();
    return new Promise((resolve, reject) => {
      const t = setTimeout(() => reject(new Error('video not ready')), 1500);
      video.onloadeddata = () => {
        clearTimeout(t);
        resolve();
      };
      video.onerror = () => {
        clearTimeout(t);
        reject(new Error('video error'));
      };
    });
  }

  // FR-P06：立即 stop 所有轨道（隐私验收：窗口外摄像头流必须 stop）
  close() {
    if (this.stream) {
      for (const track of this.stream.getTracks()) track.stop();
      this.stream = null;
    }
    this.ui?.onCameraState?.(false);
  }

  // 把所选框从帧里裁出（隐私：仅上传裁切区域，且可在设置里关闭）
  cropFrame(frame, box, { maxSize = 512, margin = 0.15, quality = 0.7 } = {}) {
    const [bx, by, bw, bh] = box.bbox || box;
    const mx = bw * margin;
    const my = bh * margin;
    const cx = Math.max(0, bx - mx);
    const cy = Math.max(0, by - my);
    const cw = Math.min(frame.w - cx, bw + mx * 2);
    const ch = Math.min(frame.h - cy, bh + my * 2);
    const scale = Math.min(1, maxSize / Math.max(cw, ch));
    const out = document.createElement('canvas');
    out.width = Math.max(1, Math.round(cw * scale));
    out.height = Math.max(1, Math.round(ch * scale));
    out.getContext('2d').drawImage(frame.canvas, cx, cy, cw, ch, 0, 0, out.width, out.height);
    return out.toDataURL('image/jpeg', quality);
  }
}
