# 工具边界清单(FR-G08)

> 本清单为代码级契约,由 `test/hooks.test.ts` 自动校验:文档中必须列出全部 MCP 工具与系统钩子。
> 机读版本:`GET /admin/tools`。

## 原则

1. **MCP tool-call**:LLM 在大臣能力执行期间可自主调用的工具,一律走白名单注册
   (`ToolGateway.register`),未注册即拒绝。
2. **系统钩子**:内容安全与情绪链路是**系统层强制管线**,在 dispatch 进入 LLM 之前 /
   离开 LLM 之后由服务端代码无条件执行;不注册为工具、不出现在任何工具列表、
   LLM 以任何工具名调用一律抛 `ToolBoundaryError`(HTTP 侧 403)。
3. 钩子**不可被提示词注入绕过**:请求参数(如 `disable_hooks`)被直接忽略;
   注入话术命中 `hook.injection_detect` 规则只标记安全态,不会改变钩子执行路径
   (边界在代码层,不在提示词层)。
4. 带 `hook.` 前缀的工具注册请求直接被拒绝,防止伪装。

## MCP 工具(LLM 可调用)

| 工具名 | 说明 | 读写 |
| --- | --- | --- |
| `kg.query` | 查询语义知识库某主体的事实(老颞) | 只读 |
| `kg.related_words` | 查询已巩固的语义词表(老颞) | 只读 |
| `schedule.reminder` | 登记日程提醒(写入 working 库,由小P执行) | 写(working) |

## 系统钩子(LLM 不可见、不可调用、不可关闭)

| 钩子名 | 作用 | 执行时机 |
| --- | --- | --- |
| `hook.injection_detect` | 提示词注入检测:命中正则规则 → 标记安全态并写入注入包 notes | dispatch 输入侧,强制 |
| `hook.emotion_detect` | 情绪检测:归一化声学情绪分(valence/arousal/label)入会话与注入包 | dispatch 输入侧,强制 |
| `hook.content_filter` | 内容过滤:输入与输出双向过滤敏感词(词表对接 05 内容安全钩子) | 输入侧 + 输出侧,双向强制 |

## 调用约定

- LLM/大臣能力 → 工具:`ToolGateway.llmInvoke(name, args)`;`name ∈ SYSTEM_HOOKS` 时抛
  `ToolBoundaryError`,未注册名称抛"未知 MCP 工具"。
- 系统 → 钩子:仅 `runInputHooks()` / `runOutputHooks()` 两条路径,均为 dispatch
  管线内固定调用,与 LLM 输出无关。
- 审计:每次 `tool_invoke`(放行/拦截)写 `data/audit/`,拦截事件可在
  `GET /admin/audit?type=tool_invoke` 审查。
