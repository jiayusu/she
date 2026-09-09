"""snapshot.py — 快照与回滚(FR-M08): 每日自动 + 手动, 任意版本 ≤1 分钟恢复。

快照内容: store.db(SQLite backup API 一致性备份) + 向量文件 + meta.json。
回滚: 拷回 db+向量 → 从恢复库全量重建索引(保证库/向量一致) → 版本单调递增。
启动自检: 向量文件损坏/缺失时自动从 SQLite 重建(FAISS 损坏"失忆"对策)。
"""
import json
import shutil
import sqlite3
import time
from pathlib import Path

from .db import connect, dump
from .vector import HashingEmbedder, VectorIndex


class Snapshots:
    def __init__(self, db, snapshot_dir: Path, vector_path: Path, episodic,
                 embedder: HashingEmbedder, index_factory=None):
        self.db = db
        self.dir = Path(snapshot_dir)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.vector_path = Path(vector_path)
        self.episodic = episodic
        self.emb = embedder
        self.index_factory = index_factory  # () -> VectorIndex, 注入以热替换 service 索引

    # ---- 向量文件命名跟随实际后端(faiss: vectors.bin / numpy: vectors.bin.npz) ----
    def _vec_file(self, folder: Path) -> Path:
        if self.episodic.index.backend == "faiss":
            return folder / "vectors.bin"
        return folder / "vectors.bin.npz"

    def index_save(self, folder: Path):
        self.episodic.index.save(folder / "vectors.bin")

    # ------------------------------------------------------------ 快照
    def create(self, note: str = "manual") -> dict:
        t0 = time.perf_counter()
        version = self.db.version()
        counts = self.episodic.counts()
        out = self.dir / f"v{version}"
        if out.exists():
            shutil.rmtree(out)
        out.mkdir(parents=True)
        with self.db.tx() as conn:  # 先注册再备份: 快照自身携带注册行, 回滚后不丢
            conn.execute("INSERT OR REPLACE INTO snapshots(version, path, note, counts) "
                         "VALUES(?,?,?,?)", (version, str(out), note, dump(counts)))
        dst = sqlite3.connect(str(out / "store.db"))
        with self.db.lock:
            self.db.conn.backup(dst)  # 一致性备份(含 WAL 合并)
            self.index_save(out)
        dst.close()
        (out / "meta.json").write_text(json.dumps(
            {"version": version, "ts": time.time(), "note": note,
             "counts": counts, "backend": self.episodic.index.backend},
            ensure_ascii=False, indent=1), encoding="utf-8")
        ms = (time.perf_counter() - t0) * 1000
        return {"version": version, "path": str(out), "counts": counts,
                "duration_ms": round(ms, 1)}

    def list(self) -> list[dict]:
        return [dict(r) for r in self.db.q(
            "SELECT version, created_at, path, note, counts FROM snapshots "
            "ORDER BY version DESC")]

    def purge_all(self) -> int:
        """Delete every restore point because each SQLite backup spans all children."""
        count = len(self.list())
        if self.dir.exists():
            shutil.rmtree(self.dir)
        self.dir.mkdir(parents=True, exist_ok=True)
        with self.db.tx() as conn:
            conn.execute("DELETE FROM snapshots")
        return count

    # ------------------------------------------------------------ 回滚
    def rollback(self, v: int) -> dict:
        snap = self.dir / f"v{v}"
        if not (snap / "store.db").exists():
            return {"error": f"snapshot v{v} not found"}
        t0 = time.perf_counter()
        current = self.db.version()
        with self.db.lock:
            self.db.conn.close()
            for suffix in ("", "-wal", "-shm"):
                p = Path(str(self.db.path) + suffix)
                if p.exists():
                    p.unlink()
            shutil.copy2(snap / "store.db", self.db.path)
            src_vec = self._vec_file(snap)
            if src_vec.exists():
                shutil.copy2(src_vec, self._live_vec_path())
            self.db.conn = connect(self.db.path)
        # 库/向量一致性优先: 一律从恢复库全量重建索引(≤1min 预算内)
        n = self.episodic.rebuild_index()
        restore_version = max(current, v) + 1  # 版本单调递增, 对齐 kg 侧约定
        self.db.set_meta("store_version", restore_version)
        self._re_register(v, snap)  # 保险: 恢复库缺注册行则补记
        ms = (time.perf_counter() - t0) * 1000
        return {"rolled_back_to": v, "version": restore_version,
                "reindexed": n, "duration_ms": round(ms, 1)}

    def _re_register(self, v: int, snap: Path):
        if self.db.q1("SELECT 1 FROM snapshots WHERE version=?", (v,)):
            return
        counts = {}
        meta_file = snap / "meta.json"
        if meta_file.exists():
            try:
                counts = json.loads(meta_file.read_text(encoding="utf-8")).get(
                    "counts", {})
            except ValueError:
                pass
        with self.db.tx() as conn:
            conn.execute("INSERT OR REPLACE INTO snapshots(version, path, note, counts) "
                         "VALUES(?,?,?,?)", (v, str(snap), "restored-after-rollback",
                                             dump(counts)))

    def _live_vec_path(self) -> Path:
        if self.episodic.index.backend == "faiss":
            return self.vector_path
        return Path(str(self.vector_path) + ".npz")

    # ------------------------------------------------------------ 健康自检/重建
    def startup_check(self) -> dict:
        """向量文件缺失/损坏 → 从 SQLite 原始数据重建索引(可重建性验证)。"""
        counts = self.episodic.counts()
        need = counts["active"] + counts["cold"]
        healthy = False
        try:
            healthy = (len(self.episodic.index) == need)
        except Exception:  # noqa: BLE001 - faiss 文件损坏在此暴露
            healthy = False
        if healthy:
            return {"rebuilt": False, "indexed": len(self.episodic.index)}
        n = self.episodic.rebuild_index()
        self.persist_index()
        return {"rebuilt": True, "reason": "index_missing_or_corrupt", "indexed": n}

    def persist_index(self):
        self.episodic.index.save(self._live_vec_path())
