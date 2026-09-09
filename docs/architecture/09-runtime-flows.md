# 运行时流程

> 当前单轮执行、决策优先级、故障降级与现实语言 RPG 端到端流程。
>
> 硬规则、组件归属与导航见仓库根 [`AGENTS.md`](../../AGENTS.md)；RPG 的完整产品约束见
> [`12-embodied-language-rpg.md`](12-embodied-language-rpg.md)。

---

# 16. 单轮实时执行流程

新产品主路径是服务端权威、逐回合提交的有限循环：

```text
1. 显式设备/客户端事件
   ├── object_observed（已确认的结构化物体）
   ├── speech（ASR 文本 + 置信度，不含原始音频）
   └── resume（显式自愿恢复）

2. Device Gateway
   └── 校验 rpg-turn；客户端不能提交 world state/mastery

3. Learning Director / DurableLearning
   ├── 从 Memory 读取最新 committed turn
   ├── 核对 previous_turn_id、请求哈希和上一 delivery
   ├── SpeechActResolver（仅物体上下文就绪的 speech）
   ├── Assessment（独立的教学 evidence 候选）
   ├── Curriculum / Scaffold / Story proposal
   └── 选择唯一 TeachingAction + 有限 transition proposal

4. Shared State / Memory
   ├── 原子核对上一 action、审核 prompt、completed delivery、confirmed object
   ├── 核对 node、world_revision、inventory
   ├── 核对 evidence 与 world event 引用
   └── 提交 turn；重放同一 turn 不重复发奖

5. Interaction
   ├── 只按审核 ID 查表
   └── 最终文本（包括 fallback）通过 Safety

6. Device Gateway
   ├── claim 已提交动作
   ├── 生成 canonical speak command
   └── 等待 RX5/模拟器 ACK

7. ACK 写回 Memory
   ├── completed：下一 speech 才有资格被评估
   ├── failed/expired：ACK 不产生新 transition；后续普通输入关闭，只允许显式恢复
   └── ACK 本身不生成 world event
```

`presenting` 与 delivery 是两个所有者不同的状态。Memory 持久保存剧情决策和 delivery；Gateway
只读投影可将 `presenting + completed` 表示为 `awaiting_speech`，将失败/过期表示为
`delivery_failed`。`resolving` 是提交事务中的瞬时阶段，不接受客户端写入。

---

# 17. 决策优先级

当 proposal 冲突时，Director 依次服从：

```text
内容安全 / 隐私 / 删除硬边界
>
情绪安全与暂停
>
输入和上一动作是否可被信任（契约、ASR、delivery）
>
当前节点 required_objects 与 Speech Act criterion
>
当前 primary learning goal
>
剧情连续性与复习效率
>
内容丰富度
```

例如孩子连续两次清楚但未满足 criterion，即使 Curriculum 希望继续，Director 也选择
`pause/S6`；ASR 低置信则选择 `reinvite`，不把它算作失败；尚未找到目标物体时，只能继续
`explore`，不能靠直接说答案越过现实任务。

---

# 21. 故障降级

任何儿童实时路径都必须不空响应，但降级不能伪造成功：

```text
审核动作正常渲染
↓失败
同节点审核 fallback
↓失败
固定安全探索句
```

- Memory 不可用：返回服务不可用；不在本地伪造 world revision 或跨天记忆。
- Director 不可用：Gateway 不接受 RPG 决策，不由客户端计算下一节点。
- Interaction 不可用：不 claim/播放成功反馈；保留已提交状态供同 turn 重试。
- 设备离线：不把 `HTTP 202` 当作播放完成；已提交世界状态不回滚，也不评估后续 speech。
- 动作 delivery 失败/过期：公开 `delivery_status`；普通 speech/object 被拒绝，仅显式 `resume`
  可创建恢复动作，且 ACK 本身永远不能补写或重复 world event。
- 视觉不确定：保持 `seeking_object/confirming_object`，不得构造已确认物体。
- ASR 低置信：`reinvite`，不计语言失败、不写长期弱点。
- 情绪风险：`pause`；只有显式 resume 才重新呈现。
- KG/开放互联网不可用：只使用本地审核 StorySeed，不进入实时外网 fallback。

---

# 35. 端到端一次完整交互

`milk_picnic.v1` 的 happy path：

```text
01 孩子显式触发短时感知，Gateway 收到确认的 fridge
02 POST /v1/rpg/direct(object_observed)
03 Director 建立 collect_milk/presenting，world_revision=1
04 Memory 提交 turn t1；Interaction 渲染 “Milk or water?”
05 Gateway 发送 speak；设备 ACK completed
06 Gateway 只读摘要显示 collect_milk/awaiting_speech

07 孩子说 “Milk!”；ASR=0.97
08 Director 核对 t1 已完成且物体上下文就绪
09 SpeechActResolver 输出 request_item(item=milk)，quest_satisfied=true
10 Assessment 不把短答当作完整句 mastery
11 Memory 原子提交 milk_token 与 collect_milk→find_red_cup，revision 1→2
12 Interaction 播放已提交后的 “Milk is ready. Find a cup!”

13 孩子在后续显式感知中确认 table/red_cup 场景
14 Director 保持 revision=2，进入 find_red_cup/presenting
15 Interaction 渲染 “Red cup or blue cup?”；设备 ACK completed

16 孩子说 “Red cup!”；ASR=0.98
17 SpeechActResolver 输出 select_item(item=cup,color=red)
18 Memory 同一事务写 red_cup_token 事件 2→3 与 quest_completed 事件 3→4
19 状态成为 picnic_ready/completed，next_quest_id=null
20 Interaction 播放 “Red cup! Our picnic is ready!”
```

错误分支不会偷偷推进：`I want water.` 保持 revision 1；在 `find_red_cup` 尚未确认桌/杯时直接
说 “Red cup!” 只会继续寻找；重复提交同一 `turn_id` 返回原结果而不会重复获得 token。

当前软件可由 `scripts/rpg-smoke.mjs` 合成驱动，但真实 pointing、ASR、TTS、RDK X5 与儿童效果
仍必须分别验收，不能把合成脚本视为真机证据。
