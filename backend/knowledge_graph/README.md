# KG 工作流 · 儿童英语知识图谱流水线

基于剑桥 YL 词表与 ConceptNet 构建儿童英语知识图谱(KG),支持嵌入检索与万级边热更新。
总流程:**收集(W1) → 整理筛选(W1-2) → 清洗(W2) → 建库(W2) → 嵌入检索(W3) → 热更新管线(W4)**

## 目录结构

```
backend/knowledge_graph/
├── README.md                  本文档
├── kg.py                      公共库: 建表/facts()/next_words()/GraphML/版本
├── cleaning.py                规则清洗层(被建库与热更链共用)
├── llm_client.py              LLM 层客户端(OpenAI 兼容, 环境变量配置)
├── build_kg.py                W2: 三层清洗 + 建库
├── kg_query.py                W2: 冒烟测试 + 万物模式演示
├── kg_embed.py                W3: RotatE 训练 / FAISS 索引 / PPR 扩散
├── server.py                  W4: 热更新管线 7 接口 + 万物模式 MVP
├── prompts/edge_review_v1.md  LLM 审边提示词(冻结版本)
├── scripts/
│   ├── make_seed.py           W1: YLE + CEFR-J → seed.csv
│   ├── fetch_conceptnet.py    W1: dump 下载(断点续传)
│   ├── filter_conceptnet.py   W1-2: 断言流式过滤 + 覆盖率报告
│   ├── turbo_clean.py         W2: LLM 批量审边(高吞吐)
│   ├── repair_coverage.py     W2: 覆盖不足词补边
│   ├── finish_pipeline.py     W2-3: 终跑链(报告刷新 → RotatE 训练 → FAISS 索引 → 抽样)
│   ├── sample_edges.py        W2 人工层: 抽样 50 条
│   ├── acceptance.py          验收红线总检查
│   └── _status.py             管线状态速查(开发用)
├── raw/                       原始文件(dump/词表, 不入库)
└── data/                      产物: seed.csv / kg.db / kg.graphml / embeddings/ / snapshots/ / reports/
```

> **产物目录只有 `data/`。** 代码中一律 `DATA = ROOT / "data"`(见 `kg.py`、`build_kg.py`、
> `server.py`),没有任何脚本读写 `kg/data/`。仓库里若存在 `kg/` 子目录,那是早期在错误工作目录
> 下运行管线留下的孤立副本,已不再跟踪(见下节)。

### 生成产物不入库

`data/` 下的 `kg.db`、`kg.graphml`、`embeddings/`、`snapshots/`、`reports/`、
`edges_candidates.csv.gz` 全部是**管线产物**,由 `.gitignore` 排除,不提交。
只有输入数据入库:`data/seed.csv`、`data/word_variants.csv` 与 `raw/` 下的词表。

重新生成全部产物(顺序即下方"复现步骤"W1 → W4):

```bash
python scripts/fetch_conceptnet.py     # W1   下载 ConceptNet dump(~475MB)
python scripts/make_seed.py            # W1   → data/seed.csv
python scripts/filter_conceptnet.py    # W1-2 候选边 + 覆盖率报告
python build_kg.py --seed data/seed.csv --out data/kg.db   # W2 规则层 + 建库
python build_kg.py --llm-clean         # W2   LLM 审边(需 API key; finish_pipeline 的前置)
python scripts/repair_coverage.py      # W2   覆盖不足词补边(每词 ≥2 边红线)
python scripts/finish_pipeline.py      # W2-3 终跑链: 报告 + 训练 + 索引 + 抽样
python server.py &                     # W4   起服务
python scripts/acceptance.py           # 验收红线实测
```

各步的参数与产物细节见下方"复现步骤"分节;LLM 层需要的环境变量见 W2 小节。

## 环境准备

```bash
python -m pip install -r requirements.txt   # numpy/scipy/torch/faiss-cpu/networkx/flask/requests
python server.py                            # 默认 127.0.0.1:8787，KG_PORT 可覆盖
```

本组件是扁平模块布局，顶层模块名很通用（`kg` / `server` / `cleaning` / `llm_client`），
因此 `pyproject.toml` **只提供工具配置，不声明可安装包**——发布这些名字会与
`backend/intel` 的同名模块冲突。

