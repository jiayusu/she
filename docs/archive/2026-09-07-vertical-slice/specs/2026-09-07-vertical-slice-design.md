> **归档 · 历史文件 · 非权威（ARCHIVED — HISTORICAL, NON-AUTHORITATIVE）**
>
> 本文件描述 2026-09-07 纵向切片的**设计时状态**，该切片已交付完成。
> 文中"在不搬迁现有 `engine`/`kg`/`store`/`po`/`route`/`zhihu` 组件的前提下"已不成立：
> 这些目录随后已退役且不在磁盘上（见 `AGENTS.md` §29）。
> 文中的绝对路径（`A:\working\she\...`）同样失效——仓库路径不固定，请使用仓库相对路径。
>
> 当前架构真源：`AGENTS.md` 与 `docs/architecture/`。
> 实际交付记录：`playbooks/changes/2026-09-07-*.md` 与 `playbooks/decisions/ADR-0001-*.md`。

---

# SHE 跨端纵向切片设计

**日期：** 2026-09-07

**状态：** 已交付并归档（原文记载："已完成对话评审，待仓库文件复核"）

**范围：** iOS 17 家长端、Device Gateway、RDK X5 Ubuntu 22 设备运行时、共享契约、工程 playbooks 与项目 skills

## 1. 目标

在不搬迁现有 `engine`、`kg`、`store`、`po`、`route`、`zhihu` 组件的前提下，交付一个可以演示、测试和继续演进的端到端纵向切片：家长在 iOS App 查看儿童学习证据和设备状态，Device Gateway 提供结构化 API 并维护设备会话，RDK X5 runtime 或本机 simulator 通过 WebSocket 交换事件。

本阶段不实现完整账户系统、真实云端 Learner Profile、完整七 Agent 教学链或未经真机验证的硬件能力。它建立这些后续能力必须遵循的契约和边界。

## 2. 已确认约束

- iOS 最低版本为 iOS 17，iPhone 为主布局，iPad 自适应。
- 首版无注册登录，内置单家庭演示档案。
- 设备凭据只允许进入 Keychain；演示数据不得冒充真实学习结论。
- RDK X5 当前不可通过 SSH 访问，因此必须提供 simulator，并诚实标记未完成的真机验收。
- 视觉采用 `Soft Orbit + Pet First`：雾白、冷薰衣草、空气感玻璃、SwiftUI 轻 3D 小P、极简任务 UI。
- 儿童长期状态的唯一真源仍在服务端；App 和设备端不维护独立 mastery。
- 摄像头只能由显式事件触发，采集窗口结束必须关闭；默认不保存或持续上传原始音视频。
- 每个逻辑变更都必须留下结构化 change 记录；可复用且有稳定验证方式的流程才升级为 skill。

## 3. 采用方案

采用“契约先行、保留现有目录”的方案。

不采用“先重排整个仓库”，因为它会制造大量与功能无关的路径变更并同时威胁既有测试。不采用“iOS 与设备各自原型”，因为那会快速产生两套不兼容事件模型。

新增目录：

```text
shared/contracts/v1/          跨端 JSON Schema、示例与契约版本
backend/device_gateway/       HTTP API、设备 WebSocket、演示状态
clients/ios/                  iOS 17 SwiftUI 家长端
clients/hardware-rx5/         Ubuntu 22 Python runtime、适配器与 simulator
playbooks/                    变更、故障、决策、发布与模板
skills/                       项目级可复用工作流
docs/superpowers/             设计与实施计划
```

现有目录继续原位运行。目录迁移只能在接口稳定后作为独立变更执行。

## 4. 组件边界

### 4.1 Shared Contracts

`shared/contracts/v1` 是跨端字段的唯一规范来源，保存 JSON Schema 和通过/拒绝 fixtures。首版定义：

- `DeviceEvent`：`event_id`、`contract_version`、`device_id`、`session_id`、`sequence`、`occurred_at`、`type`、`payload`。
- `DeviceCommand`：`command_id`、目标会话、序列号、过期时间、`speak|led|capture|stop_capture|fallback` 及 payload。
- `DashboardSnapshot`：问候、宠物状态、今日亮点、单一任务、三个核心指标、设备摘要。
- `WeeklyReport`：结构化学习证据、趋势、词汇状态变化和脚手架趋势。
- `ParentConstraints`：会话时长、偏好主题、次日场景和教学压力。
- `DeviceSettings`：音量、灯效、摄像头能力、原始音频上传许可。

