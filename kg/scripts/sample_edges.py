#!/usr/bin/env python3
"""sample_edges.py — W2 人工层: 随机抽 50 条边供人工标注(错误率 ≤10% 放行)。

用法:
  python scripts/sample_edges.py -n 50
  # 打开 data/reports/manual_sample_50.csv, 人工填写 label 列(ok / bad)与 note 列
  # 之后由 scripts/acceptance.py 复核错误率红线
"""
import argparse
import random
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "kg.db"
REPORTS = ROOT / "data" / "reports"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(DB))
    ap.add_argument("-n", type=int, default=50)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    REPORTS.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(args.db)
    rows = conn.execute(
        "SELECT id, head, rel, tail, weight, source FROM edges WHERE status='active' "
        "ORDER BY RANDOM() LIMIT ?", (args.n,)).fetchall()
    conn.close()
    if len(rows) < args.n:
        print(f"!! 库中活跃边不足 {args.n} 条", file=sys.stderr)
        sys.exit(1)
    out = REPORTS / f"manual_sample_{args.n}.csv"
    with open(out, "w", encoding="utf-8", newline="") as f:
        w = csv_writer(f)
        w.writerow(["id", "head", "rel", "tail", "weight", "source", "label", "note"])
        for r in rows:
            w.writerow([*r, "", ""])
    print(f"已抽样 {args.n} 条 → {out}")
    print("人工标注: label=ok 表示边正确且适合儿童; label=bad 表示错误/成人义/无信息, note 写原因。")


def csv_writer(f):
    import csv
    return csv.writer(f)


if __name__ == "__main__":
    main()
