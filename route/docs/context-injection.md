# 上下文注入规范(FR-G03)

大臣切换(或同大臣续聊)时,调度层在调用大臣能力前按本规范拼装 **上下文注入包**
`ctx_bundle`。目标:切换大臣时剧情上下文保持率 100%(不串台),同时控制 token 成本。

## 注入包结构

```jsonc
{
  "intent": "memory",            // 本次命中的意图
  "minister": "ahai",            // 本次注入目标大臣
  "budget": 1500,                // 本次 token 预算
  "tokens_used": 863,            // 实际估算占用
  "script_state": {              // ① 剧本状态(最高优先级,永不裁剪字段键)
    "plot": "朝会", "scene": "金銮殿", "role": "小皇上", "act": 3
  },
  "recent_turns": [ ... ],       // ② 最近对话轮(≤10 轮,时间升序)
  "today_words": ["苹果", "菠萝"], // ③ 今日已学词(≤30 个)
  "emotion": {"valence": 0.6, "arousal": 0.4, "label": "happy"}, // ④ 孩子情绪分
  "notes": ["最近 3 轮对话因 token 预算被裁剪"]  // 裁剪/安全提示,大臣必须遵守
}
```

## token 预算分级

| 场景 | 预算 |
| --- | --- |
| 任务(朝会/记忆/学词/安抚/万物) | 1500 |
| 闲聊(chitchat) | 500 |
| 小P 反问澄清(clarify) | 300 |

预算在 `config/budgets.json` 配置,运营可调。

## 拼装与裁剪顺序

1. 固定头:`script_state` → `emotion`(预算内必保)。
2. `today_words`(取最近 30 个)。
3. `recent_turns`:从最新一轮往回装入,装不下即停;输出保持时间升序。
4. 极端情况下(单轮即超剩余预算):**强制注入最新一轮并截断文本**(带 `…` 标记),
   注入包永不出现空对话。
5. 每次裁剪都写入 `notes`,大臣侧可感知。

## 状态来源

- `script_state`:剧情引擎(01)经 dispatch 请求的 `script_state` 字段(merge 语义)推送。
- `recent_turns`:调度层维护的会话环形缓冲(40 轮),儿童/大臣各记一轮。
- `today_words`:随 `memory_write[]` 中 `kind=word_learned` 的写库回执自动登记,跨自然日自动清空。
- `emotion`:请求 `emotion` 字段(声学情绪分,ASR(02) 产出),经 `hook.emotion_detect` 归一化。

## 性能预算

注入包生成 ≤50ms(`ContextBuilder.latencyStats()` 观测 p50/p95,埋点 `ctx_built(tokens)`)。
路由 + 注入全流程 ≤100ms(不含 LLM 推理)。