字段变更顺序固定为 Schema → fixtures → Gateway → RX5 → iOS → 全部契约测试。破坏性变更必须新增契约版本，不得静默猜测字段。

### 4.2 Device Gateway

Gateway 是设备与控制面的边界，不做课程或 mastery 判断。首版提供：

```text
GET   /health
GET   /v1/dashboard
GET   /v1/reports/weekly
GET   /v1/devices/{id}
PATCH /v1/devices/{id}
PUT   /v1/parent-constraints
POST  /v1/privacy/export
POST  /v1/privacy/erase
WS    /v1/device/session
```

HTTP 响应使用固定演示 repository。隐私导出与删除只实现可审计的 mock 工作流，响应必须明确 `mock` 状态，不能暗示已删除真实 `store` 数据。

WebSocket 维护设备在线状态、会话序列、心跳、命令确认和 `event_id` 幂等去重。乱序、重复、过期或契约不兼容消息返回可诊断错误并保持连接状态可恢复。

### 4.3 RDK X5 Runtime

设备 runtime 使用 Python 异步事件循环，并通过 Protocol/adapter 隔离硬件：

- `CameraPort`：短时采集、结构化检测结果、强制关闭。
- `AudioPort`：录制受控音频片段、播放 TTS 或本地安全提示。
- `GpioPort`：按键/触摸输入和 LED 输出。
- `TransportPort`：WebSocket 连接、心跳、确认和重连。

Simulator 实现相同接口，用固定时钟和脚本化事件验证完整链路。真机 adapter 采用能力探测：能力不存在时返回 `capability_unavailable`，不得返回伪成功。

官方 RDK X5 资料表明，当前推荐系统线基于 Ubuntu 22.04 aarch64；Python BPU 示例使用 `hbm_runtime`，MIPI 摄像头示例使用 `srcampy.Camera()`，GPIO Python 库为 `Hobot.GPIO`。音频首版通过 ALSA 命令/设备抽象接入。具体型号、引脚和 ALSA device 必须等 SSH 可用后由 preflight 发现，不能硬编码猜测。

参考：

