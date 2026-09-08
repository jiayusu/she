#!/usr/bin/env python3
"""build_kg.py — W2 清洗(三层) + 建库。

W2 建库(全量重建, 含规则层):
  python build_kg.py --seed data/seed.csv --out data/kg.db
W2 LLM 层(在已建库上批量审边, 只输出"要删的行", 提示词冻结版):
  python build_kg.py --llm-clean [--llm-batch 50] [--llm-rels RelatedTo,Synonym,IsA,CapableOf]
人工层(抽检 50 条):
  python scripts/sample_edges.py --db data/kg.db -n 50   # 标注后由 acceptance.py 复核

产出: data/kg.db (SQLite), data/kg.graphml, data/reports/*.csv
"""
import argparse
import csv
import gzip
import json
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cleaning  # noqa: E402
import kg  # noqa: E402

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
REPORTS = DATA / "reports"


def load_seed(path):
    words = []
    with open(path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            words.append((row["word"].strip().lower(), row["level"].strip(),
                          row["pos"].strip(), "yle" if row["level"] in
                          ("starters", "movers", "flyers") else "cefrj"))
    return words


def rule_layer(edges_iter):
    """规则层: 逐边审, 返回 (通过边, 删除计数)。"""
    kept, dropped = [], Counter()
    for head, rel, tail, weight, h_sense, t_sense, source in edges_iter:
        ok, reason = cleaning.rule_check(head, rel, tail, h_sense, t_sense, weight)
        if ok:
            kept.append((head, rel, tail, weight, source))
        else:
            dropped[reason.split(":")[0]] += 1
    return kept, dropped


def read_candidates(path):
    opener = gzip.open if str(path).endswith(".gz") else open
    with opener(path, "rt", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            yield (row["head"], row["rel"], row["tail"], float(row["weight"]),
                   row.get("head_sense", ""), row.get("tail_sense", ""), "conceptnet")


def write_coverage_reports(conn, seed):
    counts, low = kg.coverage(conn, 2)
    with open(REPORTS / "kg_coverage.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["word", "edges"])
        for w_ in sorted(counts, key=lambda x: counts[x]):
            w.writerow([w_, counts[w_]])
    lv = {s[0]: s[1] for s in seed}
    with open(REPORTS / "kg_low_coverage.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["word", "level", "edges"])
        for w_ in sorted(low):
            w.writerow([w_, lv.get(w_, "?"), low[w_]])
    return counts, low


def build_db(seed_path, out_path, candidates_path):
    seed = load_seed(seed_path)
    seed_set = {w for w, *_ in seed}
    # 常用词白名单(词表 ∪ CEFR-J 全级别): 非词表一侧必须是常用词
    lex = cleaning.build_lexicon(seed_path, ROOT / "raw" / "cefrj-vocabulary-profile-1.5.csv")
    print(f"规则层: 常用词白名单 {len(lex):,} 词")
    kept, dropped = rule_layer(read_candidates(candidates_path))
    print(f"规则层: 保留 {len(kept):,} 条, 删除 {sum(dropped.values()):,} 条")
    for reason, n in dropped.most_common():
        print(f"  - {reason}: {n:,}")

    for suffix in ("", "-wal", "-shm"):
        p = Path(str(out_path) + suffix)
        if p.exists():
            p.unlink()

    conn = kg.connect(out_path)
    kg.init_db(conn)
    with conn:
        conn.executemany("INSERT OR IGNORE INTO words(word, level, pos, source) "
                         "VALUES(?,?,?,?)", seed)
        tails = {t for _, _, t, _, _ in kept} - seed_set
        heads = {h for h, _, _, _, _ in kept} - seed_set
        conn.executemany("INSERT OR IGNORE INTO concepts(word, source) VALUES(?,?)",
                         [(w, "conceptnet") for w in sorted(tails | heads)])
        conn.executemany(
            "INSERT OR IGNORE INTO edges(head, rel, tail, weight, source, status, "
            "version_added) VALUES(?,?,?,?,?,'active',1)",
            [(h, r, t, min(3.0, w), s) for h, r, t, w, s in kept])
        kg.set_meta(conn, "kg_version", 1)
        kg.set_meta(conn, "built_at", "2026-09-04")
        kg.log_audit(conn, "build", f"edges={len(kept)} words={len(seed)}")

    counts, low = write_coverage_reports(conn, seed)
    ratio = 1 - len(low) / len(counts)
    print(f"建库完成: {kg.db_stats(conn)}")
    print(f"覆盖红线(每词≥2边): {ratio:.1%} 达标, 不足 {len(low)} 词 → kg_low_coverage.csv")
    conn.close()
    return kept, dropped


def llm_clean(db_path, batch_size, limit, rels=None, workers=6):
    """LLM 层: 批量审边, 只删 LLM 指出的行。决策留痕 data/reports/llm_clean_decisions.jsonl。

    断点续跑: 已写入决策文件的批次自动跳过; 批间独立, 支持多线程并发。
    """
    import llm_client
    from concurrent.futures import ThreadPoolExecutor, as_completed
    if not llm_client.available():
        print("!! 未配置 OPENAI_API_KEY/KG_LLM_API_KEY — LLM 层跳过(规则层+人工层仍然有效)。")
        print("   配置示例: OPENAI_BASE_URL=https://api.stepfun.com/v1 "
              "KG_LLM_API_KEY=*** KG_LLM_MODEL=step-3.5-flash python build_kg.py --llm-clean")
        return
    conn = kg.connect(db_path)
    q = "SELECT id, head, rel, tail FROM edges WHERE status='active'"
    params = []
    if rels:
        q += " AND rel IN (" + ",".join("?" * len(rels)) + ")"
        params = list(rels)
    q += " ORDER BY id"
    if limit:
        q += f" LIMIT {limit}"
    rows = conn.execute(q, params).fetchall()
    n_batches = (len(rows) + batch_size - 1) // batch_size
    print(f"LLM 层: 待审 {len(rows):,} 条 → {n_batches} 批 × {batch_size}, "
          f"{workers} 线程, 模型 {llm_client.model()}", flush=True)

    out_path = REPORTS / "llm_clean_decisions.jsonl"
    done = set()
    if out_path.exists():  # 断点续跑
        with open(out_path, encoding="utf-8") as f:
            for line in f:
                try:
                    done.add(json.loads(line)["batch"])
                except Exception:  # noqa: BLE001
                    pass
    print(f"  已完成批次: {len(done)}/{n_batches}", flush=True)

    def review_one(bi):
        batch = rows[bi * batch_size:(bi + 1) * batch_size]
        payload = [{"head": r["head"], "rel": r["rel"], "tail": r["tail"]} for r in batch]
        return bi, batch, llm_client.review_edges(payload)

    t0, removed, failed = time.time(), 0, 0
    pool = ThreadPoolExecutor(max_workers=workers)
    dec = open(out_path, "a", encoding="utf-8")
    futures = {pool.submit(review_one, bi): bi
               for bi in range(n_batches) if bi not in done}
    for fut in as_completed(futures):
        bi = futures[fut]
        try:
            _, batch, verdicts = fut.result()
        except llm_client.LLMUnavailable as e:
            failed += 1
            print(f"  批 {bi}: 失败 {str(e)[:80]}", flush=True)
            continue
        dec.write(json.dumps({"batch": bi, "verdicts": verdicts,
                              "prompt": llm_client.PROMPT_VERSION},
                             ensure_ascii=False) + "\n")
        dec.flush()
        with conn:
            for v in verdicts:
                if 0 <= v["idx"] < len(batch):
                    r = batch[v["idx"]]
                    conn.execute(
                        "UPDATE edges SET status='removed', removed_by='llm', "
                        "reason=? WHERE id=?", (f"llm:{v['reason']}", r["id"]))
                    removed += 1
        done.add(bi)
        if len(done) % 50 == 0:
            print(f"  进度 {len(done)}/{n_batches} 批, 删 {removed} 条 "
                  f"({time.time()-t0:.0f}s)", flush=True)
    dec.close()
    pool.shutdown(wait=True)
    with conn:
        kg.log_audit(conn, "llm_clean", f"removed={removed} failed_batches={failed}")
    print(f"LLM 层完成: 删除 {removed} 条, 失败批 {failed}, 决策留痕 {out_path} "
          f"({time.time()-t0:.0f}s)")
    conn.close()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--seed", default=str(DATA / "seed.csv"))
    ap.add_argument("--out", default=str(DATA / "kg.db"))
    ap.add_argument("--edges", default=str(DATA / "edges_candidates.csv.gz"))
    ap.add_argument("--graphml", default=str(DATA / "kg.graphml"))
    ap.add_argument("--llm-clean", action="store_true",
                    help="在已建库上运行 LLM 审边层(需 API key)")
    ap.add_argument("--llm-batch", type=int, default=50)
    ap.add_argument("--llm-limit", type=int, default=0, help="只审前 N 条(0=全部)")
    ap.add_argument("--llm-rels", default="RelatedTo,Synonym,IsA,CapableOf",
                    help="只审指定关系(逗号分隔); 空串=全部关系")
    ap.add_argument("--llm-workers", type=int, default=6)
    args = ap.parse_args()

    REPORTS.mkdir(parents=True, exist_ok=True)
    if args.llm_clean:
        rels = [r.strip() for r in args.llm_rels.split(",") if r.strip()] or None
        llm_clean(args.out, args.llm_batch, args.llm_limit, rels, args.llm_workers)
        return
    if not Path(args.edges).exists():
        print("!! 缺少候选边文件, 请先运行 scripts/filter_conceptnet.py", file=sys.stderr)
        sys.exit(1)
    build_db(args.seed, args.out, args.edges)
    conn = kg.connect(args.out)
    nodes, ecount = kg.export_graphml(conn, args.graphml)
    print(f"kg.graphml: {nodes:,} 节点 / {ecount:,} 边 (Gephi 目视质检: apple 应与 fruit 同簇)")
    sample = kg.facts(conn, "apple", 8)
    print("apple 样例:", [f"{f['head']} -{f['rel']}-> {f['tail']}" for f in sample[:5]])
    conn.close()


if __name__ == "__main__":
    main()
