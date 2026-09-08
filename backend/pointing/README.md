# Pointing Recognition（指向识别）

感知层：判断**孩子当前指的是哪个现实物体**。当前是浏览器实现（摄像头 + MediaPipe Hands
手势检测 + 2D 射线选物 + 确认话术兜底），为硬件版沉淀上层判定逻辑。

浏览器 pointing 与 RX5 pointing **共用同一上层 Schema**（`AGENTS.md` §38.7）：换到端侧推理时
只替换手势来源，选物与确认逻辑不重写。

- 架构定位：`AGENTS.md` §29 与 [`docs/architecture/04-backend-services.md`](../../docs/architecture/04-backend-services.md) §13
- 设计与实现：[`docs/design.md`](docs/design.md)

## 运行

```bash
npm start           # node server/server.js，默认 127.0.0.1:8792
```

本组件**无第三方依赖**（`package.json` 没有 `dependencies`，测试只用 Node 内置模块），
因此不需要 `npm install`。也**没有 lockfile**，所以 `npm ci` 会失败——直接 `npm start` 即可。

页面与端点：

```text
/                 主页面（指向实验室）
/admin.html       家长报表：指向准确率趋势 + 今日记录
POST /api/see     选中物体后的回应（LLM 不可达时走本地模板，不空响应）
WS   /ws/crown    触发广播
```

环境变量：`PORT`(8792)、`PO_DATA_DIR`（埋点目录，测试用）、LLM 三项（见 `docs/design.md`）。

摄像头只在明确 capture 窗口开启，并在成功或失败后关闭（`AGENTS.md` §38.6）。

## 测试

```bash
npm test            # node --test tests/*.test.js
```

> **已知失败（先于本次重组存在）**：`tests/server.test.js` 的静态服务用例断言首页包含
> `万物模式`，但 `web/index.html` 实际写的是「指向实验室 / 指向一个物件」。该用例自
> `init push` 起就失败，两个文件都未被改动过。当前 42 用例中 41 通过。
> 修复需要决定以哪一侧为准（改断言还是改页面文案），属于独立缺陷，未并入本次文档重组。

## 涉及契约

不直接消费 `shared/contracts/v1`。指向结果经上层 Schema 交给 Agent 层；本组件不做教学决策。

## 运行时数据目录

`data/*.jsonl`（已 gitignore）：埋点。

## 历史

旧的「指向识别模块 PRD」（含 FR-P01…FR-P10 验收项与北极星指标）已归档在
[`docs/archive/prd/pointing-prd-v1.md`](../../docs/archive/prd/pointing-prd-v1.md)。
