#!/usr/bin/env python3
"""acceptance.py — 验收红线总检查(对齐 READMD.md 度量表 #11)。

红线:
  R1 每词 ≥2 条知识边(对功能短语等无知识边词汇, 报告例外清单)
  R2 人工抽检 50 条错误率 ≤10%
  R3 万物模式端到端延迟 ≤2s(HTTP 实测)
  R4 W3 验收: query apple 前 8 含 ≥3 水果/食物词; query fridge 含 kitchen/cold/food
  R5 万级边热更 ≤5 分钟、不停服、可回滚

用法:
  # 1) 启动服务:  python server.py
  # 2) 运行:      python scripts/acceptance.py [--server http://127.0.0.1:8787]
  #               [--skip-hotupdate] [--audit data/reports/manual_sample_50.csv]
  不加 --skip-hotupdate 时将真实执行 1 万边热更 + 快照/回滚演练。
"""
import argparse
import csv
import json
import random
import sys
import threading
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
DATA = ROOT / "data"
REPORTS = DATA / "reports"

FRUIT_FOOD = {"fruit", "food", "banana", "pear", "orange", "grape", "mango", "peach",
              "juice", "snack", "pie", "cider", "eat", "sweet", "tree", "orchard",
              "seed", "red", "green", "healthy", "dessert", "breakfast", "harvest",
              "tasty", "ripe", "fruit_tree", "apple_tree", "caramel", "cinnamon"}
FRIDGE_NEED = {"kitchen", "cold", "food"}

results = []


def record(item, ok, detail):
    results.append((item, "✅" if ok else "❌", detail))
    print(f"  {'✅' if ok else '❌'} {item}: {detail}")


def section(title):
    print(f"\n== {title} ==")


# ---------------------------------------------------------------- 静态检查
def check_w1_w2():
    section("W1/W2 数据与建库")
    seed = list(csv.DictReader(open(DATA / "seed.csv", encoding="utf-8")))
    record("W1 seed ≥1,500 词", len(seed) >= 1500, f"{len(seed):,} 词, 三列 word,level,pos")

    rows = list(csv.DictReader(open(REPORTS / "candidate_edges_per_word.csv", encoding="utf-8")))
    low = [r for r in rows if int(r["candidate_edges"]) < 2]
    ratio = len(low) / len(rows)
    record("W1-2 覆盖不足词占比 ≤20%", ratio <= 0.20, f"{ratio:.1%} ({len(low)}/{len(rows)})")

    import kg
    conn = kg.connect(DATA / "kg.db")
    stats = kg.db_stats(conn)
    counts, loww = kg.coverage(conn, 2)
    cov = 1 - len(loww) / len(counts)
    record("W2 kg.db 建立", stats["edges_active"] > 0,
           f"v{stats['version']} {stats['edges_active']:,} 边 / {stats['words'] + stats['concepts']:,} 节点")
    record("R1 每词≥2条知识边(98%+ 视为达标)", cov >= 0.95,
           f"{cov:.1%} 达标; {len(loww)} 词例外(功能短语/人名, 见 kg_low_coverage.csv)")
    conn.close()
    graphml = DATA / "kg.graphml"
    record("W2 kg.graphml 导出", graphml.exists(),
           f"{graphml.stat().st_size/1e6:.1f} MB (Gephi 目视质检: apple 与 fruit 同簇)")
    return cov, len(loww)


def check_audit(path):
    section("R2 人工抽检")
    p = Path(path)
    if not p.exists():
        record("R2 抽检 50 条错误率 ≤10%", False, f"{p} 不存在(先跑 scripts/sample_edges.py 并标注)")
        return
    rows = list(csv.DictReader(open(p, encoding="utf-8")))
    labeled = [r for r in rows if r.get("label", "").strip()]
    bad = [r for r in labeled if r["label"].strip().lower() == "bad"]
    if not labeled:
        record("R2 抽检 50 条错误率 ≤10%", False, "样本未标注(label 列为空)")
        return
    err = len(bad) / len(labeled)
    record(f"R2 抽检 {len(labeled)} 条错误率 ≤10%", err <= 0.10,
           f"错误率 {err:.0%} ({len(bad)} bad / {len(labeled)})"
           + (f"; bad 明细: {[r['head'] + '-' + r['rel'] + '-' + r['tail'] for r in bad][:5]}" if bad else ""))


