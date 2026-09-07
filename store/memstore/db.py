"""db.py — SQLite 连接与 meta/版本管理(单连接 + 全局锁, 对齐 kb/kg.py 约定)。"""
import json
import sqlite3
import threading
import time
from pathlib import Path

from .schema import SCHEMA


def connect(db_path, timeout=30.0):
    # check_same_thread=False: Flask 线程池跨线程复用, 读写统一走 DB.lock 串行化
    conn = sqlite3.connect(str(db_path), timeout=timeout, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


class DB:
    """所有库操作的串行化入口: db.tx() 写事务 / db.q() 只读查询。"""

    def __init__(self, db_path):
        self.path = Path(db_path)
        self.lock = threading.RLock()
        self.conn = connect(self.path)
        with self.lock:
            self.conn.executescript(SCHEMA)
            self.conn.commit()

    # ---- 事务 ----
    def tx(self):
        """用法: with db.tx() as conn: conn.execute(...)  (异常自动回滚)"""
        return _Tx(self)

    def q(self, sql, args=()):
        with self.lock:
            return self.conn.execute(sql, args).fetchall()

    def q1(self, sql, args=()):
        rows = self.q(sql, args)
        return rows[0] if rows else None

    def close(self):
        with self.lock:
            self.conn.close()

    # ---- meta/版本(快照与回滚的单调版本号, 对齐 kg.py) ----
    def get_meta(self, key, default=None):
        row = self.q1("SELECT value FROM meta WHERE key=?", (key,))
        return row["value"] if row else default

    def set_meta(self, key, value):
        with self.tx() as conn:
            conn.execute("INSERT INTO meta(key,value) VALUES(?,?) "
                         "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, str(value)))

    def version(self) -> int:
        return int(self.get_meta("store_version", "1"))

    def bump_version(self) -> int:
        with self.tx() as conn:
            row = conn.execute("SELECT value FROM meta WHERE key='store_version'").fetchone()
            v = (int(row["value"]) if row else 1) + 1
            conn.execute("INSERT INTO meta(key,value) VALUES('store_version',?) "
                         "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (str(v),))
        return v

    def wipe_all(self):
        """物理清库(整设备删除合规), meta/audit/snapshots/erase_jobs 保留(合规留痕)。"""
        tables = ["working_turns", "sessions", "episodes", "episodes_cold",
                  "salience_buffer", "whitelist", "procedural",
                  "consolidation_ledger", "pending_conflicts", "consolidation_jobs"]
        with self.tx() as conn:
            for t in tables:
                conn.execute(f"DELETE FROM {t}")


class _Tx:
    def __init__(self, db):
        self.db = db

    def __enter__(self):
        self.db.lock.acquire()
        return self.db.conn

    def __exit__(self, et, ev, tb):
        try:
            if et is None:
                self.db.conn.commit()
            else:
                self.db.conn.rollback()
        finally:
            self.db.lock.release()
        return False


def now() -> float:
    return time.time()


def local_day(ts: float) -> str:
    return time.strftime("%Y-%m-%d", time.localtime(ts))


def day_start(day: str) -> float:
    return time.mktime(time.strptime(day, "%Y-%m-%d"))


def dump(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


def load(s, default=None):
    if not s:
        return default
    try:
        return json.loads(s)
    except (ValueError, TypeError):
        return default
