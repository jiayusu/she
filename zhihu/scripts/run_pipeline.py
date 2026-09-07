#!/usr/bin/env python3
""">>> 用法: python scripts/run_pipeline.py [--limit N] — 手动跑一轮问题池管线。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import config
import db
import pipeline

config.ensure_dirs()

if __name__ == "__main__":
    limit = int(sys.argv[sys.argv.index("--limit") + 1]) if "--limit" in sys.argv else None
    conn = db.connect()
    fetch = pipeline.fetch_and_store(conn)
    print("fetch:", {k: v for k, v in fetch.items() if k != "errors"})
    for e in fetch.get("errors", []):
        print("  error:", e)
    struct = pipeline.structure_pending(conn, limit=limit)
    print("structure:", struct)
    conn.close()
