#!/usr/bin/env python3
"""repair_coverage.py — 覆盖修复: 清洗后每词 <2 边的词, 恢复其最高权重的被删边。

原则: 红线"每词 ≥2 条知识边"优先于 LLM 层的个别删除(宁缺毋滥在稀疏词上让位)。
只恢复 removed_by='llm' 的边(规则层删的不恢复), 恢复动作记入 audit_log。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import kg  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "kg.db"
MIN_EDGES = 2


def main():
    conn = kg.connect(DB)
    counts, low = kg.coverage(conn, MIN_EDGES)
    restored = 0
    words_touched = 0
    with conn:
        for w, n in sorted(low.items()):
            need = MIN_EDGES - n
            rows = conn.execute(
                "SELECT id, weight FROM edges WHERE status='removed' AND removed_by='llm' "
                "AND (head=? OR tail=?) ORDER BY weight DESC LIMIT ?",
                (w, w, need)).fetchall()
            if not rows:
                continue
            for r in rows:
                conn.execute(
                    "UPDATE edges SET status='active', removed_by=NULL, reason=NULL, "
                    "version_removed=NULL WHERE id=?", (r["id"],))
                restored += 1
            words_touched += 1
        kg.log_audit(conn, "repair_coverage",
                     f"restored={restored} words={words_touched}")
    counts2, low2 = kg.coverage(conn, MIN_EDGES)
    cov = 1 - len(low2) / len(counts2)
    stats = kg.db_stats(conn)
    print(f"恢复 {restored} 条边(涉及 {words_touched} 词) → "
          f"覆盖红线 {cov:.1%} (仍不足 {len(low2)}), edges={stats['edges_active']:,}")
    conn.close()


if __name__ == "__main__":
    main()
