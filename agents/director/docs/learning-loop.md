# 第一阶段：学习导向 Agentic Loop（已实现）

本页描述实际代码；外部框架比较与后续设计见
`docs/architecture/11-agentic-loop-design-reference.md`（仓库根相对路径）。

## 解决的问题

旧的 `direct` 先选下一轮目标，再评估当前回答，可能将上一轮 milk 的回答拿去对照新的 apple。
同时评估使用了下一轮提示等级，而不是上一轮服务端选择的等级。新实现先读取上一轮规划上下文，
完成评估后再做下一轮选择。这里的“上一轮”是服务端返回的计划，尚不代表设备已 ACK 执行。

## 实际顺序

`input → assessment → curriculum → scaffold → story → decision`。

`LearningLoopHooks` 对每个阶段执行前核对顺序、执行后记入 trace；重复或越序立即报错。
一次请求最多六个阶段，不自动递归、不调用外部 Hook、不创建新的 LLM 子进程。
只有明确的新请求驱动下一轮。Hook 不接受自由文本命令，不替代 `hooks.ts` 的强制边界。

## 教学行为

- 首次接触只建立任务，不对尚未发出的目标打分。
- 对上一轮目标评估后才决定下一轮目标，沿用上一轮服务端选择的提示等级。
- 不成功时保持目标、增加帮助；连续两次未成功后 pause，帮助等级 S6，只听参与。
- ASR 低于 0.8 或缺少置信度时不评估、不计失败、不建议记忆更新，返回 reinvite。
- 暂停后的空/不清楚输入保持暂停；新的非空、高置信输入恢复探索，失败计数清零。
- 情绪暂停优先，不将该回合当作失败，不更改传入的 Learner Profile。
- 成功时建议推进剧情，记忆策略最多为 candidate；不会自行确认 mastery。

阈值 0.8、两次尝试、15 分钟会话过期和最多 1000 个临时会话是本次明确的保守工程默认值，
不是经过真实儿童实验验证的最优教学参数。过期/容量淘汰后按首次接触处理，不伪造连续记忆。

## API 与共享契约

`POST /agent/direct` 原请求字段不变；响应新增 `learning_loop`，对应
`shared/contracts/v1/learning-loop.schema.json`。有效/无效 fixtures 与验证脚本已同步。

```json
{
  "version": "1.0",
  "trace_id": "synthetic-trace",
  "assessed_target": null,
  "failed_attempts": 0,
  "reason": "first_contact",
  "stages": ["input", "assessment", "curriculum", "scaffold", "story", "decision"],
  "state_scope": "session_only",
  "memory_write": "not_performed"
}
```

App 记录 metadata 审计：trace、阶段、原因、失败次数；不将儿童原话加入新 trace。
`learning_event_id` 不再由该入口生成，因为不再调用旧的本地 JSONL 学习记录 fallback。
`learningEvents` 兼容组件没有删除，但新 `direct` 不再将其作为长期学习存储。
这是有意的行为修正：候选策略不等于已保存证据。正式写入必须另接 Shared State API。

## 实现文件

- `agents/director/src/learning-director.ts`：会话内上轮上下文、评估顺序、两次尝试、暂停恢复。
- `agents/director/src/learning-loop.ts`：固定生命周期与类型化 trace。
- `agents/director/src/app.ts`：实际 HTTP 调用链与 metadata 审计，停止旧 JSONL fallback 写入。
- `agents/director/src/types.ts`：响应新增字段；不改变既有别名。

## 验证

`agents/director/test/learning-loop.test.ts` 覆盖：前一目标/提示等级、首次不评分、两次失败、
低置信、会话隔离、暂停恢复、过期/容量、Hook 顺序、情绪优先、真实 HTTP 与不写原话文件。
新增首批五个测试先观察到失败；实现后 Director 全部 76 测试通过，TypeScript 检查通过。
Shared contracts 14 测试通过，fixtures 验证通过。

```sh
npm test --prefix agents/director
npm run typecheck --prefix agents/director
python -m pytest shared/contracts/tests -q
python shared/contracts/validate_contracts.py
```

## 尚未实现，不能混淆

- 没有设备 ACK/真实提示执行关联；Interaction 改写帮助方式后的实际评估仍需执行证据。
- 没有 turn_id 重放去重，网络重复请求可能被当作新回合；生产适配必须补稳定事件标识。
- 会话 ID 需要部署层鉴权与家庭范围约束；这里不是多租户授权系统。
- 临时上下文不持久化、不跨多实例共享；重启即失效。
- 既有 Assessment 是简化评估器，未修改它的固定判定规则；通过单元测试不等于发音评估已完善。
- 没有新的子 Agent 并行、外部 Hook 插件、异步取消执行器、Shared State 写回或家长报告联动。
- 本地 Compose 仍只部署 Web/Gateway；Director 源码已修改并经真实 HTTP 测试，未加入该 Compose。

这些是后续设计文档的阶段 B–E 工作，不在此次第一阶段完成声明内。
