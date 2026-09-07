"""working.py — 库1 工作记忆: session 内存常驻, 容量 10 条(FR-M01),
满则按 LRU 溢出到情景库(FR-M09); 崩溃后从情景库重建会话状态(非功能 ≤2s)。"""
import time
from collections import OrderedDict

from .db import now


class WorkingTurn(dict):
    """{ts, role, text, scene}"""


class WorkingMemory:
    def __init__(self, db, cap: int = 10):
        self.db = db
        self.cap = cap
        self._sessions: dict[str, OrderedDict] = {}  # session_id -> LRU 队列

    # ------------------------------------------------------------ 热路径
    def push(self, session_id: str, text: str, role: str = "child", scene: str = "",
             ts: float | None = None, child_id: str = "default") -> dict:
        """压入一条; 超容量时按 LRU 逐出, 返回 {evicted: turn|None}。"""
        ts = now() if ts is None else float(ts)
        queue = self._sessions.setdefault(session_id, OrderedDict())
        queue[ts] = {"ts": ts, "role": role, "text": text, "scene": scene}
        queue.move_to_end(ts)
        evicted = None
        while len(queue) > self.cap:
            _, evicted = queue.popitem(last=False)  # 最旧(LRU)
        with self.db.tx() as conn:  # 写穿透: 审计可查
            conn.execute("INSERT INTO working_turns(session_id, child_id, ts, role, "
                         "text, scene) VALUES(?,?,?,?,?,?)",
                         (session_id, child_id, ts, role, text, scene))
        return {"evicted": evicted}

    def items(self, session_id: str) -> list[dict]:
        return list(self._sessions.get(session_id, OrderedDict()).values())

    def touch_session(self, session_id: str) -> bool:
        return session_id in self._sessions

    # ------------------------------------------------------------ 溢出(FR-M09)
    def overflow_to_episodic(self, session_id: str, evicted: dict,
                             episodic_add) -> dict | None:
        """LRU 逐出项写入情景库(kind=overflow), 不清除痕迹。"""
        if not evicted:
            return None
        return episodic_add(
            ts=evicted["ts"], scene=evicted.get("scene", ""),
            utterance=evicted["text"], role=evicted.get("role", "child"),
            session_id=session_id, kind="overflow", salience=0.2)

    # ------------------------------------------------------------ 崩溃恢复(≤2s)
    def recover(self, session_id: str, default_child: str = "default") -> dict:
        """从情景库重建会话状态: 最近 10 轮 + 剧本状态 + 章节。"""
        t0 = time.perf_counter()
        srow = self.db.q1("SELECT * FROM sessions WHERE session_id=?", (session_id,))
        child_id = srow["child_id"] if srow else default_child
        rows = self.db.q(
            "SELECT id, ts, role, utterance, scene FROM episodes WHERE session_id=? "
            "ORDER BY ts DESC LIMIT ?", (session_id, self.cap))
        queue = OrderedDict()
        for r in reversed(rows):  # 恢复为时间正序
            queue[float(r["ts"])] = {"ts": float(r["ts"]), "role": r["role"],
                                     "text": r["utterance"], "scene": r["scene"],
                                     "episode_id": r["id"]}
        self._sessions[session_id] = queue
        return {"session_id": session_id, "child_id": child_id,
                "script_state": srow["script_state"] if srow else "{}",
                "chapter": srow["chapter"] if srow else 1,
                "turns": list(queue.values()),
                "rebuilt": len(rows),
                "recovered_ms": round((time.perf_counter() - t0) * 1000, 2)}

    def forget_session(self, session_id: str):
        self._sessions.pop(session_id, None)
