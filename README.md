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

- `A:\working\she\clients\ios`：SwiftUI 家长端；Soft Orbit / Pet First，单演示家庭，无登录。
- `A:\working\she\backend\device_gateway`：Node 20 + TypeScript；家长 HTTP API 与设备 WebSocket。
- `A:\working\she\clients\hardware-rx5`：Python 3.10+；RDK X5 端口、模拟器、安全降级与硬件能力探测。
- `A:\working\she\shared\contracts\v1`：JSON Schema 2020-12 与跨语言规范 fixtures。
- `A:\working\she\engine`、`A:\working\she\store`、`A:\working\she\kb`：剧情执行、共享记忆、审核知识基础设施。
- `A:\working\she\po`、`A:\working\she\route`、`A:\working\she\zhihu`：指向识别、旧路由迁移资产、隔离的数据情报。

所有教学 Agent 规则与信任边界见 `A:\working\she\AGENTS.md`。儿童实时链路不得访问开放互联网，
长期学习判断必须有 evidence，Agent 不得直接写 SQLite / FAISS。

## 本地快速验证（Windows）

```powershell
& 'A:\working\she\scripts\verify.ps1'
& 'A:\working\she\scripts\audit_repository.ps1'
```

启动 Gateway：

```powershell
Set-Location -LiteralPath 'A:\working\she\backend\device_gateway'
npm install
npm start
```

运行确定性设备模拟器：

```powershell
python -m pip install -e 'A:\working\she\clients\hardware-rx5[dev]'
python -m she_device.cli simulate --once
```

iOS 项目生成与构建命令见 `A:\working\she\clients\ios\README.md`；iOS 需要 macOS、Xcode 与 XcodeGen。

## RDK X5 状态

模拟器、契约、摄像头生命周期和降级逻辑已自动化验证。真实 RDK X5 上的 Ubuntu 22.04、
`srcampy`、`hbm_runtime`、`Hobot.GPIO`、ALSA、摄像头和针脚仍须在设备可 SSH 后逐项验证。
遵循 `A:\working\she\playbooks\releases\rx5-first-boot.md`，不得把“模块缺失”伪装成成功。

## Playbook 与 Skill 纪律

每个逻辑变更都在 `A:\working\she\playbooks\changes` 留下同提交记录；故障先搜索
`A:\working\she\playbooks\incidents` 与 `A:\working\she\skills`。只有跨场景重复验证、包含真实判断步骤的
流程才提升为 skill。iOS 视觉改动先使用 `A:\working\she\skills\she-ios-soft-orbit\SKILL.md`。

## 隐私红线

- 原始儿童音频、画面、话语、token、凭据、数据库与日志不得进入 Git。
- 摄像头只在明确 capture 窗口打开，并在成功或失败后关闭。
- 演示导出/删除必须标记 `mock: true` 与 `store_mutated: false`。
- iOS 不提供 mastery 写入口，凭据只进 Keychain，网络响应体不写日志。
