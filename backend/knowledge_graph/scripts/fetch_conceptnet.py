#!/usr/bin/env python3
"""fetch_conceptnet.py — W1: 下载 ConceptNet 英文断言 dump(官网 S3, 不走 API)。

支持断点续传(-C -), 下载后可校验大小。5.7.0 全量约 475MB。
"""
import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "raw"
URL = "https://s3.amazonaws.com/conceptnet/downloads/2019/edges/conceptnet-assertions-5.7.0.csv.gz"
EXPECTED_BYTES = 497_963_447


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--url", default=URL)
    ap.add_argument("--out", default=str(RAW / "conceptnet-assertions-5.7.0.csv.gz"))
    args = ap.parse_args()
    RAW.mkdir(parents=True, exist_ok=True)

    print(f"下载 {args.url}")
    print(f"→ {args.out} (断点续传)")
    rc = subprocess.call(["curl", "-L", "-C", "-", "-o", args.out,
                          "--retry", "5", "--retry-delay", "3", args.url])
    if rc != 0:
        print("!! curl 失败", file=sys.stderr)
        sys.exit(1)
    size = Path(args.out).stat().st_size
    print(f"完成: {size:,} bytes" +
          ("" if size >= EXPECTED_BYTES else f" (⚠ 少于预期 {EXPECTED_BYTES:,}, 可重跑续传)"))


if __name__ == "__main__":
    main()
