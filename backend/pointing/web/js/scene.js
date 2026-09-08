// 演示场景：无摄像头时在 canvas 上画一组玩具（红球/黄杯/绿树/蓝车/紫熊），
// 指针位置驱动合成手指尖 —— 全链路（采集→手势→检测→射线→确认）无需摄像头即可运行。
import { SyntheticHandSource } from './handsource.js';

export const SCENE_W = 640;
export const SCENE_H = 480;

export class DemoScene {
  constructor(hostCanvas = null) {
    // 复用页面上的 canvas（演示模式下直接展示），否则自建离屏画布
    this.canvas = hostCanvas || document.createElement('canvas');
    this.canvas.width = SCENE_W;
    this.canvas.height = SCENE_H;
    this.hand = new SyntheticHandSource();
    this.objects = [
      { label: '红色的球', color: '#e74c3c', shape: 'ball', bbox: [70, 300, 120, 120] },
      { label: '黄色的杯子', color: '#f4b400', shape: 'cup', bbox: [250, 290, 90, 130] },
      { label: '绿色的小树', color: '#2ecc71', shape: 'tree', bbox: [400, 210, 130, 210] },
      { label: '蓝色的小汽车', color: '#3498db', shape: 'car', bbox: [80, 90, 170, 110] },
      { label: '紫色的小熊', color: '#9b59b6', shape: 'bear', bbox: [470, 60, 120, 130] },
    ];
    this.draw();
  }

  // 指针（canvas 坐标）→ 归一化 → 合成手
  setPointerFromEvent(clientX, clientY, hostRect) {
    const nx = (clientX - hostRect.left) / hostRect.width;
    const ny = (clientY - hostRect.top) / hostRect.height;
    this.hand.setPointer(nx, ny);
  }

  getLandmarks() {
    return this.hand.getLandmarks();
  }

  draw(pointer = null) {
    const ctx = this.canvas.getContext('2d');
    // 背景墙 + 地板
    ctx.fillStyle = '#f6efe3';
    ctx.fillRect(0, 0, SCENE_W, SCENE_H);
    ctx.fillStyle = '#ead9bd';
    ctx.fillRect(0, 360, SCENE_W, 120);
    ctx.strokeStyle = '#d9c19a';
    ctx.lineWidth = 3;
    ctx.beginPath();
    ctx.moveTo(0, 360);
    ctx.lineTo(SCENE_W, 360);
    ctx.stroke();

    // 地板条纹
    ctx.strokeStyle = '#e2cfae';
    ctx.lineWidth = 2;
    for (let i = 1; i < 5; i++) {
      ctx.beginPath();
      ctx.moveTo(0, 360 + i * 24);
      ctx.lineTo(SCENE_W, 360 + i * 24);
      ctx.stroke();
    }

    for (const o of this.objects) {
      ctx.fillStyle = o.color;
      ctx.strokeStyle = 'rgba(0,0,0,0.15)';
      ctx.lineWidth = 3;
      const [x, y, w, h] = o.bbox;
      if (o.shape === 'ball') {
        ctx.beginPath();
        ctx.arc(x + w / 2, y + h / 2, w / 2, 0, Math.PI * 2);
        ctx.fill();
        ctx.stroke();
      } else if (o.shape === 'cup') {
        ctx.beginPath();
        ctx.roundRect(x, y, w, h, [6, 6, 22, 22]);
        ctx.fill();
        ctx.stroke();
        ctx.beginPath();
        ctx.arc(x + w + 14, y + h / 3, 20, -Math.PI / 2, Math.PI / 2);
        ctx.lineWidth = 10;
        ctx.strokeStyle = o.color;
        ctx.stroke();
      } else if (o.shape === 'tree') {
        ctx.beginPath();
        ctx.arc(x + w / 2, y + h * 0.32, w / 2, 0, Math.PI * 2);
        ctx.fill();
        ctx.stroke();
        ctx.beginPath();
        ctx.arc(x + w * 0.28, y + h * 0.52, w * 0.36, 0, Math.PI * 2);
        ctx.fill();
        ctx.stroke();
        ctx.fillStyle = '#8b5a2b';
        ctx.fillRect(x + w / 2 - 10, y + h * 0.62, 20, h * 0.38);
      } else if (o.shape === 'car') {
        ctx.beginPath();
        ctx.roundRect(x, y + h * 0.35, w, h * 0.65, 10);
        ctx.fill();
        ctx.stroke();
        ctx.beginPath();
        ctx.roundRect(x + w * 0.22, y, w * 0.5, h * 0.45, 10);
        ctx.fill();
        ctx.stroke();
        ctx.fillStyle = '#2c3e50';
        for (const wx of [x + w * 0.22, x + w * 0.68]) {
          ctx.beginPath();
          ctx.arc(wx, y + h, 14, 0, Math.PI * 2);
          ctx.fill();
        }
      } else if (o.shape === 'bear') {
        ctx.beginPath();
        ctx.arc(x + w / 2, y + h * 0.4, w * 0.45, 0, Math.PI * 2);
        ctx.fill();
        ctx.stroke();
        for (const ex of [x + w * 0.12, x + w * 0.88]) {
          ctx.beginPath();
          ctx.arc(ex, y + h * 0.06, w * 0.18, 0, Math.PI * 2);
          ctx.fill();
          ctx.stroke();
        }
        ctx.beginPath();
        ctx.arc(x + w / 2, y + h * 0.85, w * 0.34, 0, Math.PI * 2);
        ctx.fill();
        ctx.stroke();
        ctx.fillStyle = '#3b2a45';
        ctx.beginPath();
        ctx.arc(x + w * 0.36, y + h * 0.34, 5, 0, Math.PI * 2);
        ctx.arc(x + w * 0.64, y + h * 0.34, 5, 0, Math.PI * 2);
        ctx.fill();
      }
    }

    if (pointer) {
      ctx.strokeStyle = '#ff6f61';
      ctx.lineWidth = 3;
      ctx.beginPath();
      ctx.arc(pointer.x, pointer.y, 12, 0, Math.PI * 2);
      ctx.stroke();
      ctx.beginPath();
      ctx.moveTo(pointer.x - 20, pointer.y);
      ctx.lineTo(pointer.x + 20, pointer.y);
      ctx.moveTo(pointer.x, pointer.y - 20);
      ctx.lineTo(pointer.x, pointer.y + 20);
      ctx.stroke();
    }
  }
}
