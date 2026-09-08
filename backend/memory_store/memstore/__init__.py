"""memstore — 04 记忆存储: BMAM 五记忆子系统的存储与生命周期引擎。

五库: 工作记忆 / 情景库(SQLite+FAISS) / 语义库(=KG, 衔接 kb 热更新) /
      显著性缓冲(白名单物理隔离) / 程序性库。
引擎: 巩固(FR-M04) / 遗忘剪枝+再巩固(FR-M05/M06) / 快照回滚(FR-M08) / 容量(FR-M09)。
HTTP 见 ../server.py(§6 接口)。
"""
from .config import Config
from .service import MemoryService

__all__ = ["Config", "MemoryService"]
