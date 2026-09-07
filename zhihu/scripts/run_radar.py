#!/usr/bin/env python3
""">>> 用法: python scripts/run_radar.py [--force] — 手动触发家长语言雷达周报。"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import config
import db
import radar

config.ensure_dirs()

if __name__ == "__main__":
    force = "--force" in sys.argv
    conn = db.connect()
    out = radar.run(conn, force=force)
    print(json.dumps({k: v for k, v in out.items() if k != "payload"},
                     ensure_ascii=False, indent=1, default=str))
    if out.get("payload"):
        print(json.dumps(out["payload"], ensure_ascii=False, indent=1)[:1500])
    conn.close()