> **本组件目前没有自动化测试。** 只有手工验收脚本 `scripts/acceptance.py`（需先起
> `server.py`），也未纳入 `scripts/verify.ps1` 与 CI。补测试属独立工作，
> 见 `docs/IMPLEMENTATION_BACKLOG.md`。

## 复现步骤

### W1 收集

```bash
python scripts/fetch_conceptnet.py                 # ConceptNet 5.7.0 断言 dump (~475MB, S3 直下, 不走 API)
# 词表已随仓库: raw/yle-vocabulary-dataset.csv (剑桥 YLE 官方词表镜像)
#              raw/cefrj-vocabulary-profile-1.5.csv (CEFR-J 词表)
python scripts/make_seed.py                        # → data/seed.csv (2,536 词 ≥1,500 ✅)
```

seed.csv 三列 `word,level,pos`:YLE 词(Starters 495 / Movers 393 / Flyers 495)为权威来源,
CEFR-J A1/A2 内容词补充;同词多词性合并、义类括号(`band (music)`→`band`)归并、
英美拼写映射(`data/word_variants.csv`)、儿童安全政策排除词记录于 `data/reports/excluded_words.csv`。

### W1-2 整理筛选

```bash
python scripts/filter_conceptnet.py                # 34M 行断言流式过滤 → 候选边 + 报告
```

- 只保留 `/c/en/ → /r/<白名单关系> → /c/en/`,白名单 10 种:
  RelatedTo / UsedFor / HasProperty / AtLocation / MadeOf / CapableOf / PartOf / Synonym / FormOf / IsA
- 至少一端命中词表(含拼写变体归一),(head,rel,tail) 去重取最大权重
- 产出 45.1 万候选边;**覆盖不足词占比 1.5% ≤ 20% ✅**(报告: `data/reports/candidate_edges_per_word.csv`、`low_coverage_words.csv`)

### W2 清洗(三层)+ 建库

```bash
python build_kg.py --seed data/seed.csv --out data/kg.db     # 规则层 + 建库
python build_kg.py --llm-clean                               # LLM 层(需 API key, 见下)
python scripts/sample_edges.py -n 50                         # 人工层: 抽 50 条标注
python kg_query.py                                           # 冒烟测试
```

三层清洗:
1. **规则层**(`cleaning.py`):非英文/边长>40/自环/成人话题/品牌歧义(apple→computer)/
   常用词白名单(非词表一侧必须是词表∪CEFR-J 全级别词,淘汰 velocipede 类生僻概念)。
   第一轮人工抽检发现生僻概念边后按"加严规则"回路补充。
2. **LLM 层**(`build_kg.py --llm-clean`):批量审边,**只输出"要删的行"**,提示词冻结版
   `prompts/edge_review_v1.md`(错误常识/义项错位/成人义/无信息量,总原则"宁缺毋滥"),
   决策留痕 `data/reports/llm_clean_decisions.jsonl`。
   实际执行采用双模型夹击:推理模型(step-3.7-flash,id 正向,判删精细)+
   `scripts/turbo_clean.py` 无思考模型(step-1o-turbo-vision,id 反向,快速扫尾),
   决策分别留痕于 `llm_clean_decisions.jsonl` 与 `llm_clean_decisions_turbo.jsonl`。
   OpenAI 兼容接口,环境变量配置:
   ```bash
   export OPENAI_BASE_URL=https://api.stepfun.com/v1   # 任意 OpenAI 兼容端点
   export KG_LLM_API_KEY=sk-...
   export KG_LLM_MODEL=step-3.7-flash                  # 审边实测用模型
   ```
3. **人工层**:抽检 50 条标注 label(ok/bad),`scripts/acceptance.py` 复核错误率 ≤10% 放行;
   超标则回到规则层加严(本项目实际经历两轮:生僻概念 → 常用词白名单)。

产出:`data/kg.db`(SQLite,WAL)+ `data/kg.graphml`(Gephi 目视质检:apple 应与 fruit 同簇)。

### W3 嵌入检索

```bash
python kg_embed.py train --db data/kg.db --dim 100 --epochs 300   # RotatE (自对抗负采样)
python kg_embed.py index                                          # FAISS IndexIDMap2(IndexFlatIP)
python kg_embed.py query apple                                    # FAISS→PPR→带边溯源
```

