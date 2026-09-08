"""FR-E07 · 兜底模板库。

LLM 全挂（拔网线）时按场景命中人工模板，回应率 100%。

资产布局::

    assets/templates/<minister>.yaml
      templates:
        - id: xiaop-court-001
          scene: court          # court/adventure/bedtime/things/comfort/learn/invite/generic
          en: "Task done!"
          zh: "任务达成！"       # 中文脚手架（可空）
          slots: [task]         # 模板里出现 {task} 等占位符时必须声明

验收（tests 自动断言）：
- 每大臣 ≥50 条；
- 万物/朝会/安抚三类场景每大臣各有覆盖；
- 占位符与 slots 声明一致，未知 slot 拒绝加载；
- 命中策略：场景匹配 + 轮转避重（同一模板不连出两次）。
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence

import yaml

# 冠词自动修正：插槽填入元音开头的词后 "a apple" → "an apple"
_VOWEL_AN_RE = re.compile(r"\b[Aa] ([aeiou]\w*)")

SCENES = ("court", "adventure", "bedtime", "things", "comfort", "learn", "invite", "generic")

# FR-E07 点名要求的三类场景，每位大臣必须各有覆盖
REQUIRED_SCENES = ("court", "things", "comfort")

MIN_TEMPLATES_PER_MINISTER = 50

_PLACEHOLDER_RE = re.compile(r"\{([a-z_]+)\}")


@dataclass(frozen=True)
class Template:
    id: str
    minister: str
    scene: str
    en: str
    zh: str = ""
    slots: Sequence[str] = ()

    def render(self, **vars: str) -> str:
        """填占位符；未提供的 slot 用空串并在开发期可见（`?slot`），绝不抛异常。"""
        def fill(text: str) -> str:
            def sub(m: "re.Match[str]") -> str:
                name = m.group(1)
                val = vars.get(name, "")
                return val if val else f"?{name}"
            return _PLACEHOLDER_RE.sub(sub, text)
        out = fill(self.en)
        if self.zh and "|" not in out:
            out = f"{out} | {fill(self.zh)}"
        return _VOWEL_AN_RE.sub(lambda m: ("an " if m.group(0)[0] == "a" else "An ") + m.group(1), out)


@dataclass
class TemplateLibrary:
    """模板库：加载 + 场景命中 + 轮转避重。``stats()`` 供「模板占比 >30% 报警」监控。"""

    _by_minister: Dict[str, List[Template]] = field(default_factory=dict)
    _cursor: Dict[str, int] = field(default_factory=dict)
    _last_used: Dict[str, str] = field(default_factory=dict)

    # ---- 加载 ---------------------------------------------------------------
    def load_dir(self, templates_dir: str) -> int:
        count = 0
        if not os.path.isdir(templates_dir):
            return 0
        for fname in sorted(os.listdir(templates_dir)):
            if fname.endswith((".yaml", ".yml")):
                count += self.load_file(os.path.join(templates_dir, fname))
        return count

    def load_file(self, path: str) -> int:
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if not isinstance(data, dict) or "templates" not in data:
            raise ValueError(f"template file {path} missing 'templates'")
        default_minister = str(data.get("minister", "")).strip()
        loaded = 0
        for i, item in enumerate(data["templates"]):
            t = self._coerce(item, default_minister, path, i)
            self._by_minister.setdefault(t.minister, []).append(t)
            loaded += 1
        return loaded

    @staticmethod
    def _coerce(item: object, default_minister: str, path: str, idx: int) -> Template:
        if not isinstance(item, dict):
            raise ValueError(f"{path}[{idx}] not a mapping")
        en = str(item.get("en", "")).strip()
        if not en:
            raise ValueError(f"{path}[{idx}] empty 'en'")
        minister = str(item.get("minister", default_minister)).strip()
        if not minister:
            raise ValueError(f"{path}[{idx}] missing minister")
        scene = str(item.get("scene", "generic")).strip()
        if scene not in SCENES:
            raise ValueError(f"{path}[{idx}] unknown scene '{scene}'")
        slots = tuple(str(s) for s in item.get("slots", []) or ())
        used = set(_PLACEHOLDER_RE.findall(en)) | (
            set(_PLACEHOLDER_RE.findall(str(item.get("zh", "")))) if item.get("zh") else set()
        )
        unknown = used - set(slots)
        if unknown:
            raise ValueError(f"{path}[{idx}] placeholders {sorted(unknown)} not declared in slots")
        tid = str(item.get("id", f"{minister}-{scene}-{idx:03d}"))
        return Template(
            id=tid, minister=minister, scene=scene, en=en,
            zh=str(item.get("zh", "")).strip(), slots=slots,
        )

    # ---- 命中 ---------------------------------------------------------------
    def pick(self, minister: str, scene: str = "generic", **vars: str) -> Optional[Template]:
        """场景命中。优先选插槽齐备的模板（?slot 泄漏只作最后手段）。"""
        full_pool = [t for t in self._by_minister.get(minister, []) if t.scene == scene]
        if not full_pool:
            full_pool = [t for t in self._by_minister.get(minister, []) if t.scene == "generic"]
        if not full_pool:
            return None
        provided = set(vars) - {k for k, v in vars.items() if not v}
        pool = [t for t in full_pool if set(t.slots) <= provided] or full_pool
        cursor = self._cursor.get(minister, 0)
        base = min(cursor, max(len(pool) - 1, 0))
        # 轮转 + 避免与上一条重复
        for step in range(len(pool)):
            t = pool[(base + step) % len(pool)]
            if t.id != self._last_used.get(minister):
                chosen = t
                self._cursor[minister] = (base + step + 1) % len(pool)
                self._last_used[minister] = chosen.id
                return chosen
        chosen = pool[base % len(pool)]
        self._cursor[minister] = (base + 1) % len(pool)
        return chosen

    # ---- 观测 ---------------------------------------------------------------
    def count(self, minister: Optional[str] = None) -> int:
        if minister:
            return len(self._by_minister.get(minister, []))
        return sum(len(v) for v in self._by_minister.values())

    def scene_count(self, minister: str, scene: str) -> int:
        return sum(1 for t in self._by_minister.get(minister, []) if t.scene == scene)

    def stats(self) -> Dict[str, Dict[str, int]]:
        return {
            m: {s: sum(1 for t in ts if t.scene == s) for s in SCENES}
            for m, ts in self._by_minister.items()
        }

    def all_templates(self, minister: Optional[str] = None) -> List[Template]:
        if minister:
            return list(self._by_minister.get(minister, []))
        return [t for ts in self._by_minister.values() for t in ts]
