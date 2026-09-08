# DESIGN · LLM 剧情引擎实现说明（对应 PRD 01 · V1.0）

> 本文回答三个问题：每个 FR 落在哪个模块、关键决策为什么这么定、怎么跑验收。

## 1. 目录结构

```
engine/
├── README.md                  # PRD（原文，未改动）
├── docs/design.md             # 本文
├── pyproject.toml
├── src/she_engine/
│   ├── types.py               # PRD §6 接口契约：TurnRequest/TurnResponse/MemoryWrite/六意图/五大臣常量
│   ├── engine.py              # 主编排（一次开口→一次回应的完整链路）
│   ├── router.py              # FR-E02 规则+轻量模型路由（含 60 条标注评测集）
│   ├── schema.py              # FR-E06 输出 Schema 解析/修复/重试
│   ├── recast.py              # FR-E04 Recast 指令编译 + 打断式纠错检测 + 确定性兜底
│   ├── levels.py              # FR-E05 L0-L5 句长上限/词汇池/中文脚手架
│   ├── state_machine.py       # FR-E03 朝会→探险→睡前 + 跨天续接
│   ├── context.py             # FR-E08 上下文拼装（≤1500 token，按优先级截断）
│   ├── stuck.py               # FR-E09 连续卡壳检测 → 降 L + parent_note
│   ├── prompts.py             # FR-E01/FR-E10 大臣注册表（版本化冻结 + DLC 热注册）
│   ├── templates.py           # FR-E07 兜底模板库（场景命中 + 轮转避重）
│   ├── llm.py                 # Provider 抽象：OpenAI兼容/Mock/Flaky/Garbled/Cached
│   ├── memory.py              # 记忆存储适配器（04 模块接口 + InMemory/File 参考实现）
│   ├── safety.py              # 内容安全挂钩（05 模块接口 + 本地保底过滤）
│   └── events.py              # PRD §8 埋点（routed/recast/fallback/latency/stuck/cost）
├── assets/
│   ├── ministers/<id>/v1.yaml # FR-E01 冻结提示词 + FR-E10 三件套（voice_id/light_color）
│   └── templates/<id>.yaml    # FR-E07 模板：5 大臣 × 56 条 = 280 条
├── tests/                     # 逐 FR 验收测试（pytest，103 条）
├── scripts/validate_assets.py # CI 首跑资产校验
└── examples/demo.py           # 离线全流程演示（含拔网线）
```

## 2. FR → 实现映射与验收方式

| FR | 实现 | 验收（tests/） |
|---|---|---|
| E01 人格提示词 | `assets/ministers/*/v*.yaml` 冻结版本；`MinisterRegistry` 按版本加载、可 pin/rollback；渲染后残留占位符即报错（写错立刻暴露） | `test_prompts.py`：五人格注册、三件套完整、渲染校验、回滚 |
| E02 查询路由 | `RuleClassifier`（中英正则加权打分）+ `HybridClassifier`（规则置信度<0.72 时回调可插拔轻量模型，模型挂了自动回落）；上游可 `route_intent` 强制路由 | `test_router.py`：60 条标注集 **100%**（红线 ≤10% 错误）、六类意图覆盖、闲聊按剧本状态路由 |
| E03 剧本状态机 | `ScriptState` 纯数据快照持久化到记忆存储；`advance()` 只在实质开口时调用（沉默/重邀不推进）；`resume_for_today()` 跨天接续并产出 recap 注入本轮 prompt | `test_state_machine.py` + `test_engine_e2e.py::test_restart_resumes_story`：同天重启进度原样接续、跨天 recap「昨天讲到哪」 |
| E04 Recast | 评估结果（corrected/error_type）编译成 `RECAST MODE` 指令注入；三重防线：提示词铁律 → `detect_error_pointing()` 后置扫描（违规视同无效输出走重试链）→ `template_recast()` 确定性兜底 | `test_recast.py`：7 类打断式纠错话术全部拦截、Recast 样例零违规；用户故事 1 输出逐字复现 |
| E05 分级句式 | `LevelRules.to_prompt()` 注入上限/词汇池/脚手架；`fit_text_to_level()` 确定性收敛（单句超限截词、句数超限丢弃）；验收口径=单句（"I like apples too! Apples are sweet." 每句 ≤5 词） | `test_levels.py`：L1≤5/L2≤10/L3+≤16、啰嗦模型输出也被收敛 |
| E06 Schema | `extract_json_blob`（剥围栏/平衡大括号）→ 校验+就地修复（emotion 归一、坏 memory_write 剔除、speaker 拉回路由大臣）→ 失败重试 1 次 → 模板 | `test_schema.py` + e2e `test_retry_once_then_template`（恰好重试 1 次） |
| E07 兜底模板 | 5×56=280 条手写 YAML；`pick()` 场景命中优先选插槽齐备条目 + 轮转避重；冠词 a/an 自动修正 | `test_templates.py`：≥50/人、三类场景覆盖、全量可渲染；e2e 拔网线/乱码 provider 回应率 100% |
| E08 上下文 | `build_ctx_block`：剧本状态+已学词必保，最近 10 轮从最旧丢弃直至 ≤1500 token（中英混排估算器）；上游 `ctx_bundle` 优先，缺省自查记忆存储 | `test_context_stuck.py`：大历史压到预算内、状态/词永不被截丢 |
| E09 降L | `StuckTracker`：无实质话语/ASR 低置信/过短 → streak+1；**连续第 2 次**降一级（下限 L0，只降一次防连坐）；写 `parent_note`；发 `engine_stuck` 埋点 | `test_context_stuck.py` + e2e：链路可观测（埋点+note+meta） |
| E10 DLC | 丢一个 YAML（id/voice_id/light_color 三件套+人格）进 `assets/ministers/<id>/` → 自动注册；`route_overrides` 配置可让新大臣接管某意图；坏文件进 `load_errors` 不炸主链路 | `test_prompts.py::test_dlc_registration_without_code_change` |

