#!/usr/bin/env python3
"""finish_pipeline.py — LLM 清洗完成后的终跑链: 报告刷新 → 最终训练 → 索引 → 抽样。

用法(确认 build_kg.py --llm-clean 已跑完):
  python scripts/finish_pipeline.py [--epochs 300] [--dim 100] [--skip-train]
产出: data/kg.graphml(重导), data/reports/kg_coverage.csv, data/embeddings/*,
      data/reports/manual_sample_50.csv(待人工标注)
"""
import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
DATA = ROOT / "data"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--epochs", type=int, default=300)
    ap.add_argument("--dim", type=int, default=100)
    ap.add_argument("--db", default=str(DATA / "kg.db"))
    ap.add_argument("--skip-train", action="store_true")
    args = ap.parse_args()

    import build_kg
    import kg

    # 1) 清洗后刷新: graphml 重导 + 覆盖率报告
    conn = kg.connect(args.db)
    stats = kg.db_stats(conn)
    nodes, ecount = kg.export_graphml(conn, DATA / "kg.graphml")
    seed = build_kg.load_seed(DATA / "seed.csv")
    counts, low = build_kg.write_coverage_reports(conn, seed)
    cov = 1 - len(low) / len(counts)
    print(f"[1/4] 清洗后图: {stats['edges_active']:,} 边 / {nodes:,} 节点, "
          f"覆盖红线 {cov:.1%}")
    conn.close()

    # 2) 最终训练(RotatE 300 epochs) + 3) FAISS 索引
    if not args.skip_train:
        subprocess.check_call([sys.executable, str(ROOT / "kg_embed.py"), "train",
                               "--db", args.db, "--dim", str(args.dim),
                               "--epochs", str(args.epochs)])
    subprocess.check_call([sys.executable, str(ROOT / "kg_embed.py"), "index"])
    print("[2/4] RotatE 训练 + [3/4] FAISS 索引 完成")

    # 4) 人工抽检样本
    subprocess.check_call([sys.executable, str(ROOT / "scripts" / "sample_edges.py"),
                           "-n", "50"])
    print("[4/4] 抽样完成 → 人工标注 label 列(ok/bad)后运行 scripts/acceptance.py")


if __name__ == "__main__":
    main()
