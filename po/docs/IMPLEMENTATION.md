# 指向识别模块（浏览器端）· 实现说明

对应 `README.md`（PRD V1.0）的完整实现。零 npm 依赖，Node ≥18 直接运行。

## 快速开始

```bash
npm start            # node server/server.js，默认 http://localhost:8787
npm test             # 42 个单元/集成测试（node:test）
```

- 主页面 `http://localhost:8787/` —— 王冠 · 万物模式
- 家长报表 `http://localhost:8787/admin.html` —— 指向准确率趋势 + 今日万物记录 + 蛇首模拟按钮

页面默认进入**演示场景**（无需摄像头/模型即可体验全链路：移动鼠标指向物件 → 点"指它" → 确认 → 王冠回答）。
真实摄像头模式：设置里把"画面来源"切到"摄像头"（授权后走 MediaPipe Hands + 物件检测）。

## 目录结构

```
server/
  server.js        零依赖 HTTP 服务：静态托管 + /api/see + 埋点报表 + /crown/press + WS 升级
  ws.js            极简 RFC6455 WebSocket 服务端（/ws/crown 广播）
  see.js           /api/see 生成逻辑：LLM（可选）→ 模板兜底
web/
  index.html       孩子端主页面（摄像头/演示场景、确认卡片、隐私徽章）
  admin.html       家长报表（FR-P08 趋势/明细、FR-P09 今日记录、FR-P10 蛇首模拟）
  css/app.css
  js/
    config.js      全部阈值 + 肯定/否定词表 + parseAnswer（最长匹配优先，否定同长优先）
    gesture.js     FR-P02 手势判定（PIP 向量夹角，尺度不变；放宽档=食指+中指并伸）
    raycast.js     FR-P03 射线求交（slab 法）：多交取最近、无交取离指尖最近、中心兜底
    pipeline.js    FR-P01/04/05/06/07 会话编排 + ConfirmFlow 状态机（可注入依赖，Node 可测）
    capture.js     FR-P01 摄像头拉起 + 5 帧突发采集；FR-P06 停流；裁切上传
    handsource.js  手势源：MediaPipe Hands（CDN）/ 演示合成手（同走判定规则）
    detector.js    检测器：YOLOv8n ONNX Runtime Web / 演示显著性（颜色连通域）/ 场景内置
    speech.js      TTS + ASR（zh-CN）+ 确认话术适配器 + "那是什么"语音唤醒
    replies.js     儿童话术模板（服务端/浏览器共用，保证任何路径非空响应）
    telemetry.js   FR-P08 埋点上报（失败排队重试；仅统计字段，无图像）
    crown-ws.js    FR-P10 /ws/crown 客户端（断线重连）
    scene.js       演示场景（红球/黄杯/绿树/蓝车/紫熊）
    app.js         UI 装配：事件→状态栏/叠加层（射线+框+指尖）/确认卡片
tests/
  helpers/handpose.js   合成 21 关键点手部模型（角度几何，验证判定规则）
  gesture/raycast/confirm/pipeline/server .test.js   共 42 个用例
data/pointing-stats.jsonl   埋点落盘（JSONL，可用 DELETE /admin/pointing-stats 清空）
```

## 需求覆盖对照

| 编号 | 实现 | 验证 |
|---|---|---|
| FR-P01 触发+5帧突发 | 按钮 / 语音"那是什么"（SpeechRecognition 连续监听）/ WS 蛇首指令三入口；`CameraCapture.captureBurst` 5 帧×70ms | GUI 实测触发→采集；`triggerToCaptureMs` 入埋点（>1s 计数超时次数） |
| FR-P02 手势判定 | `gesture.js`：食指 PIP 夹角≥140°且指尖比例≥1.3 判伸直；中/无名/小指≤110°或比例≤1.15 判弯曲；腕 visibility≥0.5；放宽档食指+中指并伸 | 合成姿态集 81 种指向姿态全命中、拳头/巴掌/伸手拿取全拒绝（tests/gesture）；真实儿童数据需按 PRD 自采后调 `config.js` 阈值 |
| FR-P03 射线选物 | `raycast.js` slab 求交，腕(0)→食指根(5) 延长；多交按 t 升序；无交按指尖(8)到框距离；只取前方交点 | tests/raycast：近距优先、身后不取、平行无交、中心兜底 |
| FR-P04 确认话术 | `ConfirmFlow`：≤2 轮；肯定→生成；否定→第二候选；再否定→"那我们一起看看别的东西吧"；词表覆盖"是/对/嗯/没错/好/想/就是它 / 不是/不对/没有/换一个…"；ASR+按钮双通道 | tests/confirm 12 用例；GUI 实测两轮否定→优雅退出 |
| FR-P05 全链路兜底 | 摄像头失败→台词兜底；0 框→"再对准一点"重试×2→优雅收尾；0 帧手势→中心框+重确认；LLM 失败→模板（服务端 `template-fallback` + 浏览器本地模板双保险）；所有异常也有台词 | tests/pipeline 全路径断言非空响应；GUI 实测 no-object 链 |
| FR-P06 隐私窗口 | 流打开后 2s 硬超时停轨（`finally` 保证必停）；页面隐藏/关闭也停；帧只进内存；上传仅所选框裁切 JPEG（默认开、可关、不传原图） | GUI 摄像头徽章随窗口开/关；tests/pipeline 断言 closeCamera 次数 |
| FR-P07 置信度分级 | `gradeGestureFrames`：≥3 帧轻确认（2s 无否定自动通过）；1-2 帧重确认（"你是指A还是B？"）；0 帧中心框兜底+重确认 | tests/pipeline + confirm；GUI 实测 5/5 帧走轻确认 |
| FR-P08 埋点 | 每次会话记录 {触发源, 手势帧数, 候选列表, 选中框/标签, 确认结果, 轮次, 纠正次数, 触发→采帧ms, apiSource…}；`GET /admin/pointing-stats` 聚合（准确率/首选即中/纠正均值/手势分布/14天趋势） | tests/server 聚合断言；admin.html 渲染 |
| FR-P09 今日万物记录 | 报表 `today` 字段（指了几次/一次就对几次/明细）；与 FR-P08 同一存储 | admin.html "今日万物记录"卡片 |
| FR-P10 小智联动 | `WS /ws/crown` + `POST /crown/press` 广播 `{"type":"please_photo"}` → 页面自动拉起 FR-P01；断线重连 | tests/server WS 广播用例；GUI 实测 curl 按下→页面自动触发会话 |

