#!/usr/bin/env python3
"""临时: 查当前图状态。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import kg

conn = kg.connect(Path(__file__).resolve().parents[1] / "data" / "kg.db")
s = kg.db_stats(conn)
counts, low = kg.coverage(conn, 2)
cov = 1 - len(low) / len(counts)
print(f"edges={s['edges_active']:,} v{s['version']} 覆盖红线: {cov:.1%} (不足 {len(low)})")
conn.close()
