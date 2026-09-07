#!/usr/bin/env python3
""">>> 用法: python scripts/run_sentiment.py [--force] — 手动跑一轮舆情监控。"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import config
import db
import sentiment

config.ensure_dirs()

if __name__ == "__main__":
    conn = db.connect()
    out = sentiment.poll(conn, force="--force" in sys.argv)
    print(json.dumps(out, ensure_ascii=False, indent=1, default=str))
    conn.close()
