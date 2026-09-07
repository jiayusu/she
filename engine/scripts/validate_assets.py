# -*- coding: utf-8 -*-
"""资产校验脚本（CI 首跑）：提示词冻结完整性 + 模板库验收 + 路由评测 + 词汇池。

验收对应：
- FR-E01 提示词全部可解析、无坏文件、可渲染；
- FR-E07 每大臣 ≥50 条模板、三类场景覆盖、全量可渲染；
- FR-E02 标注集路由准确率 ≥90%；
- FR-E05 红线 L1≤5 / L2≤10 / L3+≤16 自检。

跑法::

    cd engine
    python scripts/validate_assets.py
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from she_engine.levels import MAX_SENTENCE_WORDS, POOLS               # noqa: E402
from she_engine.prompts import MinisterRegistry                        # noqa: E402
from she_engine.router import EVAL_SET, Router, RuleClassifier          # noqa: E402
from she_engine.templates import REQUIRED_SCENES, TemplateLibrary      # noqa: E402

MINISTERS = ["xiaop", "laonie", "xingxing", "ahai", "wangguan"]
ok = True


def check(name: str, cond: bool, detail: str = "") -> None:
    global ok
    mark = "✅" if cond else "❌"
    if not cond:
        ok = False
    print(f"  {mark} {name}" + (f" —— {detail}" if detail and not cond else ""))


def main() -> int:
    print("═" * 64)
    print("① FR-E01 提示词系统（版本化冻结 + 三件套完整）")
    print("═" * 64)
    reg = MinisterRegistry(os.path.join(ROOT, "assets", "ministers"))
    check("无坏 YAML 文件", not reg.load_errors, str(reg.load_errors))
    check("五大大臣全部注册", sorted(reg.ids()) == sorted(MINISTERS), str(reg.ids()))
    for mid in MINISTERS:
        spec = reg.get(mid)
        text = spec.render_system("L", "S", "R", "C", "O")
        check(f"{mid}: 三件套 + 渲染无残留占位符",
              bool(spec.voice_id) and spec.light_color.startswith("#") and "{" not in text)

    print()
    print("═" * 64)
    print("② FR-E07 兜底模板库")
    print("═" * 64)
    lib = TemplateLibrary()
    lib.load_dir(os.path.join(ROOT, "assets", "templates"))
    for mid in MINISTERS:
        n = lib.count(mid)
        scenes_ok = all(lib.scene_count(mid, s) > 0 for s in REQUIRED_SCENES)
        check(f"{mid}: ≥50 条（实际 {n}）+ 万物/朝会/安抚覆盖", n >= 50 and scenes_ok)
    bad_render = [t.id for t in lib.all_templates()
                  if not t.render(**{s: "x" for s in t.slots})]
    check("全量模板可渲染", not bad_render, str(bad_render[:5]))

    print()
    print("═" * 64)
    print("③ FR-E02 查询路由（标注集 60 条）")
    print("═" * 64)
    router = Router(RuleClassifier())
    hits = sum(1 for text, expected in EVAL_SET if router.route(text).intent == expected)
    acc = hits / len(EVAL_SET)
    check(f"准确率 {acc:.1%} ≥ 90%（错误率 ≤10%）", acc >= 0.90,
          f"misses: {[t for t, e in EVAL_SET if router.route(t).intent != e]}")
    intents_hit = {router.route(t).intent for t, _ in EVAL_SET}
    check("六类意图全部被映射表覆盖", len(intents_hit) == 6, str(intents_hit))

    print()
    print("═" * 64)
    print("④ FR-E05 分级句式红线")
    print("═" * 64)
    check("L1≤5 / L2≤10 / L3+≤16",
          MAX_SENTENCE_WORDS[1] == 5 and MAX_SENTENCE_WORDS[2] == 10
          and MAX_SENTENCE_WORDS[3] == 16 and MAX_SENTENCE_WORDS[4] == 16
          and MAX_SENTENCE_WORDS[5] == 16,
          str(MAX_SENTENCE_WORDS))
    check("L0-L5 词汇池齐备", all(len(POOLS[i]) >= 10 for i in range(6)))

    print()
    print("═" * 64)
    print(("✅ 全部通过" if ok else "❌ 存在失败项 —— 禁止上线"))
    print("═" * 64)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
