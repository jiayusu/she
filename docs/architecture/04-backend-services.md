# 确定性后台服务

> 指向识别、知识图谱后台、数据情报后台三个确定性服务的职责与红线。
>
> 硬规则、组件归属与导航见仓库根 [`AGENTS.md`](../../AGENTS.md)。
> 本文各节沿用 AGENTS.md 原有编号，以保持既有交叉引用有效。

---

# 13. 指向识别模块

路径来源：当前 Pointing 浏览器模块。

## 做什么

识别：

> **孩子当前指的是哪个现实物体。**

流程：

```text
触发
→ 5 帧采集
→ MediaPipe 手势识别
→ YOLO 物体检测
→ 射线选物
→ 置信度判断
→ 必要时确认
→ detected_object
```

关键规则：

- ≥3 帧命中：轻确认；
- 1–2 帧：重确认；
- 0 帧：中心框兜底；
- 最多 2 轮确认；
- 指向窗口结束必须关闭摄像头；
- 原图默认不落盘。

输出进入：

```text
Learning Director
Curriculum Agent
Story World Agent
```

它不是 Agent，不负责生成课程。

---

# 14. KG 后台

目录：

```text
kb/
```

## 做什么

KG 是：

> **儿童可用、可审查、可回滚的通用英语知识和课程约束层。**

负责：

- YLE / CEFR-J 词表；
- ConceptNet 知识关系；
- 清洗；
- 嵌入；
- 检索；
- 万物事实；
- 热更新；
- 冲突检测；
- snapshot / rollback。

关键接口：

```text
POST /kg/edges:batch
POST /kg/snapshot
POST /kg/rollback/{v}
GET  /kg/packs/{level}
POST /kg/runtime-consolidate
GET  /kg/conflicts
POST /kg/retrieve
GET  /kg/facts/{word}
```

### KG 不负责

- 保存某一个孩子的私人学习画像；
- 保存聊天全文；
- 决定孩子今天练什么；
- 决定脚手架等级；
- 自由从互联网补知识。

---

# 15. 数据情报后台

目录：当前 `intel` 模块。

## 做什么

数据情报只服务：

- 内容运营；
- 家长痛点研究；
- 万物模式知识池；
- 舆情监控。

流程：

```text
外部内容
→ 抓取
→ 排序/去重
→ LLM 结构化
→ 敏感内容过滤
→ 人工审核
→ KG
```

### 架构红线

```text
外部搜索
≠
儿童实时 Agent Tool
```

任何外部互联网内容进入儿童产品前必须：

```text
结构化
→ 人工审核
→ KG 热更新
→ 可回滚
```

不得：

```text
儿童问一句
→ Agent 即时搜索知乎/互联网
→ 直接回答儿童
```
