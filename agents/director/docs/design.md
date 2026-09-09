# 设计说明(03 五大臣 Agent 调度)

运行与测试见 [`../README.md`](../README.md)。
历史 PRD（已归档，非权威）：[`docs/archive/prd/director-prd-v1.md`](../../../docs/archive/prd/director-prd-v1.md)

## 定位

BMAM 论文架构的产品化翻译层:**决定"这句话归谁管、带多少上下文、往哪里写记忆"**,
防止"阿海和老颞各记各的"的记忆碎片化(soul erosion)。本模块不含大臣能力实现、
记忆存储 Schema(04)、剧情引擎内部逻辑(01)——这些通过接口边界解耦。

## 五大臣(领域映射)

| 大臣 | 脑区隐喻 | 职责 | 归属记忆库 | 主责意图 |
| --- | --- | --- | --- | --- |
| 小P | 前额叶 | 总调度 / 澄清 / 闲聊 / 元认知 | working | chitchat |
| 阿海 | 海马体 | 情景记忆 / 剧情回忆 | episodic | memory |
| 老颞 | 颞叶 | 学词 / 万物知识 / KG | semantic | word, object |
| 杏杏 | 杏仁核 | 安抚 / 情绪 / 显著性 | affective | comfort |
| 小脑 | 小脑 | 朝会仪式 / 程序流程 | procedural | court |

> PRD 点名了四位大臣;第五位按"朝会=仪式性程序流程"的职能取"小脑"。
> 映射全部在 `config/minister-map.json`,运营可随时改名/改映射,无需动代码。

## 请求生命周期(dispatch 管线)

```
ASR 文本+情绪分
  │
  ├─ hook.injection_detect ─┐
  ├─ hook.emotion_detect    ├─ 系统钩子,强制,不可绕过(FR-G08)
  ├─ hook.content_filter ───┘
  │
  ├─ FR-G01 意图分类(词法评分+情绪加权+softmax)→ 意图+置信度
  │     └─ 低置信 → 小P反问澄清(clarify 预算 300)
  ├─ FR-G02 映射表解析(主大臣 → 备选链 → 兜底小P)
  ├─ FR-G03 上下文注入包(剧本状态/最近10轮/今日已学词/情绪分,预算 500/1500)
  ├─ FR-G04 memory_write[] → 显著性打标(FR-G05)→ KG 事实校验 → 五库写入
  │     └─ 失败重试 1 次 → 死信队列 + WS/审计告警
  ├─ 会话更新(值守大臣/对话轮/情绪/今日已学词)→ 快照落盘(崩溃恢复)
  └─ 审计(路由理由/注入摘要/写库结果)+ 埋点
```

全程无 LLM 调用;路由+注入 ≤100ms(实测 p95 数 ms)。

## 关键设计决策

- **意图分类器为词法+情绪混合规则引擎**(FR-G01):不依赖模型推理,确定性、可审计、
  满足 ≤100ms 预算;词典/权重在 `config/lexicon.json` 运营可调,每月盲测集扩容
  (风险对策)只需加样本进测试集。置信度 = softmax 主类概率 × ASR 置信度折减。
- **映射表带备选链与 `*` 通配**(FR-G02):安抚可被任何大臣降级执行;主大臣降级
  (运维标记或健康检查)时按序取备选;全部不可用兜底小P,绝不空转。
- **记忆写入前置事实校验**(风险对策):`semantic` 库的 fact 写入先对 KG 查冲突,
  冲突 → 待审队列(`POST /admin/kg/pending-review/:id/resolve`),不直接固化,
  防"错误记忆固化"。
- **白名单只增不删**(FR-G05):`NeverForgetWhitelist` 类不提供任何删除方法,
  测试断言之;剪枝作业对白名单条目豁免。
- **巩固是两阶段**(FR-G06):每周自动产 draft 报告(孩子无感知),人工一键确认才
  热更新 KG —— 对应"diff 报告,人工一键确认后生效"。
- **遗忘剪枝 = EMA 式置信度衰减**(FR-G07):`salience·e^(-λ·闲置天数)`,低于地板
  删除,整天粒度计闲;白名单豁免。
- **崩溃恢复**(非功能):会话快照 50ms 防抖写 `data/snapshots/`,启动
  `recover()` 全量重建(实测 ~5ms,远低于 2s);"首次行为"集合从情景库回放,
  重启不会把旧行为当首次。

## 目录结构

```
src/
  intent.ts          FR-G01 意图分类器 + 澄清话术
  mapping.ts         FR-G02 映射表(加载/校验/热加载/降级解析)
  context.ts         FR-G03 注入包(预算裁剪)
  memory-write.ts    FR-G04 写调度(重试/DLQ/事实校验)
  salience.ts        FR-G05 显著性规则引擎
  consolidation.ts   FR-G06 巩固(扫描/diff/确认)
  metacognition.ts   FR-G07 三 agent + 调度器
  hooks.ts           FR-G08 工具边界网关 + 强制钩子
  session.ts         会话状态 + 快照恢复
  app.ts             应用容器 + dispatch 管线
  server.ts          HTTP + WS
  config.ts          配置加载与兜底默认值
  stores/local.ts    五库适配器(内存+JSONL,可注故障)+ 白名单
  stores/kg.ts       语义 KG(热更新/冲突/待审)
test/                66 用例:8 条 FR 验收 + 非功能 + e2e(HTTP/WS)
docs/                tool-boundary / context-injection / api / design
config/              运营可改:映射表 / 词典 / 预算 / 显著性参数
```

## 与兄弟模块的边界

| 模块 | 边界 |
| --- | --- |
| 01 剧情引擎 | 经 `POST /agent/dispatch` 推 `script_state` 与 `memory_write[]`;本模块回 `minister`+`ctx_bundle` |
| 02 ASR | `asr`(识别文本置信度)+ `emotion`(声学情绪分)字段 |
| 04 记忆存储 | `MemoryStoreAdapter` 接口(五库)+ `SemanticKG.hotUpdate`(热更新)+ 白名单;本仓库提供内存/JSONL 实现,替换为 04 时仅换适配器 |
| 05 内容安全 | `hook.content_filter` 词表为最小实现,完整实现在 05;边界与调用点固定于 `ToolGateway` |
