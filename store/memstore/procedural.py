"""procedural.py — 库5 程序性库: 触发-动作模式, 容量 500(FR-M01/M07)。

触发类型:
  {"type":"time","time":"20:30","repeat":"daily"}          每日定时(朝会提醒)
  {"type":"time","time":"20:30","repeat":"weekly","days":[0,6]}  周几定时(0=周一, 周总结)
  {"type":"once","at":"2026-09-05T20:30:00"}               单次到期
  {"type":"scene","scene":"朝会"}                           进入场景触发

due() 纯函数化(可注入 now), 保证 20:30 提醒准时率 100%; 消费方执行后
mark_fired() 防止同周期重复触发。
"""
import time
from datetime import datetime, timedelta

from .db import dump, load, now


class ProceduralStore:
    def __init__(self, db, cap: int = 500):
        self.db = db
        self.cap = cap

    # ------------------------------------------------------------ 写入
    def add(self, name: str, trigger: dict, action: dict,
            child_id: str = "default") -> dict:
        self._validate(trigger, action)
        with self.db.tx() as conn:
            while conn.execute("SELECT COUNT(*) c FROM procedural").fetchone()["c"] \
                    >= self.cap:  # 容量: 先清已完成的单次任务, 再淘汰最低使用
                row = conn.execute(
                    "SELECT id FROM procedural WHERE trigger LIKE '%\"once\"%' "
                    "AND last_fired IS NOT NULL ORDER BY last_fired ASC LIMIT 1"
                ).fetchone()
                if row is None:
                    row = conn.execute("SELECT id FROM procedural ORDER BY "
                                       "fire_count ASC, id ASC LIMIT 1").fetchone()
                conn.execute("DELETE FROM procedural WHERE id=?", (row["id"],))
            conn.execute("INSERT INTO procedural(name, trigger, action, child_id) "
                         "VALUES(?,?,?,?)",
                         (name, dump(trigger), dump(action), child_id))
            rid = conn.execute("SELECT last_insert_rowid() r").fetchone()["r"]
        return self.get(rid)

    @staticmethod
    def _validate(trigger, action):
        ttype = trigger.get("type")
        if ttype == "time":
            time.strptime(trigger["time"], "%H:%M")
            if trigger.get("repeat") not in ("daily", "weekly"):
                raise ValueError("time 触发 repeat 须为 daily|weekly")
            if trigger["repeat"] == "weekly" and not trigger.get("days"):
                raise ValueError("weekly 触发需要 days(0=周一)")
        elif ttype == "once":
            datetime.fromisoformat(trigger["at"])
        elif ttype == "scene":
            if not trigger.get("scene"):
                raise ValueError("scene 触发需要 scene")
        else:
            raise ValueError("trigger.type 须为 time|once|scene")
        if not action.get("type"):
            raise ValueError("action.type 必填(remind/summary/...)")

    # ------------------------------------------------------------ 到期计算(FR-M07)
    def due(self, ts: float | None = None, scene: str | None = None) -> list[dict]:
        ts = now() if ts is None else float(ts)
        dt = datetime.fromtimestamp(ts)
        out = []
        for r in self.db.q("SELECT * FROM procedural WHERE enabled=1 ORDER BY id"):
            trig = load(r["trigger"], {})
            if self._is_due(trig, dt, r["last_fired"], ts, scene):
                out.append({**dict(r), "trigger": trig,
                            "action": load(r["action"], {})})
        return out

    @staticmethod
    def _is_due(trig: dict, dt: datetime, last_fired, ts: float,
                scene: str | None) -> bool:
        ttype = trig.get("type")
        if ttype == "scene":
            return bool(scene) and trig["scene"] == scene
        if ttype == "once":
            at = datetime.fromisoformat(trig["at"]).timestamp()
            return last_fired is None and ts >= at
        # time
        hh, mm = (int(x) for x in trig["time"].split(":"))
        today_due = dt.hour > hh or (dt.hour == hh and dt.minute >= mm)
        if not today_due:
            return False
        if trig.get("repeat") == "weekly":
            if dt.weekday() not in trig.get("days", []):  # 0=周一
                return False
        if last_fired is None:
            return True
        fired = datetime.fromtimestamp(last_fired)
        return not (fired.date() == dt.date() and
                    (fired.hour, fired.minute) >= (hh, mm))

    def mark_fired(self, pid: int, ts: float | None = None) -> dict | None:
        ts = now() if ts is None else float(ts)
        with self.db.tx() as conn:
            conn.execute("UPDATE procedural SET last_fired=?, fire_count=fire_count+1 "
                         "WHERE id=?", (ts, pid))
        return self.get(pid)

    # ------------------------------------------------------------ 管理
    def get(self, pid: int):
        row = self.db.q1("SELECT * FROM procedural WHERE id=?", (pid,))
        if not row:
            return None
        d = dict(row)
        d["trigger"], d["action"] = load(d["trigger"], {}), load(d["action"], {})
        return d

    def list(self, child_id: str | None = None) -> list[dict]:
        sql = "SELECT * FROM procedural"
        args = []
        if child_id:
            sql += " WHERE child_id=?"
            args.append(child_id)
        sql += " ORDER BY id"
        return [self._decorate(r) for r in self.db.q(sql, args)]

    def _decorate(self, r):
        d = dict(r)
        d["trigger"], d["action"] = load(d["trigger"], {}), load(d["action"], {})
        return d

    def set_enabled(self, pid: int, on: bool):
        with self.db.tx() as conn:
            conn.execute("UPDATE procedural SET enabled=? WHERE id=?",
                         (1 if on else 0, pid))
        return self.get(pid)

    def delete(self, pid: int) -> bool:
        with self.db.tx() as conn:
            cur = conn.execute("DELETE FROM procedural WHERE id=?", (pid,))
        return cur.rowcount > 0

    def count(self) -> int:
        return self.db.q1("SELECT COUNT(*) c FROM procedural")["c"]
