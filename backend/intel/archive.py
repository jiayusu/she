#!/usr/bin/env python3
"""archive.py — FR-I08 原始抓取存档。

原始 JSON 落盘 data/raw/YYYYMMDD/<purpose>/<ts>_<md5>.json, 保留 90 天(可配),
purge() 由调度器每日执行; 结构化结果进 SQLite 永久存档, 可经 /intel/archive 检索。
"""
import hashlib
import json
import time
from pathlib import Path

import config


def write_raw(purpose, payload):
    """存原始 JSON, 返回归档路径 (相对项目根; 数据目录在项目外时为绝对路径)。"""
    day = time.strftime("%Y%m%d")
    body = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    name = f"{time.strftime('%H%M%S')}_{hashlib.md5(body.encode()).hexdigest()[:10]}.json"
    d = config.RAW_DIR / day / purpose
    d.mkdir(parents=True, exist_ok=True)
    p = d / name
    p.write_text(body, encoding="utf-8")
    try:
        return str(p.relative_to(config.ROOT))
    except ValueError:  # INTEL_DATA 配在项目外 (如 D:\data)
        return str(p)


def purge(days=None):
    """清理超过保留期的归档目录。返回删除的目录数。"""
    days = days or config.RAW_RETENTION_DAYS
    cutoff = time.strftime("%Y%m%d", time.localtime(time.time() - days * 86400))
    removed = 0
    if not config.RAW_DIR.exists():
        return removed
    for day_dir in config.RAW_DIR.iterdir():
        if day_dir.is_dir() and day_dir.name < cutoff:
            _rmtree(day_dir)
            removed += 1
    return removed


def _rmtree(p):
    for f in p.rglob("*"):
        if f.is_file():
            f.unlink()
    for d in sorted(p.rglob("*"), reverse=True):
        if d.is_dir():
            d.rmdir()
    p.rmdir()


def find_raw(rel_path):
    """按归档路径取回原文 (争议溯源用)。路径必须落在 RAW_DIR 内, 防目录穿越。"""
    root = config.RAW_DIR.resolve()
    p = Path(rel_path)
    if not p.is_absolute():
        p = config.ROOT / rel_path
    p = p.resolve()
    if not str(p).startswith(str(root)) or not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
