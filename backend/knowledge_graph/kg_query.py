#!/usr/bin/env python3
"""kg_query.py — W2 建库冒烟测试 + 万物模式查询演示。

  python kg_query.py                 # 冒烟: 统计/样例/红线检查, 异常时退出码非零
  python kg_query.py --word fridge   # 单词查询演示(kg.facts + next_words)
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import kg  # noqa: E402

ROOT = Path(__file__).resolve().parent
DB = ROOT / "data" / "kg.db"


def smoke():
    if not DB.exists():
        print("!! data/kg.db 不存在, 先运行: python build_kg.py --seed data/seed.csv --out data/kg.db")
        return 1
    conn = kg.connect(DB)
    stats = kg.db_stats(conn)
    print("== kg.db 冒烟 ==")
    for k, v in stats.items():
        print(f"  {k}: {v:,}")
    assert stats["words"] >= 1500, "seed 词数不足 1500"
    assert stats["edges_active"] >= stats["words"] * 2, "边数不足(红线: 每词≥2)"
    assert stats["concepts"] > 0 and stats["edges_active"] > 0, "空库"

    print("\n== kg.facts('apple') 万物模式样例 ==")
    for f in kg.facts(conn, "apple", 8):
        print(f"  {f['head']} -[{f['rel']}]→ {f['tail']}  (w={f['weight']}, {f['source']})")

    print("\n== kg.facts('fridge') 样例 ==")
    for f in kg.facts(conn, "fridge", 5):
        print(f"  {f['head']} -[{f['rel']}]→ {f['tail']}")

    print("\n== next_words('apple') 规则版推荐 ==")
    for i, c in enumerate(kg.next_words(conn, "apple", 5), 1):
        print(f"  {i}. {c['word']} ({c['level']}, score={c['score']})")

    counts, low = kg.coverage(conn, 2)
    ratio = 1 - len(low) / len(counts)
    print(f"\n== 红线检查: 每词≥2条知识边 → {ratio:.1%} (不足 {len(low)} 词, 详见 data/reports/kg_low_coverage.csv)")
    if ratio < 0.95:
        print("!! 覆盖红线未达 95%, 建议检查清洗规则", file=sys.stderr)
        conn.close()
        return 1
    conn.close()
    print("\n冒烟通过 ✅")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--word", help="查询单词(kg.facts 演示), 省略则跑完整冒烟")
    ap.add_argument("--db", default=str(DB))
    args = ap.parse_args()
    if args.word:
        conn = kg.connect(args.db)
        for f in kg.facts(conn, args.word, 15):
            print(f"  {f['head']} -[{f['rel']}]→ {f['tail']}  (w={f['weight']})")
        conn.close()
        return
    sys.exit(smoke())


if __name__ == "__main__":
    main()
