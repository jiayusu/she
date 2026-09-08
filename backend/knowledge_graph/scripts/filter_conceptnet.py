#!/usr/bin/env python3
"""W1-2 整理筛选: ConceptNet 英文断言 dump → 候选边 + 覆盖率报告

对 raw/conceptnet-assertions-5.7.0.csv.gz(~2GB 解压, 34M 行)做流式过滤:
  1. 只保留 /c/en/ → /r/<REL> → /c/en/ 的英文断言, REL ∈ 10 种白名单关系
  2. 至少一端命中 seed.csv 词表(含英美拼写变体归一)
  3. (head, rel, tail) 去重取最大 weight, 保留 sense 后缀供 W2 规则层使用

产出:
  - data/edges_candidates.csv.gz            候选边
  - data/reports/candidate_edges_per_word.csv  每词候选边数
  - data/reports/low_coverage_words.csv     覆盖不足词清单(<2 条边)
  - 退出标准: 覆盖不足词占比 ≤20%, 超出则以非零码退出
"""
import argparse
import csv
import gzip
import re
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
REPORTS = DATA / "reports"

# README 列出的关系白名单(按名单全收, RelatedTo 噪声大但覆盖广, W2 清洗层再压)
RELATIONS = {"RelatedTo", "UsedFor", "HasProperty", "AtLocation", "MadeOf",
             "CapableOf", "PartOf", "Synonym", "FormOf", "IsA"}
MIN_COVERAGE = 2
EXIT_LIMIT = 0.20  # 覆盖不足词占比上限
WORD_RE = re.compile(r"^[a-z][a-z_]{0,39}$")
WEIGHT_RE = re.compile(r'"weight":\s*([0-9]+(?:\.[0-9]+)?)')


def lemma(uri: str):
    """'/c/en/apple/n/fruit' → ('apple', 'n/fruit'); 非英文返回 None"""
    if not uri.startswith("/c/en/"):
        return None
    parts = uri.split("/")
    # ['', 'c', 'en', 'apple', 'n', 'fruit']
    if len(parts) < 4:
        return None
    return parts[3], "/".join(parts[4:])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dump", default=str(ROOT / "raw/conceptnet-assertions-5.7.0.csv.gz"))
    ap.add_argument("--seed", default=str(DATA / "seed.csv"))
    ap.add_argument("--variants", default=str(DATA / "word_variants.csv"))
    ap.add_argument("--out", default=str(DATA / "edges_candidates.csv.gz"))
    ap.add_argument("--min-weight", type=float, default=0.9)
    args = ap.parse_args()

    seed = set()
    with open(args.seed, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            seed.add(row["word"])
    canonical = {w: w for w in seed}  # 词表内词 → 自身
    with open(args.variants, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            canonical[row["variant"]] = row["word"]  # color → colour

    REPORTS.mkdir(parents=True, exist_ok=True)
    edges = {}          # (head, rel, tail) -> [weight, head_sense, tail_sense]
    rel_counter = Counter()
    t0, n_lines, n_en, n_kept = time.time(), 0, 0, 0

    with gzip.open(args.dump, "rt", encoding="utf-8", errors="ignore") as f:
        for line in f:
            n_lines += 1
            if n_lines % 5_000_000 == 0:
                print(f"  ... {n_lines/1e6:.0f}M 行, en-en {n_en/1e6:.1f}M, "
                      f"保留 {n_kept/1e3:.0f}k, {time.time()-t0:.0f}s", flush=True)
            cols = line.rstrip("\n").split("\t")
            # dump 格式: /a/[...] \t /r/Rel \t /c/en/word/pos/sense \t /c/en/word \t {json}
            if len(cols) >= 5 and cols[0].startswith("/a/"):
                rel_uri, start_uri, end_uri, meta = cols[1], cols[2], cols[3], cols[4]
            elif len(cols) >= 4:  # 兼容旧式 4 列: start \t rel \t end \t json
                start_uri, rel_uri, end_uri, meta = cols[0], cols[1], cols[2], cols[3]
            else:
                continue
            if not rel_uri.startswith("/r/"):
                continue
            rel = rel_uri[3:]
            if rel not in RELATIONS:
                continue
            hs = lemma(start_uri)
            ts = lemma(end_uri)
            if hs is None or ts is None:
                continue
            n_en += 1
            h, h_sense = hs
            t, t_sense = ts
            if h == t or not WORD_RE.match(h) or not WORD_RE.match(t):
                continue
            if h in canonical:
                h = canonical[h]
            elif t in canonical:
                t = canonical[t]
            else:
                continue
            if len(h) > 40 or len(t) > 40 or len(h.split("_")) > 3 or len(t.split("_")) > 3:
                continue
            m = WEIGHT_RE.search(meta)
            weight = float(m.group(1)) if m else 1.0
            if weight < args.min_weight:
                continue
            key = (h, rel, t)
            cur = edges.get(key)
            if cur is None:
                edges[key] = [weight, h_sense, t_sense]
            elif weight > cur[0]:
                cur[0] = weight
                cur[1], cur[2] = h_sense, t_sense
            n_kept += 1

    print(f"扫描 {n_lines/1e6:.1f}M 行 / 英文断言 {n_en/1e6:.1f}M / 唯一候选边 {len(edges):,}")

    out_path = Path(args.out)
    with gzip.open(out_path, "wt", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["head", "rel", "tail", "weight", "head_sense", "tail_sense"])
        for (h, rel, t), (wt, hs, ts) in sorted(edges.items()):
            w.writerow([h, rel, t, wt, hs, ts])

    per_word = Counter()
    for (h, rel, t) in edges:
        per_word[h] += 1
        per_word[t] += 1
    seed_counts = {w_: per_word.get(w_, 0) for w_ in seed}

    with open(REPORTS / "candidate_edges_per_word.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["word", "candidate_edges"])
        for w_ in sorted(seed_counts, key=lambda x: -seed_counts[x]):
            w.writerow([w_, seed_counts[w_]])

    low = [w_ for w_, c in seed_counts.items() if c < MIN_COVERAGE]
    with open(REPORTS / "low_coverage_words.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["word", "candidate_edges"])
        for w_ in sorted(low):
            w.writerow([w_, seed_counts[w_]])

    ratio = len(low) / len(seed_counts) if seed_counts else 1.0
    print(f"每词候选边: 中位数 {sorted(seed_counts.values())[len(seed_counts)//2]}, "
          f"覆盖不足(<{MIN_COVERAGE}) {len(low)} 词, 占比 {ratio:.1%}")
    print(f"退出标准: 覆盖不足占比 ≤20% → {'通过' if ratio <= EXIT_LIMIT else '未通过'}")
    print(f"产出: {out_path}")
    if ratio > EXIT_LIMIT:
        print("!! 覆盖不足词占比超过 20%, W1-2 不达标", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
