# App 端：家长端

> 家长端首页、学习报告、家长输入、设备管理与隐私数据边界。
>
> 硬规则、组件归属与导航见仓库根 [`AGENTS.md`](../../AGENTS.md)。
> 本文各节沿用 AGENTS.md 原有编号，以保持既有交叉引用有效。

---

# 33. App 端：家长端

App 是 **家长与系统之间的控制面**，不是儿童实时教学 Agent。

## 33.1 做什么

App 负责：

```text
设备绑定
儿童档案
学习目标
学习报告
历史趋势
兴趣设置
使用时间
家长反馈
隐私授权
数据导出/删除
设备设置
```

## 33.2 首页建议数据

App 首页重点显示真实学习进展，而不是“学习时长”。

推荐：

```text
今日主动开口次数
无提示输出次数
最高完成 Scaffold Level
新增主动词汇
跨场景迁移词汇
今日探险剧情
需要家长注意的异常
```

## 33.3 学习报告

报告来源必须是：

```text
Assessment
+
Learner Profile
+
Learning History
```

而不是让 LLM 根据聊天记录自由总结。

示例结构：

```json
{
  "spontaneous_speaking_count": 12,
  "prompted_speaking_count": 7,
  "new_spontaneous_words": ["milk", "open"],
  "transferred_words": ["apple"],
  "current_focus": "主动表达食物需求",
  "scaffold_trend": "L3 -> L2",
  "parent_note": ""
}
```

## 33.4 家长输入

家长可以提供约束：

```text
今天最多 10 分钟
明天去动物园
最近喜欢恐龙
今天状态不好
暂时不练某主题
```

这些输入写入：

```text
Parent Constraints
```

由 Learning Director / Curriculum Agent 消费。

家长输入 **不能直接修改 mastery**。

例如：

```text
“我觉得他已经会 apple 了”
```

不能直接：

```text
apple = TRANSFERRED
```

只能作为一条辅助 evidence。

## 33.5 设备管理

App 负责：

- RX5 设备绑定；
- Wi-Fi 配置；
- 音量；
- 灯效开关；
- 摄像头权限；
- 麦克风权限；
- 固件版本；
- 在线状态；
- 设备解绑。

App 不承担实时音视频推理。

## 33.6 隐私与数据

必须提供：

```text
查看儿童数据
导出
删除
关闭长期记忆
关闭摄像头能力
关闭原始音频上传
```

删除操作走：

```text
POST /memory/erase
```

不得只删除 App 展示层数据。
