# 硬件端：地瓜 RX5 + 摄像头

> 设备端职责、摄像头边界、本地与服务端分工、设备接口建议与硬件红线。
>
> 硬规则、组件归属与导航见仓库根 [`AGENTS.md`](../../AGENTS.md)。
> 本文各节沿用 AGENTS.md 原有编号，以保持既有交叉引用有效。

---

# 31. 硬件端：地瓜 RX5 + 摄像头

硬件端是儿童真正使用的实时交互终端。

## 31.1 做什么

硬件端负责：

```text
唤醒
采集语音
采集图像/短帧
触摸/按键事件
设备状态上报
播放 TTS
灯效/提示反馈
断网时基础兜底
```

硬件端应尽量承担 **确定性、低延迟、隐私敏感** 的工作。

推荐职责：

```text
RX5
├── Wake / Button / Touch Event
├── Audio Capture
├── Camera Capture
├── Local Vision Preprocess
├── Pointing / Object Candidate
├── Device State
├── Audio Playback
├── LED / Light Feedback
└── Network / Reconnect / Local Fallback
```

## 31.2 摄像头负责什么

摄像头只为“当前现实场景理解”提供输入。

典型输出：

```json
{
  "frame_id": "",
  "detected_objects": [
    {
      "label": "fridge",
      "bbox": [0, 0, 0, 0],
      "confidence": 0.0
    }
  ],
  "pointing_target": "fridge",
  "pointing_confidence": 0.0
}
```

摄像头链路不负责：

- 判断今天学什么；
- 判断孩子是否掌握某词；
- 直接生成回复；
- 直接写长期记忆。

视觉结果只能作为：

```text
Learning Director
Curriculum Agent
Story World Agent
```

的环境上下文。

## 31.3 本地与服务端边界

优先本地：

```text
唤醒
触摸
摄像头生命周期
基础手势判断
图像裁切
设备状态
隐私控制
本地兜底提示
```

可以送服务端：

```text
ASR 所需音频
必要的裁切图像 / 特征
pointing/object 结构化结果
设备事件
```

不得默认持续上传：

```text
全天摄像头视频
无触发环境音
无关家庭场景原图
```

## 31.4 硬件端接口建议

### 设备 → 服务端

```text
WS /device/session
```

事件：

```json
{
  "type": "wake|touch|audio|pointing|device_state",
  "device_id": "",
  "session_id": "",
  "ts": 0,
  "payload": {}
}
```

### 服务端 → 设备

```json
{
  "type": "speak|led|capture|stop_capture|fallback",
  "session_id": "",
  "payload": {}
}
```

## 31.5 硬件端红线

1. 摄像头必须事件触发，不默认持续上传。
2. 采集窗口结束后必须停止采集。
3. 设备端不保存儿童原始视频作为长期学习数据。
4. Agent 不允许自行打开摄像头；必须通过硬件权限层。
5. 网络失败时必须有确定性回应，不允许孩子得到空响应。
6. 设备 ID 只用于设备会话，不作为儿童身份画像本身。
