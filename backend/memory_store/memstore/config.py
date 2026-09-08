"""config.py — 环境变量配置(全部有默认值,测试可直接覆盖)。"""
import os
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _int(name: str, default: int) -> int:
    return int(os.environ.get(name, default))


def _float(name: str, default: float) -> float:
    return float(os.environ.get(name, default))


@dataclass
class Config:
    data_dir: Path = field(default_factory=lambda: Path(
        os.environ.get("STORE_DATA", ROOT / "data")))
    port: int = field(default_factory=lambda: _int("STORE_PORT", 8789))

    # KG(语义库)热更新服务, kb/server.py
    kg_url: str = field(default_factory=lambda: os.environ.get(
        "KG_URL", "http://127.0.0.1:8787"))
    # KG HTTP 超时: 万级边热更可达分钟级, 超时批次落 outbox 可重推
    kg_timeout: float = field(default_factory=lambda: _float("KG_TIMEOUT_S", 30.0))

    # 容量(FR-M01/M09)
    working_cap: int = field(default_factory=lambda: _int("WORKING_CAP", 10))
    salience_cap: int = field(default_factory=lambda: _int("SALIENCE_CAP", 1000))
    procedural_cap: int = field(default_factory=lambda: _int("PROCEDURAL_CAP", 500))

    # 遗忘剪枝(FR-M05): EMA 式衰减, 对齐 route/config/salience.json
    decay_lambda_per_day: float = field(default_factory=lambda: _float("DECAY_LAMBDA", 0.05))
    prune_floor: float = field(default_factory=lambda: _float("PRUNE_FLOOR", 0.05))
    # 再巩固加权(FR-M06): 恢复时 salience' = min(1, salience*boost_mult + boost_add)
    reconsolidate_boost: float = field(default_factory=lambda: _float("RECONS_BOOST_MULT", 1.5))
    reconsolidate_add: float = field(default_factory=lambda: _float("RECONS_BOOST_ADD", 0.1))

    # 显著性 ≥ 阈值自动进"永不遗忘"白名单(对齐 route FR-G05 whitelist_threshold)
    whitelist_threshold: float = field(default_factory=lambda: _float("WHITELIST_THRESHOLD", 0.8))

    # 巩固发音评估闸门(风险: 孩子说错的词被固化)
    consolidate_min_assess: float = field(default_factory=lambda: _float("CONSOLIDATE_MIN_ASSESS", 80.0))

    # 向量层
    embed_dim: int = field(default_factory=lambda: _int("EMBED_DIM", 256))
    use_faiss: bool = field(default_factory=lambda: os.environ.get("USE_FAISS", "1") == "1")

    # 非功能: 审计保留 3 年(儿童合规)
    audit_retention_days: int = field(default_factory=lambda: _int("AUDIT_RETENTION_DAYS", 3 * 365))

    # 后台任务(每日自动快照 FR-M08 + 每日衰减剪枝 FR-M05)
    auto_jobs: bool = field(default_factory=lambda: os.environ.get("AUTO_JOBS", "1") == "1")
    job_interval_s: int = field(default_factory=lambda: _int("JOB_INTERVAL_S", 60))

    def db_path(self) -> Path:
        return self.data_dir / "store.db"

    def snapshot_dir(self) -> Path:
        return self.data_dir / "snapshots"

    def audit_dir(self) -> Path:
        return self.data_dir / "audit"

    def report_dir(self) -> Path:
        return self.data_dir / "reports"

    def vector_path(self) -> Path:
        return self.data_dir / "vectors.faiss"

    def ensure_dirs(self) -> None:
        for p in (self.data_dir, self.snapshot_dir(), self.audit_dir(), self.report_dir()):
            p.mkdir(parents=True, exist_ok=True)
