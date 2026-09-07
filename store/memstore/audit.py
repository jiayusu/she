"""audit.py — 五库统一审计日志(非功能: 谁/何时/内容摘要, 保留 3 年儿童合规)。

双写: audit_log 表(可查) + data/audit/YYYY-MM-DD.jsonl(按天归档)。
"""
import json
import threading
import time
from pathlib import Path

DAY = 86400.0


class Audit:
    def __init__(self, db, audit_dir: Path, retention_days: int = 3 * 365):
        self.db = db
        self.dir = Path(audit_dir)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.retention_days = retention_days
        self._lock = threading.Lock()

    def log(self, actor: str, action: str, target: str = "", summary: str = "",
            ts: float | None = None):
        ts = time.time() if ts is None else ts
        day = time.strftime("%Y-%m-%d", time.localtime(ts))
        iso = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts))
        with self._lock:
            with self.db.tx() as conn:
                conn.execute("INSERT INTO audit_log(ts, actor, action, target, summary) "
                             "VALUES(?,?,?,?,?)", (iso, actor, action, target, summary))
            with open(self.dir / f"{day}.jsonl", "a", encoding="utf-8") as f:
                f.write(json.dumps({"ts": iso, "actor": actor, "action": action,
                                    "target": target, "summary": summary},
                                   ensure_ascii=False) + "\n")

    def query(self, date: str | None = None, action: str | None = None,
              limit: int = 100) -> list[dict]:
        sql, args = "SELECT * FROM audit_log WHERE 1=1", []
        if date:
            sql += " AND ts LIKE ?"
            args.append(date + "%")
        if action:
            sql += " AND action=?"
            args.append(action)
        sql += " ORDER BY id DESC LIMIT ?"
        args.append(int(limit))
        return [dict(r) for r in self.db.q(sql, args)]

    def enforce_retention(self, now: float | None = None) -> int:
        """清理超过保留期的审计(表 + 归档文件), 返回删除条数。"""
        now = time.time() if now is None else now
        cutoff = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(
            now - self.retention_days * DAY))
        with self.db.tx() as conn:
            cur = conn.execute("DELETE FROM audit_log WHERE ts < ?", (cutoff,))
            removed = cur.rowcount
        removed_files = 0
        for f in self.dir.glob("*.jsonl"):
            try:
                day_ts = time.mktime(time.strptime(f.stem, "%Y-%m-%d"))
            except ValueError:
                continue
            if day_ts < now - self.retention_days * DAY:
                f.unlink()
                removed_files += 1
        return removed + removed_files