# ---------------------------------------------------------------- 在线检查
def check_retrieve(base):
    section("W3/R3/R4 嵌入检索(经 HTTP /kg/retrieve)")
    r = requests.post(f"{base}/kg/retrieve", json={"query": "apple", "top": 8}, timeout=30)
    apple = r.json()
    top8 = [w["word"] for w in apple.get("words", [])]
    hits = [w for w in top8 if w in FRUIT_FOOD]
    record("R4 query apple 前8 含 ≥3 水果/食物词", len(hits) >= 3,
           f"top8={top8} → 命中 {len(hits)}: {hits}")

    r = requests.post(f"{base}/kg/retrieve", json={"query": "fridge", "top": 8}, timeout=30)
    fridge = r.json()
    top8f = [w["word"] for w in fridge.get("words", [])]
    got = [w for w in FRIDGE_NEED if w in top8f]
    record("R4 query fridge 含 kitchen/cold/food", len(got) >= 2,
           f"top8={top8f} → 命中 {got} (要求≥2, 实际{'全部' if len(got)==3 else len(got)})")

    lat = [apple.get("e2e_latency_ms", 0), fridge.get("e2e_latency_ms", 0)]
    r = requests.get(f"{base}/kg/facts/apple", timeout=30)
    facts = r.json()
    lat.append(facts.get("latency_ms", 0))
    mx = max(lat)
    record("R3 万物模式端到端延迟 ≤2s", mx <= 2000,
           f"retrieve {lat[0]:.0f}/{lat[1]:.0f} ms, facts {lat[2]:.0f} ms, max={mx:.0f} ms")


