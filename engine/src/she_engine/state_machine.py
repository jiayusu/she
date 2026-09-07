"""FR-E03 · 剧本状态机：朝会 → 探险 → 睡前，开口是唯一推进条件。

规则：
- 只有「孩子实质开口」（有可懂话语）才推进进度；沉默/重邀/卡壳轮一律不动。
- 朝会：完成 tasks_total 个任务 → 进探险；
- 探险：每开口一次故事走一步，走满 adventure_turns → 进睡前；
- 睡前：开口 bedtime_turns 次 → 一天结束；
- 持久化到记忆存储（跨天续剧情）：重启后 resume_for_today() 接续
  「昨天讲到哪」，并在 meta 里给出 recap 提示供大臣重述。

状态以纯数据 dict 持久化（记忆模块 04 可换成 Redis/SQLite，形状不变）。
"""

from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

STATE_MORNING_COURT = "morning_court"
STATE_ADVENTURE = "adventure"
STATE_BEDTIME = "bedtime"
STATE_DAY_ENDED = "ended"

ALL_STATES = (STATE_MORNING_COURT, STATE_ADVENTURE, STATE_BEDTIME, STATE_DAY_ENDED)


def _today() -> str:
    return _dt.date.today().isoformat()


@dataclass
class ScriptState:
    """一天剧本的可持久化快照（dict ↔ dataclass）。"""

    date: str = field(default_factory=_today)
    state: str = STATE_MORNING_COURT
    tasks_total: int = 3
    tasks_done: int = 0
    tasks_planned: List[str] = field(default_factory=list)   # 今日任务词
    adventure_turns: int = 6                                  # 探险开口目标
    adventure_done: int = 0
    chapter: int = 1                                          # 故事章节（跨天累计）
    bedtime_turns: int = 2
    bedtime_done: int = 0
    days_played: int = 1

    # ---- 持久化 -------------------------------------------------------------
    def to_dict(self) -> Dict[str, Any]:
        return {
            "date": self.date, "state": self.state,
            "tasks_total": self.tasks_total, "tasks_done": self.tasks_done,
            "tasks_planned": list(self.tasks_planned),
            "adventure_turns": self.adventure_turns, "adventure_done": self.adventure_done,
            "chapter": self.chapter, "bedtime_turns": self.bedtime_turns,
            "bedtime_done": self.bedtime_done, "days_played": self.days_played,
        }

    @classmethod
    def from_dict(cls, d: Optional[Dict[str, Any]]) -> "ScriptState":
        if not d:
            return cls()
        base = cls()
        try:
            base.tasks_total = int(d.get("tasks_total", base.tasks_total))
            base.tasks_done = int(d.get("tasks_done", 0))
            base.adventure_turns = int(d.get("adventure_turns", base.adventure_turns))
            base.adventure_done = int(d.get("adventure_done", 0))
            base.chapter = int(d.get("chapter", 1))
            base.bedtime_turns = int(d.get("bedtime_turns", base.bedtime_turns))
            base.bedtime_done = int(d.get("bedtime_done", 0))
            base.days_played = int(d.get("days_played", 1))
            base.tasks_planned = [str(x) for x in (d.get("tasks_planned") or [])]
            base.state = str(d.get("state", STATE_MORNING_COURT))
            base.date = str(d.get("date") or _today())
        except (TypeError, ValueError):
            return cls()
        if base.state not in ALL_STATES:
            base.state = STATE_MORNING_COURT
        return base

    # ---- 跨天续接（验收：关机重开后接续"昨天讲到哪"） ------------------------
    def resume_for_today(self) -> Optional[str]:
        """重启后调用。返回给大臣的「上次讲到哪」recap 提示（无历史返回 None）。"""
        if self.date == _today():
            return None  # 同一天内重启，剧情原样接续
        self.days_played += 1
        if self.state in (STATE_BEDTIME, STATE_DAY_ENDED):
            # 昨天已经道过晚安 → 新的一天从朝会开始，故事进入下一章
            self.state = STATE_MORNING_COURT
            self.tasks_done = 0
            self.adventure_done = 0
            self.bedtime_done = 0
            self.chapter += 1
            self.date = _today()
            return f"昨天讲到第{self.chapter - 1}章结束，孩子已道晚安；今天是新的一天，进入第{self.chapter}章的朝会。"
        if self.state == STATE_ADVENTURE:
            self.date = _today()
            return (
                f"昨天探险进行到第{self.chapter}章，走了{self.adventure_done}步（共{self.adventure_turns}步），"
                f"还没到睡前。今天从中途接续：先花一句回顾'昨天讲到哪'，再继续探险。"
            )
        # 昨天停在朝会（没讲完任务）
        self.date = _today()
        return (
            f"昨天朝会完成了{self.tasks_done}/{self.tasks_total}个任务，探险还没开始。"
            f"今天先收尾朝会任务，再进入第{self.chapter}章探险。"
        )

    # ---- 推进（开口是唯一推进条件） ------------------------------------------
    def advance(self, task_hit: str = "") -> Dict[str, Any]:
        """一次实质开口 → 状态推进一步。返回事件 dict（供 memory_write / 埋点）。"""
        events: Dict[str, Any] = {}
        if self.state == STATE_MORNING_COURT:
            self.tasks_done += 1
            events["court_task"] = task_hit or f"task_{self.tasks_done}"
            if self.tasks_done >= self.tasks_total:
                self.state = STATE_ADVENTURE
                events["state_change"] = STATE_ADVENTURE
                events["court_completed"] = True
        elif self.state == STATE_ADVENTURE:
            self.adventure_done += 1
            events["adventure_step"] = self.adventure_done
            if self.adventure_done >= self.adventure_turns:
                self.state = STATE_BEDTIME
                events["state_change"] = STATE_BEDTIME
        elif self.state == STATE_BEDTIME:
            self.bedtime_done += 1
            events["bedtime_step"] = self.bedtime_done
            if self.bedtime_done >= self.bedtime_turns:
                self.state = STATE_DAY_ENDED
                events["state_change"] = STATE_DAY_ENDED
                events["day_completed"] = True
        # STATE_DAY_ENDED：不推进，等 resume_for_today() 开新的一天
        return events

    # ---- 场景指令（注入 prompt 的 scene_directive） ---------------------------
    def scene_directive(self, recap: str = "") -> str:
        if self.state == STATE_MORNING_COURT:
            left = self.tasks_total - self.tasks_done
            task = self.tasks_planned[self.tasks_done] if self.tasks_done < len(self.tasks_planned) else ""
            body = (
                f"SCRIPT STATE: morning court. {self.tasks_done}/{self.tasks_total} tasks done, {left} left. "
                + (f"The next task is about: {task}. Give it as ONE short mission now." if task
                   else "Give the child one short mission (a word to say or a thing to find).")
            )
        elif self.state == STATE_ADVENTURE:
            body = (
                f"SCRIPT STATE: adventure, chapter {self.chapter}. "
                f"Story progress {self.adventure_done}/{self.adventure_turns} steps. "
                "Advance the tale by ONE small step, then hand the 'next page' to the child "
                "with an open hook (a question or 'then what?')."
            )
        elif self.state == STATE_BEDTIME:
            body = (
                f"SCRIPT STATE: bedtime. Wind down: count today's learned words softly, "
                f"one gentle line, no new plot, no new questions that require long answers. "
                f"(bedtime step {self.bedtime_done}/{self.bedtime_turns})"
            )
        else:
            body = (
                "SCRIPT STATE: day ended. Keep it warm and brief; invite a soft goodnight "
                "word but do not push any task."
            )
        if recap:
            body = "STORY RECAP (resume from last session): " + recap + "\n" + body
        return body


# ------------------------------------------------------------------ 任务规划
DEFAULT_TASK_POOL = ("fruit", "animal", "toy", "color", "food", "weather")


def plan_tasks(seed: int = 0, count: int = 3, pool: Optional[List[str]] = None) -> List[str]:
    """给今天的朝会排任务（同一孩子同一天稳定；换天自动换任务）。"""
    src = list(pool or DEFAULT_TASK_POOL)
    out = []
    for i in range(count):
        out.append(src[(seed + i) % len(src)])
    return out


def day_seed(date_iso: str) -> int:
    """从日期推导稳定伪随机种子（无随机依赖，跨重启一致）。"""
    return sum(ord(c) for c in date_iso) % 997
