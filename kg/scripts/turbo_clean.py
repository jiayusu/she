#!/usr/bin/env python3
"""turbo_clean.py — LLM 层高速通道: step-1o-turbo-vision 无思考模型反向批审。

与 build_kg.py --llm-clean(推理模型, id 正向)并行, 双向夹击噪声边。
turbo 几乎不消耗输出 token, 与推理任务共享配额时影响很小。

用法:
  OPENAI_BASE_URL=... KG_LLM_API_KEY=... KG_LLM_MODEL=step-1o-turbo-vision \
  python scripts/turbo_clean.py --passes 3
"""
import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import cleaning  # noqa: E402  # noqa: F401 (触发 COMMON_LEXICON 说明文档)
import kg  # noqa: E402
import llm_client  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
REPORTS = DATA / "reports"

STRICT_NOTE = ("从严审: 儿童直觉上无意义的关联、抽象/书面/专业搭配、依赖冷僻义项的, 全部删除。"
               "RelatedTo 只保留两端都是儿童熟悉的具体事物/动作/感官属性且直接相关的。"
               "注意方向: X UsedFor Y 表示 X 被用于 Y, X PartOf Y 表示 X 是 Y 的一部分, 方向反了删除。"
               "快速判断, 不要过度分析。")


def run_pass(conn, pass_no, batch_size, out, min_id_seen):
    """单轮反向扫描: 从当前最小已审 id 继续往 id 小的方向走。"""
    cursor = min_id_seen
    reviewed, removed, t0 = 0, 0, time.time()
    while True:
        rows = conn.execute(
            "SELECT id, head, rel, tail FROM edges WHERE status='active' "
            "AND rel IN ('RelatedTo','Synonym','IsA','CapableOf') AND id < ? "
            "ORDER BY id DESC LIMIT ?", (cursor, batch_size)).fetchall()
        if not rows:
            return reviewed, removed, cursor
        cursor = min(r["id"] for r in rows)
        payload = [{"head": r["head"], "rel": r["rel"], "tail": r["tail"]} for r in rows]
        lines = "\n".join(f'{i}. {e["head"]} | {e["rel"]} | {e["tail"]}'
                          for i, e in enumerate(payload))
        user = (f"待审边 {len(payload)} 条:\n{lines}\n"
                f"按提示词契约只输出紧凑 JSON 数组(二元组)。{STRICT_NOTE}")
        try:
            raw = llm_client._chat([{"role": "system", "content": llm_client._load_prompt()},
                                    {"role": "user", "content": user}])
            verdicts = llm_client._parse_json_list(raw)
        except llm_client.LLMUnavailable as e:
            print(f"  pass{pass_no} 批 cursor={cursor}: 失败 {str(e)[:80]}", flush=True)
            continue
        out.write(json.dumps({"pass": pass_no, "cursor": cursor, "verdicts": verdicts,
                              "prompt": llm_client.PROMPT_VERSION},
                             ensure_ascii=False) + "\n")
        out.flush()
        with conn:
            for v in verdicts:
                if 0 <= v["idx"] < len(rows):
                    r = rows[v["idx"]]
                    conn.execute("UPDATE edges SET status='removed', removed_by='llm', "
                                 "reason=? WHERE id=?", (f"llm:{v['reason']}", r["id"]))
                    removed += 1
        reviewed += len(rows)
        if reviewed % 500 < batch_size:
            print(f"  pass{pass_no}: 已审 {reviewed:,} (cursor={cursor}), 删 {removed:,} "
                  f"({time.time()-t0:.0f}s)", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(DATA / "kg.db"))
    ap.add_argument("--batch", type=int, default=50)
    ap.add_argument("--passes", type=int, default=3)
    ap.add_argument("--from-max", action="store_true", help="忽略断点, 从最大 id 重新扫")
    args = ap.parse_args()

    conn = kg.connect(args.db)
    out_path = REPORTS / "llm_clean_decisions_turbo.jsonl"
    # 断点续跑: 从已审的最小 cursor 继续
    min_id_seen = 10 ** 12
    if out_path.exists() and not args.from_max:
        with open(out_path, encoding="utf-8") as f:
            for line in f:
                try:
                    min_id_seen = min(min_id_seen, json.loads(line)["cursor"])
                except Exception:  # noqa: BLE001
                    pass
    print(f"turbo 清洗: {args.passes} 轮, 批 {args.batch}, 起始 cursor={min_id_seen}")
    total_removed = 0
    with open(out_path, "a", encoding="utf-8") as out:
        for p in range(1, args.passes + 1):
            reviewed, removed, min_id_seen = run_pass(conn, p, args.batch, out, min_id_seen)
            total_removed += removed
            print(f"pass{p} 完成: 审 {reviewed:,}, 删 {removed:,}", flush=True)
            if reviewed == 0:
                break  # 全域审完
            min_id_seen = 10 ** 12  # 下一轮从头(反向)再扫
    with conn:
        kg.log_audit(conn, "turbo_clean", f"removed={total_removed} passes={args.passes}")
    print(f"turbo 清洗完成: 共删 {total_removed:,} 条")
    conn.close()


if __name__ == "__main__":
    main()