## 3. 关键决策

1. **五大臣与六意图的映射**（PRD 未定死，按兄弟模块文档中出现的角色定名）：

   | 意图 | 大臣 | 依据 |
   |---|---|---|
   | 朝会任务 | 小P（企鹅小管家） | PRD 用户故事 2 小P负责重邀，朝会主持归它 |
   | 记忆询问 | 阿海（老海獭） | kb 手册 W4「阿海情景记忆」 |
   | 学词 | 杏杏（杏色小鹦鹉） | PRD 用户故事 1 杏杏做 Recast |
   | 情绪安抚 | 阿海 | 记忆+情绪同管家（安抚要引用共同记忆） |
   | 万物 | 王冠 | po 手册「王冠说你是想问冰箱吗」 |
   | 闲聊 | 按剧本状态：朝会→小P / 探险→老颞 / 睡前→阿海 | 老颞接续「昨天讲到哪」出自 PRD FR-E03 验收 |

2. **句长上限按「单句」而非「整段」计**：PRD 用户故事 1 的回答 "I like apples too! Apples are sweet."（4+3 词）与 FR-E05 的 L1≤5 词只有按单句口径才同时成立。

3. **Recast 的正确形式来自 ASR 评估结果**（02 模块的 corrected/target_form），引擎不自行做语法纠正——架构上 02 评估器才是权威，引擎负责「翻译成人格化输出」并守住「绝不指出错误」红线。

4. **静默也算卡壳**：空输入/纯标点走小P重邀且计入 FR-E09 连续卡壳；重邀轮**不推进**剧本（开口是唯一推进条件的反面）。

5. **级别归引擎所有**：默认只在首轮采纳上游 `level`，此后由引擎管理（降级不被上游陈旧值顶回）；`follow_request_level=True` 可切回上游主导。

6. **降级只降一次**（连续第 2 次触发）：避免持续沉默的孩子被一路压到 L0 失去内容。

7. **不空响应的三层保险**：LLM 挂/超时 → 重试 → 场景模板 → 硬编码句；安全拦截同样落到模板。任何 `TurnResponse.text` 非空是 e2e 断言。

8. **成本护栏**：`CachedProvider` 精确 prompt 缓存（万物/朝会高频问法命中零成本）+ 会话成本累计超 ¥0.02 发 `engine_cost_warn`；万物意图强制注入 `kg.facts`（kb 模块接入点），没有事实就答不了——幻觉从入口被卡住。

## 4. 接口（与 PRD §6 一致）

```python
from she_engine import Engine, EngineConfig
from she_engine.llm import OpenAICompatProvider

engine = Engine(EngineConfig(
    provider=OpenAICompatProvider(base_url="https://…/v1", api_key="…", model="…"),
    memory=FileMemoryStore("data/child_001"),   # 换成 04 模块的实现即可
    kg_lookup=kg.facts,                          # kb 模块的 KG 检索
    session_level=1,
))

out = engine.turn({
    "child_utterance": "I like apple",
    "asr_result":   {"text": "I like apple", "confidence": 0.92},
    "assess_result": {"has_error": True, "original": "I like apple",
                      "corrected": "I like apples", "error_type": "plural", "word": "apple"},
    "level": 1,
    "route_intent": "",            # 空=引擎自行路由
    "ctx_bundle": None,            # 空=引擎自查记忆存储
})
out.to_dict()   # → {speaker, text, emotion_tag, memory_write[]}  ← TTS/上游只读这个
out.meta        # → intent/minister/voice_id/light_color/state/latency/… （调度与硬件用）

engine.handle_silence("apple")   # 上游 10 秒静音定时器触发
```

埋点：`engine_routed(intent, minister)` / `engine_recast(assess_used)` /
`engine_fallback(template_hit)` / `engine_latency(ttft, total)` +
`engine_stuck(streak, level, downgraded)`（FR-E09 可观测）+
`engine_cost_warn(session_yuan)`（成本护栏）。接线上：`EngineConfig(event_sink=CallbackSink(...))`。

## 5. 跑验收

```bash
cd engine
python -m pytest tests/ -q        # 103 条全绿
python scripts/validate_assets.py # 资产/模板/路由/分级四道校验
python examples/demo.py           # 离线全流程演示（含拔网线）
```

## 6. 已知边界（对齐 PRD Out-of-scope）

- ASR/评估本身（02）、记忆读写实现（04）、安全过滤实现（05）只接适配器；`OpenAICompatProvider` 是线上 LLM 的参考接入，超时 2s 即降级（对应首 token ≤800ms P95 的红线策略，真实阈值由压测定）。
- 路由「轻量模型」在 V1 是可插拔 callable；规则层已在标注集达到 100%，模型层留给线上灰度。
- 每周人格盲测、模板占比 >30% 报警的**报表侧**不在本模块（埋点已备齐字段）。
