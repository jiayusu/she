#!/usr/bin/env python3
""">>> 用法: python scripts/purge_archive.py [--days 90] — 清理过期原始归档 (FR-I08)。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import archive
import config

if __name__ == "__main__":
    days = int(sys.argv[sys.argv.index("--days") + 1]) if "--days" in sys.argv \
        else config.RAW_RETENTION_DAYS
    print(f"purged {archive.purge(days)} day-dirs (retention={days}d)")
