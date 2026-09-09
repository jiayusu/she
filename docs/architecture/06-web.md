# Web 端

> 本文区分现有 Web 产品、浏览器感知工具与目标态调试台。硬规则、组件归属与导航见仓库根
> [`AGENTS.md](../../AGENTS.md)；RPG 对外只读契约见 [`08-contracts.md](08-contracts.md)。
>
> 当前 RPG 代码尚未执行本轮完整验证；Web 任务/调试 UI 仍未实现。

---

# 32. Web 端

仓库里存在三类 Web surface，不能把它们混写成一个已经完成的后台：

| Surface | 代码位置 | 当前事实 |
|---|---|---|
| 家长 Web | `clients/web` | 已有 Today/Report/Device/Family 页面，读取 Gateway；当前主要是演示数据 |
| 浏览器 pointing | `backend/pointing/web` | 有摄像头、手势/物体与确认相关前端代码；本轮未验证，也未接成 RPG quest UI |
| 数据审核 Web | `backend/intel/web` | 属于离线内容/运营链；不得进入儿童实时回答 |

目标态还需要第四类 surface：面向开发者的 RPG quest/debug/Agent Trace。当前仓库没有
`/debug/session/{session_id}` 页面，也没有消费 `rpg-quest-summary` 的 Web UI。

## 32.1 当前家长 Web

`clients/web` 是 React 家长端，现有页面包括：

~~~text
今天
成长记录
我的设备
家庭计划
亲子共看任务预览
~~~

它调用 Device Gateway 的 dashboard、weekly report、device、parent constraints 和 privacy
端点，不复制 Director/Assessment/mastery 逻辑。当前 Gateway 默认使用 `DemoRepository`，
页面也会明确展示“体验版/示例家庭”。

“亲子共看”目前只是 dashboard task 的静态预览：

- 不调用 `GET /v1/rpg/state`；
- 不展示 `node_id`、`phase`、`world_revision`、inventory 或 delivery；
- 不发送 `object_observed/speech/resume`；
- 不开启摄像头或录音；
- 不是现实语言 RPG 的可操作任务卡。

## 32.2 浏览器指向验证

浏览器与 RX5 必须共用同一上层感知契约，不能让前端直接构造世界成功。目标感知摘要类似：

~~~json
{
  "detected_object": "fridge",
  "bbox": [],
  "pointing_confidence": 0.92,
  "confirmation_state": "confirmed"
}
~~~

`backend/pointing/web` 可作为浏览器感知实验入口，但“存在前端代码”不等于已经与 Gateway
`POST /v1/rpg/direct` 完成身份、事件顺序和摄像头生命周期集成。本轮没有运行浏览器或真实相机
验证，不能把它写成完成的 RPG 输入端。

摄像头仍必须由显式事件开启，成功/失败后关闭；Web 只能提交确认后的结构化感知事件，不能提交
`confirmed_object`、world patch 或 quest success。

## 32.3 待实现：Quest UI

Gateway 已提供只读后端能力：

~~~text
GET /v1/rpg/state?child_id=...&session_id=...&turn_id=...
~~~

未来 Web quest card 应解码共享 `rpg-quest-summary.schema.json`，只展示：

~~~text
seed/version
current node and phase
virtual inventory
completed nodes
confirmed object summary
world role
prompt/feedback content references
next quest
delivery status
~~~

推荐状态呈现：

| phase | UI 含义 | 可用动作 |
|---|---|---|
| `seeking_object` | 正在寻找现实线索 | 引导显式感知 |
| `confirming_object` | 识别不确定 | 请求确认，不宣布成功 |
| `presenting` | 提示待执行/播放 | 等待 delivery |
| `awaiting_speech` | 提示已完成 | 等待设备侧语音 |
| `delivery_failed` | 播放失败或过期 | 显示可恢复，不推进世界 |
| `paused` | 儿童自愿暂停 | 只允许显式 resume |
| `completed` | 有限任务完成 | 展示虚拟成果 |

该页面不得显示儿童逐字原话、Speech Act evidence、内部 assessment、request hash、原始音视频或
完整 Memory response。它也不能提供 world/mastery 编辑按钮。

## 32.4 待实现：开发调试台与 Agent Trace

目标调试页仍建议使用：

~~~text
/debug/session/{session_id}
~~~

但它目前不存在。实现后应回答“系统为什么刚刚说了这句话”，至少显示经过脱敏的：

~~~text
accepted perception/input metadata
→ authoritative prior state and delivery
→ Speech Act decision
→ Curriculum / Scaffold / Story / Assessment proposals
→ Director's one TeachingAction
→ Memory commit/revision
→ Interaction render result category
→ Gateway command/ACK
~~~

每一步至少包含状态、confidence、latency、fallback/error 与稳定 trace ID。调试权限必须与家长
产品权限隔离，默认不暴露儿童原始音频、图像或逐字原话。

## 32.5 运营/审核后台

目标职责包括 KG 冲突审核、外部内容审核、Prompt/StorySeed/Teaching Skill 版本查看、模板管理、
系统指标与回滚。现有离线内容页面位于 `backend/intel/web`；它与儿童实时链路严格隔离。

知识发布仍必须经过：

~~~text
候选
→ 规则校验与冲突检查
→ 人工审核
→ backend/knowledge_graph
~~~

不能因为存在审核页面代码就声称完整权限、审批审计和生产发布流程已验收。

## 32.6 当前隐私状态

家长 Web 有导出/删除的演示交互，但 Gateway 当前明确返回：

~~~json
{
  "status": "accepted_demo_only",
  "mock": true,
  "store_mutated": false
}
~~~

因此真实身份认证、数据范围预览、可下载导出、Memory erase 调度与完成证明均未实现。页面必须
继续标明演示性质，不能把 HTTP 202 写成真实数据已经导出或删除。

## 32.7 Web 端硬边界

Web 端不得：

- 保存另一份 Learner Profile 或自行推导 mastery；
- 直接写 `backend/knowledge_graph` 或 Memory 数据文件；
- 调用 Memory 内部 learning commit 绕过 Director/Gateway；
- 把 `rpg-quest-summary` 反向当作可写 world state；
- 在浏览器版复制 Speech Act、StorySeed transition 或 scaffold 业务逻辑；
- 把调试 Prompt、原始儿童数据或内部 trace 暴露给儿童；
- 从开放互联网实时生成儿童回答。

