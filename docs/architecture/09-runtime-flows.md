# 运行时流程

> 单轮实时执行流程、决策优先级、故障降级链，以及端到端一次完整交互。
>
> 硬规则、组件归属与导航见仓库根 [`AGENTS.md`](../../AGENTS.md)。
> 本文各节沿用 AGENTS.md 原有编号，以保持既有交叉引用有效。

---

# 16. 单轮实时执行流程

标准单轮顺序：

```text
1. 儿童输入
   ├── 语音
   ├── 触摸
   └── 指物

2. 感知层
   ├── ASR
   ├── 发音/语言评估
   ├── 情绪信号
   └── 指向识别

3. Session State 更新

4. Learner Model Agent
   → 当前能力状态

5. Curriculum Agent
   → primary target / review / i+1

6. Scaffold Agent
   → scaffold_level

7. Story World Agent
   → story_action

8. Learning Director
   → 生成唯一 teaching_action

9. Interaction Agent
   → 生成儿童听到的一句话

10. 内容安全过滤

11. TTS / 灯效 / 世界反馈

12. 儿童回应

13. Assessment Agent
   → learning evidence

14. Learner Model Agent
   → 更新 learner state

15. 写入
   ├── Session State
   ├── Learning History
   ├── Story Memory
   └── candidate / confirmed learner evidence

16. 下一轮
```

---

# 17. 决策优先级

当多个 Agent 建议冲突时：

```text
安全
>
情绪安全
>
让孩子愿意继续互动
>
当前 primary learning goal
>
剧情连续性
>
复习效率
>
内容丰富度
```

例如：

```text
Curriculum:
现在应该练过去式

Scaffold:
孩子已经连续失败

Emotion:
明显挫败
```

最终 Learning Director 应选择：

```text
降低要求 / 暂停目标
```

而不是继续强推课程。

---

# 21. 故障降级

任何实时路径必须：

> **不空响应。**

建议顺序：

```text
LLM 正常
↓失败
LLM retry ×1
↓失败
场景模板
↓失败
硬编码安全回应
```

KG 不可用：

```text
不生成未经验证的事实
→ 使用通用安全剧情 / 引导换对象
```

Memory 不可用：

```text
继续当前 session
→ 不伪造跨天记忆
```

视觉不确定：

```text
确认物体
→ 第二候选
→ 优雅退出
```

---

# 35. 端到端一次完整交互

以孩子戴着设备指向冰箱为例：

```text
01 儿童触摸蛇首
↓
02 RX5 产生 wake 事件
↓
03 摄像头进入短时采集窗口
↓
04 端侧/视觉服务识别：
   pointing_target = fridge
↓
05 RX5 上传结构化 pointing event
↓
06 Backend 建立/更新 Session State
↓
07 Learner Model：
   milk = PROMPTED_OUTPUT
   water = SPONTANEOUS_OUTPUT
↓
08 Curriculum：
   primary_target = milk
↓
09 Scaffold：
   scaffold_level = L2
↓
10 Story：
   “冰箱精灵想喝东西”
↓
11 Director：
   要求二选一诱导 milk
↓
12 Interaction：
   "Milk or water?"
↓
13 TTS 返回 RX5
↓
14 RX5 播放
↓
15 儿童："Milk!"
↓
16 RX5 上传语音
↓
17 ASR + Assessment
↓
18 Assessment：
   target_reached = true
   spontaneous = false
   scaffold = L2
↓
19 Learner Model：
   milk evidence +1
↓
20 Story：
   冰箱精灵回应
↓
21 Interaction：
   "Milk! Yum! You found it!"
↓
22 RX5 播放 + 灯效
↓
23 Learning History 写入 store
↓
24 App 报告异步更新
↓
25 Web trace 可供开发查看
```
