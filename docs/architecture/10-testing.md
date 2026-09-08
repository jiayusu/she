# 测试要求

> 各 Agent 必须覆盖的测试项。
>
> 硬规则、组件归属与导航见仓库根 [`AGENTS.md`](../../AGENTS.md)。
> 本文各节沿用 AGENTS.md 原有编号，以保持既有交叉引用有效。

---

# 26. 测试要求

新增 Agent 不能只测试“LLM 回答看起来不错”。

至少测试：

## Interaction Agent

- Recast 不直接指出错误；
- language_level 句长限制；
- 无空响应；
- approved facts 之外不生成事实型万物回答。

## Learning Director

- 每轮只有一个 primary goal；
- 情绪风险覆盖课程推进；
- 低置信 assessment 不产生 confirmed memory write；
- 多 Agent 冲突有确定优先级。

## Learner Model

- 单次错误不直接降级 mastery；
- repeated evidence 才 confirmed；
- spontaneous evidence 权重大于 prompted evidence。

## Curriculum

- 不超出 language_level；
- i+1；
- 到期复习优先；
- 当前物体与学习目标相关。

## Scaffold

- 连续失败提高 scaffold；
- 连续成功降低 scaffold；
- 抗拒时允许只输入不要求输出。

## Story

- 不改变教学目标；
- 跨天 StoryArc 可恢复；
- 世界反馈与儿童开口行为绑定。

## Assessment

- 区分 spontaneous / prompted；
- 低 ASR 置信度降低 assessment_confidence；
- 不直接修改长期状态。
