# 现实语言 RPG MVP 实施计划

> 依据：[`../architecture/12-embodied-language-rpg.md`](../architecture/12-embodied-language-rpg.md)
> 原则：先文档，后共享契约，再测试与最小实现；每个阶段都能独立回滚。

## 实施进度（2026-09-09）

| 阶段 | 状态 | 说明 |
|---|---|---|
| 0 Trust Boundary | 部分完成且当时已验证 | 最终 Safety、erase 原话残留、RequestInit 已修；capture/auth/KG 边界仍未完成 |
| 1 契约与资产 | 已实现 | 初版曾验证；后续 summary/字段收紧未重跑 |
| 2 Agent 核心 | 已实现，待验证 | Speech Act、物体门、有限 Story、唯一动作、审核 Interaction |
| 3 Shared State | 已实现，待验证 | previous action/evidence/revision/event 的事务校验与恢复 |
| 4 Gateway/合成闭环 | 已编写，待运行 | `/v1/rpg/*` 与 `scripts/rpg-smoke.mjs` |
| 5 产品表面 | 部分实现 | Gateway 脱敏 summary 已有；Web/iOS 任务卡和 debug trace 未做 |
| 6 真机/研究 | 未开始 | 必须保持待真机/研究验证 |

本轮用户明确要求不运行测试；“已实现”仅指代码已编辑，不表示验证通过。

## 目标

在现有合成设备闭环中跑通 `milk_picnic.v1`：确认冰箱场景，孩子用英语请求 milk，虚拟世界
获得 `milk_token` 并转到桌子找红杯；孩子选 red cup 后完成野餐任务。重放、设备失败、低置信
识别和错误槽位均不得推进世界状态。

## 阶段 0：基线与 Trust Boundary

1. 为已复现的最终输出 fallback 漏检补失败测试，再修复最终安全过滤。
2. 为 erase 后 working cache、manifest、audit 仍含儿童原话补失败测试，再修复删除链路。
3. 修复 Web/Gateway `RequestInit.body` 类型不兼容，使根验证继续运行。
4. 运行全部现有测试，保留与 RPG 无关行为。

验收：安全合成样例被终审拒绝；删除后所有本地副本不含原话；`scripts/verify.ps1` 通过或只剩
明确的环境/硬件门。

## 阶段 1：共享契约与审核资产

1. 在 `shared/contracts/v1/` 新增向后兼容的 `rpg-turn.schema.json`、
   `rpg-decision.schema.json` 与脱敏只读 `rpg-quest-summary.schema.json`。
2. 为三个 schema 各增加 valid/invalid fixture 并接入统一验证器。
3. 新增 `milk_picnic.v1` 审核资产与静态图校验测试：唯一入口、节点可达、合法后继、合法事件、
   道具白名单、模板引用完整。

验收：旧 v1 fixtures 继续通过；新契约拒绝客户端 world patch/mastery、非法节点、非法道具和
缺失 revision 的 transition。

## 阶段 2：Agent 核心

1. 新增确定性 `SpeechActResolver`，区分 act、slots、上下文支持和任务满足。
2. 将 Story World 从字符串 patch 改为 seed/node 驱动的有限 transition proposal。
3. Curriculum 从当前节点选择目标，不再用四表达自由表决定 RPG 路径。
4. Scaffold 使用真实的成功/失败历史；成功后降低帮助，清楚失败后提高帮助。
5. Director 明确区分 `quest_satisfied` 与 Assessment 的语言证据，并继续每轮只产出一个动作。
6. Interaction 按 `ask/prompt/reinvite/advance_story/pause` 渲染不同审核文案并终审。

验收：Agent 单测覆盖完整种子、错误槽位、单词上下文成功、低置信不失败、两次失败暂停、成功
撤脚手架和反馈差异。

## 阶段 3：Shared State 原子状态

1. 扩展 learning turn 持久记录中的 RPG 决策；当前 world state 只从上一服务端响应恢复。
2. 在同一 turn 提交事务中验证 base revision、合法节点转换和 source evidence，并生成新 revision。
3. 保持请求哈希、stale turn、delivery claim/ACK 和单次 evidence 规则。
4. erase 继续以 session/child 根级联删除 RPG 回合和事件。

验收：并发重放只发一次奖励；跨重启恢复同一节点；提交失败不产生成功反馈；删除后状态清空。

## 阶段 4：Gateway 与合成设备闭环

1. Gateway 继续作为唯一命令边界，只在已提交决策后渲染与发送 speak command。
2. 用 `scripts/rpg-smoke.mjs` 完整跑通冰箱 → milk → 桌子/杯子 → red cup → completed。
3. 覆盖错误 `water`、错误 `blue cup`、低 ASR、重复 execute、ACK 失败与过期。
4. 把扩展 smoke 接入 CI 的 Docker compose 验证。

验收：一条命令只播放一次；世界状态只在合法 speech turn 推进；最终返回 completed。

## 阶段 5：只读产品表面

1. Gateway 提供脱敏 quest summary 和 debug trace；不返回原始音频、图像或儿童原话。
2. 家长 Web/iOS 只读显示当前任务、世界反馈、下一任务提示和设备采集状态。
3. 调试台显示 Object→Role→Speech→Action 各阶段、ID、置信度、fallback、revision 和 ACK。

验收：客户端不存在 mastery/world state 写接口；Web/iOS contract tests 拒绝非兼容版本。

## 阶段 6：真机与研究验证

严格按 release playbook 在真实 RDK X5 上验证短时 capture、指向、ASR、TTS、ACK、断网恢复与
摄像头关闭。真实儿童研究需另行伦理/隐私方案；未完成前只标记“待真机/研究验证”。

## 每阶段统一验证

```powershell
& './scripts/verify.ps1'
& './scripts/release_readiness.ps1'
& './scripts/audit_repository.ps1'
git diff --check
```

RPG 合成闭环在本地服务启动后运行：

```powershell
node './scripts/rpg-smoke.mjs'
```

每个阶段在 `playbooks/changes/` 留记录；若发现新故障，先按 `playbooks/templates/incident.md`
记录复现与通过证据，再决定是否形成可复用 skill。
