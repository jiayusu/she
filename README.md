# SHE — 小P儿童英语陪伴系统

SHE 面向 4–8 岁英语启蒙儿童，用一个稳定的前台角色“小P”把现实物件、
小剧情和最小提示连起来，让孩子愿意从听懂、跟读走到主动开口。

当前第一阶段是一条可重复验证的端到端纵向切片：

```text
iOS 17 家长端 → Device Gateway → RDK X5 Python 运行时 / 模拟器
                         ↕
               shared/contracts/v1
```

## 组件边界

- `clients/ios`：SwiftUI 家长端；Soft Orbit / Pet First，单演示家庭，无登录。
- `backend/device_gateway`：Node 20 + TypeScript；家长 HTTP API 与设备 WebSocket。
- `clients/hardware-rx5`：Python 3.10+；RDK X5 端口、模拟器、安全降级与硬件能力探测。
- `shared/contracts/v1`：JSON Schema 2020-12 与跨语言规范 fixtures。
- `agents/interaction`、`agents/director`：儿童唯一语言出口与学习导演。
- `backend/knowledge_graph`、`backend/memory_store`、`backend/pointing`、`backend/intel`：审核知识、共享记忆、指向识别与知乎数据情报基础设施。
- `backend/digital_twin`：**仅文档目录**，说明服务器权威 Digital Twin 与硬件门户；
  实现在 `backend/device_gateway/src/digital-twin.ts`，该组件同时承担唯一设备传输边界。

## 文档入口

- `AGENTS.md`：硬规则、组件归属、工作纪律，以及架构文档导航。**改代码前先读这里。**
- `docs/architecture/`：按主题拆分的详细架构说明（Agent、共享状态、硬件、Web、App、契约）。
- `docs/architecture/99-target-state.md`：目标状态，**不是现状**。
- `playbooks/`：变更、事故、决策与发布记录。`docs/archive/`：历史文件，非权威。
- 组件文档约定（见 AGENTS.md「组件文档约定」）：`<component>/README.md` 写职责 / 运行 / 测试，
  `<component>/docs/design.md` 写设计细节。**尚未全部组件对齐，正在收敛中。**

儿童实时链路不得访问开放互联网，长期学习判断必须有 evidence，Agent 不得直接写 SQLite / FAISS。

## 本地快速验证（Windows）

> 本文所有路径均相对于仓库根目录。请先 `cd` 到仓库根再执行以下命令。

```powershell
& './scripts/verify.ps1'
& './scripts/audit_repository.ps1'
```

启动 Gateway（用 `Push-Location`/`Pop-Location`，执行完自动回到仓库根）：

```powershell
Push-Location -LiteralPath './backend/device_gateway'
npm install
npm start
Pop-Location
```

运行确定性设备模拟器：

```powershell
python -m pip install -e './clients/hardware-rx5[dev]'
python -m she_device.cli simulate --once
```

iOS 项目生成与构建命令见 `clients/ios/README.md`；iOS 需要 macOS、Xcode 与 XcodeGen。

## RDK X5 状态

模拟器、契约、摄像头生命周期和降级逻辑已自动化验证。真实 RDK X5 上的 Ubuntu 22.04、
`srcampy`、`hbm_runtime`、`Hobot.GPIO`、ALSA、摄像头和针脚仍须在设备可 SSH 后逐项验证。
遵循 `playbooks/releases/rx5-first-boot.md`，不得把“模块缺失”伪装成成功。

## Playbook 与 Skill 纪律

每个逻辑变更都在 `playbooks/changes` 留下同提交记录；故障先搜索
`playbooks/incidents` 与 `skills`。只有跨场景重复验证、包含真实判断步骤的
流程才提升为 skill。iOS 视觉改动先使用 `skills/she-ios-soft-orbit/SKILL.md`。

## 隐私红线

- 原始儿童音频、画面、话语、token、凭据、数据库与日志不得进入 Git。
- 摄像头只在明确 capture 窗口打开，并在成功或失败后关闭。
- 演示导出/删除必须标记 `mock: true` 与 `store_mutated: false`。
- iOS 不提供 mastery 写入口，凭据只进 Keychain，网络响应体不写日志。
