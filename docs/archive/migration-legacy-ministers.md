> **归档 · 历史文件 · 非权威（ARCHIVED — HISTORICAL, NON-AUTHORITATIVE）**
>
> 本文件记录 2026-09 从旧「五大臣 = 五后台 Agent」架构迁移到当前架构的处理方式。
> 迁移已完成：文中的 `engine`、`kb`、`store`、`route`、`po`、`zhihu` 目录均已退役且不在磁盘上。
> 当前组件归属见 [`AGENTS.md`](../../AGENTS.md) §29。
>
> **不要按本文件恢复旧架构** —— AGENTS.md §28 明确禁止。保留仅为记录迁移依据。

---

# 历史：旧五大臣架构与迁移原则

记录旧架构的处理方式与新旧代码迁移原则。

# 22. 旧五大臣架构处理方式

旧文档 `03 五大臣 Agent 调度 PRD` 不再作为目标 Agent 架构。

以下概念废弃：

```text
一个意图 → 一个大臣 Agent
一个大臣 → 一套独立记忆
切换大臣 = 切换后台认知主体
```

原因：

- 不符合幼儿前台关系稳定性；
- 容易导致记忆碎片；
- 将“记忆类型”误做成“Agent 职责”；
- 难以形成统一 Learner Model；
- 教学决策缺少中心协调。

以下资产仍可保留：

```text
角色名
音色
灯色
剧情人物
模板
DLC 角色
```

它们属于：

> **Story / Presentation Assets**

而不是后台认知 Agent。

---

# 23. 新旧代码迁移原则

## 保留

### engine

保留：

```text
recast.py
levels.py
state_machine.py
context.py
stuck.py
schema.py
templates.py
llm.py
memory.py
safety.py
events.py
```

### kb

整体保留。

### store

整体保留。

### pointing

整体保留。

### intel

整体保留，且继续与儿童实时路径隔离。

## 重构

```text
engine/router.py
prompts.py 中的 minister routing
03 Agent 调度
```

目标：

```text
intent → minister
```

改为：

```text
observation
→ learner state
→ curriculum
→ scaffold
→ story
→ learning decision
→ interaction
```
