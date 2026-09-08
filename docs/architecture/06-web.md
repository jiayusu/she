# Web 端

> 浏览器指向验证、开发调试台、Agent Trace 与运营后台。
>
> 硬规则、组件归属与导航见仓库根 [`AGENTS.md`](../../AGENTS.md)。
> 本文各节沿用 AGENTS.md 原有编号，以保持既有交叉引用有效。

---

# 32. Web 端

Web 端不是儿童主要学习终端。

它承担三类职责：

```text
A. 浏览器版交互验证
B. 开发 / 调试 / Demo
C. 运营 / 审核后台
```

## 32.1 浏览器交互验证

现有 pointing 浏览器模块继续保留。

做什么：

- 手机 / 平板摄像头调用；
- MediaPipe 手势识别；
- YOLO 物体框；
- 指向确认；
- 浏览器版万物模式 MVP；
- 在 RX5 硬件完全稳定前验证交互。

它与硬件版使用相同的结构化输出契约：

```json
{
  "detected_object": "",
  "bbox": [],
  "pointing_confidence": 0.0,
  "confirmation_state": ""
}
```

因此：

```text
Web 摄像头
和
RX5 摄像头
```

只允许实现不同，不能产生两套上层 Agent API。

## 32.2 开发调试台

Web 调试端应能查看：

```text
当前 Session
当前学习目标
Learner Model 摘要
Curriculum Proposal
Scaffold Level
Story State
Assessment Result
Agent 调用顺序
LLM latency
fallback
memory write
KG retrieval
```

推荐页面：

```text
/debug/session/{session_id}
```

主要用于回答：

> “系统为什么刚刚说了这句话？”

必须展示结构化决策链，而不是只展示最终 LLM 输出。

## 32.3 Agent Trace

Web 调试端建议显示：

```text
Perception
↓
Learner Model
↓
Curriculum
↓
Scaffold
↓
Story
↓
Director
↓
Interaction
↓
Assessment
```

每一步至少显示：

```text
input summary
output
confidence
latency
fallback
```

不得默认显示敏感原始儿童音视频。

## 32.4 运营后台

Web 端还负责：

- KG 冲突审核；
- 外部内容审核；
- Prompt / Teaching Skill 版本查看；
- 模板管理；
- 数据情报周报；
- 系统指标；
- 回滚操作；
- 测试设备状态。

现有 `intel` 人工审核工作台属于这里。

KG 热更新必须：

```text
候选
→ Web 审核
→ approve
→ KG
```

## 32.5 Web 端不做什么

Web 端不得：

- 自己保存另一份 Learner Profile；
- 绕过服务端直接写 KG 数据文件；
- 绕过 store 直接改儿童记忆；
- 把调试 Prompt 暴露给儿童；
- 让浏览器版和硬件版形成两套教学逻辑。
