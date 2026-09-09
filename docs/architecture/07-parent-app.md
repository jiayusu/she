# App 端：家长端

> 本文区分 iOS 家长端当前代码与生产目标。硬规则、组件归属与导航见仓库根
> [`AGENTS.md](../../AGENTS.md)；现实语言 RPG 产品定义见
> [`12-embodied-language-rpg.md](12-embodied-language-rpg.md)。
>
> 当前 iOS quest UI、生产身份与真实隐私链均未实现。

---

# 33. App 端：家长端

App 是家长与系统之间的控制面，不是儿童实时教学 Agent。它只能通过 Gateway API 读取摘要或
提交家长约束，不能直接修改 Learner mastery、world state 或设备驱动。

## 33.0 当前实现总览

`clients/ios` 是 iOS 17 SwiftUI 应用，使用 XcodeGen。当前代码明确定位为“无登录、单一演示
家庭”，包含四个 Tab：

~~~text
今天
成长
设备
家庭
~~~

| 能力 | 当前事实 |
|---|---|
| Dashboard | 已读取 `GET /v1/dashboard`；Gateway 默认演示数据 |
| Weekly report | 已读取 `GET /v1/reports/weekly`；不是生产 Parent Agent 摘要 |
| Device | 有设备状态/有限设置页面和 Gateway API client |
| Parent constraints | 可提交时长与场景等约束 |
| Privacy | 有演示导出/删除确认 UI；后端不导出、不删除真实数据 |
| RPG quest | 未解码或调用 `GET /v1/rpg/state`，没有真实任务卡 |
| 生产接入 | Release endpoint 为惰性占位域名；没有登录和多家庭授权 |

“有页面/客户端方法”只表示 UI 与协议骨架存在，不等于生产能力完成。

## 33.1 当前 Today 页面

Today 页面展示：

~~~text
设备在线摘要
小P的观察
dashboard task
三个学习指标
~~~

其中“下一步”来自通用 `DashboardSnapshot.task`。当前按钮没有启动 RPG 的行为，也不读取
`rpg-quest-summary`，所以它不是 `milk_picnic.v1` 当前节点的权威任务卡。

## 33.2 待实现：RPG Quest UI

Gateway 已提供后端只读端点：

~~~text
GET /v1/rpg/state?child_id=...&session_id=...&turn_id=...
~~~

iOS 仍需要新增共享 contract 对应模型、严格 decoder、API method 和明确的加载/空/离线/错误
状态。Quest UI 只能呈现脱敏摘要，例如：

~~~text
当前节点与 phase
小P可转述的 world role
审核 prompt/feedback 引用对应的产品文案
虚拟 inventory 与完成节点
next quest
delivery status
world revision（仅调试或支持场景）
~~~

它不得显示儿童逐字原话、Speech Act evidence、内部 assessment、原始感知、request hash 或完整
Memory response，也不得提供 inventory/world/mastery 编辑功能。

阶段触发建议：

| phase | 家长/亲子 UI |
|---|---|
| `seeking_object` | 显示“下一步去找什么”的非评分提示 |
| `confirming_object` | 表示系统仍在确认，不宣告找到 |
| `presenting` | 显示提示正在准备/播放 |
| `awaiting_speech` | 仅说明设备正在等待，不在 App 代替孩子作答 |
| `delivery_failed` | 提供检查设备/重试说明，不伪造剧情推进 |
| `paused` | 尊重暂停，只通过明确操作发起 resume |
| `completed` | 展示虚拟成果，不等同于 mastery |

RPG 的实时 speech 和 pointing 仍发生在设备/Gateway 链路，家长 App 不应成为第二套
SpeechActResolver 或 Story Engine。

## 33.3 学习报告

目标态报告必须基于：

~~~text
Assessment evidence
+ Learner Profile
+ Learning History
~~~

而不是让 LLM 根据聊天记录自由总结。目标字段可包括主动开口、无提示输出、提示等级趋势、新
词与迁移证据，但必须说明证据口径，不能把 quest success 当 mastery。

当前 iOS 已有 Reports 页面与 weekly report decoder，但 Gateway 默认返回
`DemoRepository` 演示数据；当前没有独立 Parent Agent、生产 Learning History 聚合或真实家庭
报告验收。

## 33.4 家长输入

当前 App 可向 Gateway 提交 `ParentConstraints`，包括 session 时长、偏好/避免主题、下一日场景
和 teaching pressure。它们是 Director/Curriculum 可消费的约束，不是能力结论。

例如“我觉得他已经会 apple 了”最多作为辅助 evidence，不能直接写：

~~~text
apple = TRANSFERRED
~~~

生产版本还需要身份、授权、冲突处理、审计及“约束何时生效”的反馈；当前演示环境不能证明这些
能力已完成。

## 33.5 设备管理

目标职责包括设备绑定、Wi-Fi、音量、灯效、摄像头/麦克风权限、固件、在线状态与解绑。设备控制
必须统一经过 `backend/device_gateway`。

当前 iOS 有设备摘要与有限设置 API，但无登录单家庭演示不等于完成真实绑定、所有权校验、Wi-Fi
配网、固件升级或解绑。App 不承担实时音视频推理，也不得直接开启摄像头驱动。

## 33.6 隐私与数据

当前 Profile 页面明确写着演示隐私流程。它调用：

~~~text
POST /v1/privacy/export
POST /v1/privacy/erase
~~~

但 Gateway 当前只返回：

~~~json
{
  "status": "accepted_demo_only",
  "mock": true,
  "store_mutated": false
}
~~~

因此以下生产能力仍未实现：

- 用户登录、家庭/儿童数据范围授权；
- 导出前的数据清单与真实可下载产物；
- 将 erase 请求可靠路由到 Memory 的 `POST /memory/erase`；
- 删除任务状态、失败恢复、完成证明与审计；
- 关闭长期记忆、摄像头能力和原始音频上传的端到端执行证明；
- 多设备、多儿童和监护人权限隔离。

App 不得把“请求被演示端点接受”展示成“真实数据已经删除”。Memory 的 RPG learning path 不存
儿童逐字原话，但旧 episodic API 仍有 `utterance` 字段；在迁移与生产验证结束前，也不能对外
承诺全系统零原话存储。

## 33.7 App 端硬边界

App 不得：

- 直接修改 Learner mastery、world revision 或 virtual inventory；
- 直接调用 Memory learning commit、KG 数据文件或设备驱动；
- 在本地复制 Director、Scaffold、Speech Act 或 Story transition 逻辑；
- 把 quest success 包装成分数或“已掌握”；
- 缓存或记录原始儿童音视频/逐字话语用于调试；
- 以 demo 数据、HTTP 202 或按钮存在为依据宣称生产隐私完成。