- [D-Robotics RDK Model Zoo](https://github.com/D-Robotics/rdk_model_zoo/tree/rdk_x5)
- [RDK X5 摄像头示例](https://github.com/D-Robotics/rdk_x_doc/blob/main/i18n/en/docusaurus-plugin-content-docs/current/03_Basic_Application/03_pydev_demo_sample/RDK_X5/09_web_display_camera_sample.md)
- [RDK GPIO 应用](https://github.com/D-Robotics/rdk_doc/blob/main/docs/03_Basic_Application/01_40pin_user_sample/gpio.md)
- [RDK X5 硬件介绍](https://github.com/D-Robotics/rdk_doc/blob/main/docs/01_Quick_start/hardware_introduction/rdk_x5.md)

### 4.4 iOS App

App 使用 SwiftUI、async/await、`URLSession`、Codable 和 Keychain，不引入重量级 UI 或 3D 依赖。业务数据通过 `AppAPI` protocol 获取，`MockAppAPI` 与 `LiveAppAPI` 可替换。

底部导航固定为：

```text
今天 | 报告 | 设备 | 我的
```

“今天”采用 Pet First：顶部问候与设备状态，中部为小P和一条真实亮点，其后是单一今日任务，底部为主动开口、无提示输出、新词三个指标。“报告”采用更高信息密度，展示周趋势与结构化 evidence。“设备”负责状态、音量、灯效与隐私能力。“我的”负责演示档案、家长约束、导出和删除入口。

小P用 SwiftUI 多层径向渐变、高光、内外阴影和低频呼吸动画绘制。视觉 token 统一管理颜色、间距、圆角、阴影和动画时长。必须支持深色模式、Dynamic Type、VoiceOver 和 Reduce Motion。

## 5. 数据流

```text
iOS App
  └─ HTTPS ──> Device Gateway ──> Demo Repository

RDK X5 Runtime / Simulator
  <─ WebSocket ─> Device Gateway
       event: wake / touch / pointing / device_state / command_ack
       command: speak / led / capture / stop_capture / fallback
```

后续真实服务接入时，Gateway 只替换 repository/adapters，不改变 App 或设备公开契约。

## 6. 故障与隐私策略

- Gateway 不可达：指数退避并加入抖动；设备播放本地安全提示，不产生空响应。
- 摄像头或模型不可用：关闭采集，上报 capability；不上传占位图。
- 消息重复或乱序：按 `event_id` 去重并校验 `session_id + sequence`。
- 契约不兼容：明确拒绝并记录版本，不静默降级字段。
- App 加载失败：保留最近一次非敏感快照并显示离线状态，不伪造“实时”。
- 日志默认不包含图像、音频、儿童原话、认证信息或完整设备凭据。
- 相机采集必须使用 `try/finally` 等价结构保证关闭。
- 原始音视频不能进入 simulator fixtures、Git 或 playbook。

## 7. Playbooks 与 Skills

### 7.1 结构化记录

```text
playbooks/changes/       目标、层级、契约影响、文件、验证、回滚
playbooks/incidents/     症状、环境、根因、无效尝试、解决、验证、防复发
playbooks/decisions/     重要取舍、替代方案和后果
playbooks/releases/      本地检查、CI、推送、RX5 真机验收
playbooks/templates/     固定文档模板
```

“每次 diff”定义为每个可独立审查的逻辑变更。记录引用 Git commit，不复制逐行 diff。

### 7.2 首批 Skills

- `she-contract-change`：强制跨端契约修改顺序和验证。
- `she-incident-recovery`：先搜索已知 incident/skill，再按证据诊断未知错误并沉淀。
- `she-ios-soft-orbit`：复用视觉 token、Pet First 层级及无障碍检查。

`she-rx5-preflight` 暂不创建。首次真机连接先执行 playbook；只有步骤经真实硬件验证和修正后才升级为 skill。

`AGENTS.md` 将要求 Coding Agent：修改前识别层级并检索 skills/incidents；修改后记录 change；相同错误优先执行现有 skill；所有解决方案必须包含验证证据。

## 8. 测试策略

### 8.1 本机

- 现有 Python 与 Node 测试保持通过。
- Shared Contracts 校验合法/非法 fixtures。
- Gateway 测试 HTTP、WebSocket、幂等、乱序、版本错误和 mock 隐私语义。
- RX5 simulator 测试重连、显式采集、`finally` 关闭、离线 fallback 和无敏感日志。
- iOS 源码、资源和工程配置进行平台无关的结构检查。

### 8.2 macOS CI

- 生成 Xcode 工程并构建 iOS 17 App。
- 执行 Swift 单元测试、ViewModel 测试和 Codable fixture 测试。
- 校验目标版本、无障碍标识和 Reduce Motion 分支。

### 8.3 完成标准

- Simulator 与 Gateway 完成一次上线、wake、capture、pointing、speak、ack 演示。
- iOS 四个页面可从 Gateway 演示 API 加载并正确呈现离线/失败状态。
- 所有可在当前 Windows 环境运行的测试通过。
- GitHub Actions 配置完整；若推送后 CI 可访问，则构建结果必须通过后才宣称 iOS 已编译验证。
- 无密钥、原始儿童数据、数据库、模型产物、`node_modules` 或 GitHub 超限文件进入 Git 索引。

## 9. Git 与发布

当前 `A:\working\she` 没有 Git 元数据，目标 GitHub 仓库为空。实施将初始化 `main`，添加目标 remote，并建立根 `.gitignore`。ConceptNet 原始包、KG 快照、数据库、缓存、日志、`.env` 和视觉讨论临时目录只留在本机，不删除但不提交。

变更按可独立验证的任务提交。最终推送前执行测试、敏感信息扫描和大文件审计。若认证失败，保留完整本地提交并报告唯一剩余认证步骤，不把凭据写入仓库。

## 10. 明确不在本阶段范围

- 用户注册、短信登录、云端多家庭同步。
- 将演示数据写成真实 Learner Profile。
- 完整七 Agent 实现或旧五大臣架构迁移。
- RX5 真机性能、摄像头型号、GPIO 引脚和 ALSA device 的虚假验收。
- App Store 发布、推送通知、支付或第三方分析 SDK。
- 现有组件目录的大规模搬迁。