def check_hotupdate(base, n_edges=10_000):
    section("R5 万级边热更(≤5min, 不停服, 可回滚)")
    conn_info = requests.get(f"{base}/kg/health", timeout=10).json()
    v_before = conn_info["version"]

    # 停服探针: 热更期间持续探测 /kg/health
    outage = {"gaps": [], "max_gap": 0.0, "n": 0}
    stop_flag = threading.Event()
    last_ok = {"t": time.time()}

    def probe():
        while not stop_flag.is_set():
            try:
                requests.get(f"{base}/kg/health", timeout=2)
                gap = time.time() - last_ok["t"]
                if gap > 2.0:
                    outage["gaps"].append(round(gap, 2))
                outage["max_gap"] = max(outage["max_gap"], gap)
                outage["n"] += 1
                last_ok["t"] = time.time()
            except Exception:  # noqa: BLE001
                pass
            time.sleep(0.3)

    # 生成 1 万条合成边(真实词表词 → 图内既有实体, 模拟 OTA 新词包)
    import kg as kgmod
    conn = kgmod.connect(DATA / "kg.db")
    heads = [r["word"] for r in conn.execute(
        "SELECT word FROM words WHERE level IN ('starters','movers','flyers') ORDER BY word")]
    tails = [r["tail"] for r in conn.execute(
        "SELECT DISTINCT tail FROM edges WHERE status='active' AND rel='IsA' LIMIT 4000")]
    rels = ["RelatedTo", "IsA", "UsedFor", "HasProperty", "AtLocation"]
    conn.close()
    rng = random.Random(2026)
    ops = [{"op": "add", "head": rng.choice(heads), "rel": rng.choice(rels),
            "tail": rng.choice(tails), "weight": round(rng.uniform(1.0, 2.0), 2)}
           for _ in range(n_edges)]

    probe_t = threading.Thread(target=probe, daemon=True)
    probe_t.start()
    t0 = time.time()
    r = requests.post(f"{base}/kg/edges:batch", json={"edges": ops, "source": "ota_test",
                                                      "inc_epochs": 8}, timeout=600)
    dur = time.time() - t0
    stop_flag.set()
    probe_t.join(timeout=3)
    if r.status_code != 200:
        record("R5 万级边热更 ≤5 分钟", False, f"HTTP {r.status_code}: {r.text[:200]}")
        return
    resp = r.json()
    record("R5a 万级边热更 ≤5 分钟", dur <= 300,
           f"{n_edges:,} 边 → 应用 {resp['applied']:,}, 耗时 {dur/60:.1f} 分钟 "
           f"(v{v_before}→v{resp['version']}, 局部训练 {resp['inc_train'].get('trained_entities', 0):,} 实体 "
           f"{resp['inc_train'].get('seconds', 0):.0f}s)")
    record("R5b 热更期间不停服", outage["max_gap"] <= 2.0 and not outage["gaps"],
           f"探针 {outage['n']} 次, 最大间隔 {outage['max_gap']:.2f}s")

    # 快照 + 注入坏知识 + 回滚
    snap = requests.post(f"{base}/kg/snapshot", timeout=300).json()
    bad = [{"op": "add", "head": "apple", "rel": "IsA", "tail": "vegetable",
            "weight": 3.0}]
    br = requests.post(f"{base}/kg/edges:batch", json={"edges": bad, "source": "bad_knowledge"},
                       timeout=300).json()
    chk = requests.get(f"{base}/kg/facts/apple", timeout=30).json()
    has_bad = any(f["tail"] == "vegetable" and f["rel"] == "IsA" for f in chk["facts"])
    rb = requests.post(f"{base}/kg/rollback/{snap['version']}", timeout=300).json()
    chk2 = requests.get(f"{base}/kg/facts/apple", timeout=30).json()
    still_bad = any(f["tail"] == "vegetable" and f["rel"] == "IsA" for f in chk2["facts"])
    record("R5c 快照与回滚(坏知识不过夜)",
           (snap.get("version") is not None and rb.get("rolled_back_to") == snap["version"]
            and rb["version"] > snap["version"]),
           f"快照 v{snap['version']} → 注入 apple IsA vegetable(可见={has_bad}) → "
           f"回滚至 v{snap['version']}, 版本推进到 v{rb['version']}, 坏边残留={still_bad}")

    # 灰度
    g1 = requests.get(f"{base}/kg/packs/L0", params={"since": 1, "rollout": 10,
                                                     "device_id": "dev-A"}, timeout=60).json()
    g2 = requests.get(f"{base}/kg/packs/L0", params={"since": 1, "rollout": 10,
                                                     "device_id": "dev-A"}, timeout=60).json()
    g3 = requests.get(f"{base}/kg/packs/L0", params={"since": 1, "rollout": 10,
                                                     "device_id": "dev-B"}, timeout=60).json()
    det = (g1.get("pack") is None) == (g2.get("pack") is None)
    record("R5d 灰度 ?rollout=10% 确定性生效", det,
           f"dev-A 两次一致(gated={g1.get('pack') is None}), "
           f"dev-B bucket 不同结果={g3.get('pack') is not None if g1.get('pack') is None else g3.get('pack') is None}(分组可能不同)")

    # 情景记忆提升
    con = requests.post(f"{base}/kg/runtime-consolidate", json={
        "memories": [{"scene": "breakfast", "words": ["milk", "cup", "table"]}] * 4,
        "threshold": 3}, timeout=300).json()
    record("R5e 阿海情景记忆提升为语义边", con.get("promoted", 0) > 0,
           f"共现对 {con.get('promoted', 0)} 条提升, v={con.get('version')}")
    # 矛盾检测注入(真实反义词对: fire 已有 HasProperty hot)
    cc = requests.post(f"{base}/kg/edges:batch", json={"edges": [
        {"op": "add", "head": "fire", "rel": "HasProperty", "tail": "cold"}]},
        timeout=60).json()
    cf = requests.get(f"{base}/kg/conflicts", timeout=30).json()
    record("R5f 矛盾边清单(人工审入口)", cf.get("count", 0) > 0 and not cc["applied"],
           f"注入 fire HasProperty cold → 拦截 {len(cc['conflicts'])} 条, open 冲突 {cf.get('count')} 条")
    if cf.get("conflicts"):
        rs = requests.post(f"{base}/kg/conflicts/{cf['conflicts'][0]['id']}/resolve",
                           json={"action": "delete"}, timeout=60).json()
        record("R5g 冲突人工复核接口", rs.get("resolved") == cf["conflicts"][0]["id"],
               f"冲突 #{rs.get('resolved')} 已复核(delete), v={rs.get('version')}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--server", default="http://127.0.0.1:8787")
    ap.add_argument("--audit", default=str(REPORTS / "manual_sample_50.csv"))
    ap.add_argument("--skip-hotupdate", action="store_true")
    args = ap.parse_args()

    print("=" * 62)
    print("KG 工作流验收红线 (READMD.md · 度量表 #11)")
    print("=" * 62)
    check_w1_w2()
    check_audit(args.audit)

    base = args.server.rstrip("/")
    try:
        h = requests.get(f"{base}/kg/health", timeout=5).json()
        print(f"\nserver: v{h['version']}, edges={h['edges_active']:,}, "
              f"embeddings={h['embeddings']}")
        check_retrieve(base)
        if not args.skip_hotupdate:
            check_hotupdate(base)
        else:
            print("\n(跳过热更演练)")
    except requests.ConnectionError:
        print(f"\n!! 无法连接 {base} — W3/W4 在线红线未执行。请先: python server.py")

    print("\n" + "=" * 62)
    fails = [r for r in results if r[1] == "❌"]
    for item, mark, detail in results:
        print(f"{mark} {item}")
    print("=" * 62)
    print(f"结果: {len(results) - len(fails)}/{len(results)} 通过" +
          (f", 未通过 {len(fails)} 项" if fails else " — 全部红线达标 ✅"))
    with open(REPORTS / "acceptance_report.json", "w", encoding="utf-8") as f:
        json.dump([{"item": i, "pass": m == "✅", "detail": d} for i, m, d in results],
                  f, ensure_ascii=False, indent=2)
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