## 服务端接口

```
POST /api/see                {image?, level, bbox_hint:{x,y,w,h,label?}} → {ok,text,source,latencyMs}
                             source: llm | template | template-fallback（LLM 失败自动回落）
                             LLM 接线：SEE_LLM_URL / SEE_LLM_KEY / SEE_LLM_MODEL 环境变量
                             SEE_SIMULATE_LLM_FAIL=1 可强制演练模板兜底
GET  /admin/pointing-stats   聚合报表（total/accuracy/days/labels/today/recent）
POST /admin/pointing-stats   追加一条会话记录
DELETE /admin/pointing-stats 清空（admin 页有按钮）
POST /crown/press            模拟蛇首按下 → 向所有页面广播"请拍照"
WS   /ws/crown               浏览器监听通道
GET  /healthz
```

环境变量：`PORT`（默认 8787）、`PO_DATA_DIR`（埋点目录，测试用）、上述 LLM 三项。

## 与真实视觉模块对接

当前 `/api/see` 是视觉模块存根（用 bbox_hint.label 组织话术）。接入真实模块时只需替换
`server/see.js` 的 `generateReply`：把裁切图交给端侧/服务端视觉模型生成描述，失败路径已由模板兜底。

物件检测三档 Provider（`detector.js`）：
1. **YOLOv8n ONNX**：把 `yolov8n.onnx` 放到 `web/models/`（640 输入、[1,84,8400] 输出、COCO 80 类已译中文），ONNX Runtime Web 从 CDN 加载，自动 letterbox/NMS；
2. **演示显著性检测器**：无模型时按颜色饱和度连通域产出"红色的东西"等候选框（弱光→0 框，正好验证 FR-P05）；
3. **场景内置**：演示模式直接返回已知物件框。

## 已验证的端到端场景（浏览器 GUI 实测）

1. 演示场景指向红球 → 射线高亮命中 → "你是想问红色的球吗？" → 2s 无否定自动通过 → /api/see 回应红球小知识；
2. 连续两轮点"不是" → "那我们一起看看别的东西吧！"（优雅退出）；
3. `curl -X POST /crown/press` → 打开中的页面自动拉起指向窗口并走完整会话；
4. 摄像头模式（IAB 虚拟设备、画面无内容）→ 采帧后停流 → 两次"再对准一点" → 优雅收尾，无空响应、无报错；
5. 家长报表正确累计：准确率=确认通过/进入确认、手势命中分布（0/1-2/≥3 帧）、今日记录。

`npm test`：42/42 通过。

## 已知限制 / 下一步（对应 PRD Out of Scope 或 V1.1）

- 手势召回/误触发阈值为合成集验证值，需按 PRD 用 20 孩子自采集校正 `config.js`（词表同源可扩充）；
- "点头"确认未做（需 face landmarker），当前确认通道=语音词表 + 屏幕按钮；
- 语音唤醒/ASR 依赖浏览器 SpeechRecognition（Chrome 需联网；iOS Safari 部分版本不可用），不可用时自动降级按钮，轻确认仍有 2s 快进路径；
- 连续视频流实时跟随、3D 指向、挥手/鼓掌词库为 Out of Scope；
- YOLO 模型文件不入库（.gitignore），需手动放置；无模型时自动走演示检测器，不影响其余链路。