- RotatE 底座(torch CPU):实体按行归一(复数能量 1),距离 ‖h∘r−t‖₂(RMS 尺度),
  自对抗负采样按行 softmax,尾实体破坏 + 已知三元组过滤(假负例会毒化 1-N 关系的几何)
- FAISS IndexIDMap2(IndexFlatIP)余弦近邻 + PPR 图扩散(多跳,α=0.15)融合排序(0.45·cos + 0.55·PPR)
- 图谱 <5,000 节点时自动退回 `kg.next_words()` 规则版(`--force-vector` 可强制)
- 实测:query apple 前 8 = red/fruit/green/pie/tree/pear/food/round(水果食物词 7 个);
  query fridge 前 8 含 food/kitchen/milk/butter/meat/cheese;端到端延迟 <20ms(预热后)

### W4 热更新管线(接口冻结)

```bash
python server.py          # 默认 127.0.0.1:8787, KG_DB/KG_PORT/KG_ONLINE_FALLBACK 可配
```

| 接口 | 方法 | 用途 |
| --- | --- | --- |
| `/kg/edges:batch` | POST | 批量加/删/改边;链:规则过滤→矛盾检测→IncLoRA 局部训练→FAISS 局部重建→版本+1 |
| `/kg/snapshot` | POST | 快照(SQLite backup API + 嵌入文件) |
| `/kg/rollback/{v}` | POST | 回滚(backup API 原地覆盖,Windows 文件锁安全),版本号单调递增;坏知识不过夜 |
| `/kg/packs/{level}` | GET | 按 L0-L5 打包 diff(含墓碑);`?rollout=10&device_id=` 灰度(md5 确定性分桶) |
| `/kg/runtime-consolidate` | POST | 阿海情景记忆共现词对 → 批量提升为语义边(走同一条热更链) |
| `/kg/conflicts` | GET | 矛盾边清单(反义词对/IsA 环/曾删边),人工审入口 `/kg/conflicts/{id}/resolve` |
| `/kg/retrieve` | POST | FAISS→PPR→LLM 重排(可选),返回带边溯源 |
| `/kg/facts/{word}` | GET | 万物模式 MVP:kg.facts() 本地优先,query_conceptnet() 在线兜底(KG_ONLINE_FALLBACK=1) |

IncLoRA 局部训练 = 冻结主干嵌入,仅对受影响实体行解冻若干梯度步(梯度掩码实现),
新实体用邻居向量均值冷启动接入 FAISS;FAISS 局部重建 = remove_ids 受影响向量后重加。
实测(验收演练):1 万边批量热更 24s 完成(红线 ≤5 分钟),期间健康探针最大间隔 0.43s(不停服),
回滚后坏知识不可见、版本号单调递增。

## 验收红线(度量表 #11)

```bash
python server.py &                      # 终端 1
python scripts/acceptance.py            # 终端 2: 全部红线实测
```

| 红线 | 结果 | 证据 |
| --- | --- | --- |
| W1 seed ≥1,500 词 | ✅ 2,536 词 | data/seed.csv |
| W1-2 覆盖不足词 ≤20% | ✅ 1.5% | data/reports/low_coverage_words.csv |
| 每词 ≥2 条知识边 | ✅ 见 data/reports/kg_coverage.csv | acceptance.py 实测(例外清单 kg_low_coverage.csv,为语法功能短语/人名,ConceptNet 无知识边) |
| 抽检 50 条错误率 ≤10% | ✅ | data/reports/manual_sample_50.csv(标注: label 列) |
| query apple 前8 ≥3 水果/食物词 | ✅ | acceptance.py 实测 |
| query fridge 含 kitchen/cold/food | ✅ | acceptance.py 实测 |
| 万物模式端到端 ≤2s | ✅ | /kg/facts 与 /kg/retrieve HTTP 实测 |
| 万级边热更 ≤5min、不停服、可回滚 | ✅ | acceptance.py: 1 万边批量 + 探针 + 快照/回滚演练 |

## 数据与版权说明

- ConceptNet 5.7.0 断言:CC BY-SA 4.0(conceptnet.org)
- Cambridge YLE 词表镜像(yle-vocabulary-dataset):仅作教研用途
- CEFR-J Vocabulary Profile:CC BY-SA 4.0
