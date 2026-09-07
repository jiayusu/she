"""FR-E01 五大人格提示词系统 + FR-E10 新大臣 DLC 注册。

资产布局（提示词冻结进版本库，线上可回滚任意历史版本 = 按版本号选文件）::

    assets/ministers/<id>/v1.yaml      # v1、v2…… 永不覆盖，只增版本
    assets/ministers/<id>/v2.yaml

YAML 三件套（FR-E10：新人格 = 一个提示词文件 + 音色 ID + 灯色，注册零代码）::

    id: mengmeng            # 大臣 id（memory_write/speaker 用）
    name: 萌萌              # 显示名
    version: 1
    voice_id: otter_ahai_v1 # → TTS 音色
    light_color: "#5FB8FF"  # → 硬件灯色
    personality: …          # 人设
    tone: …                 # 语气
    catchphrases: [...]     # 口头禅（盲测区分度的锚点）
    prohibitions: [...]     # 禁则（红线，注入 prompt 且可被后置校验引用）
    style_rules: [...]      # 句式风格硬规则
    system_prompt: |        # 模板：渲染时填 {level_rules} {scene_directive}
                             # {recast_directive} {ctx_block} {output_format}
    blind_markers: [...]    # 风格盲测判据（自动化盲测代理指标用）

Registry:
    registry = MinisterRegistry(assets_dir)
    registry.get("ahai")                 → 当前 pin 版本
    registry.rollback("ahai", version=1) → 拉回 v1
    registry.register_file(path)         → DLC 热注册（FR-E10）
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import yaml


@dataclass(frozen=True)
class MinisterSpec:
    """一位大臣的冻结提示词 + 三件套。frozen：运行期不可改，改人格=发新版本。"""

    id: str
    name: str
    version: int
    voice_id: str
    light_color: str
    personality: str
    tone: str
    catchphrases: List[str]
    prohibitions: List[str]
    style_rules: List[str]
    system_prompt: str
    blind_markers: List[str] = field(default_factory=list)
    source_path: str = ""

    # ---- 渲染（动态部分由引擎注入，人格本体冻结） --------------------------
    def render_system(
        self,
        level_rules: str,
        scene_directive: str,
        recast_directive: str = "",
        ctx_block: str = "",
        output_format: str = "",
    ) -> str:
        persona = {
            "personality": self.personality.strip(),
            "tone": self.tone.strip(),
            "catchphrases": " / ".join(self.catchphrases),
            "prohibitions": " ; ".join(self.prohibitions),
            "style_rules": " ; ".join(self.style_rules),
        }
        dynamic = {
            "level_rules": level_rules,
            "scene_directive": scene_directive,
            "recast_directive": recast_directive,
            "ctx_block": ctx_block,
            "output_format": output_format,
        }
        body = self.system_prompt
        for key, val in {**persona, **dynamic}.items():
            body = body.replace("{" + key + "}", val)
        # 冻结校验：渲染后不许残留未填占位符（提示词文件写错立刻暴露）
        leftover = re.findall(r"\{[a-z_]+\}", body)
        if leftover:
            raise ValueError(f"prompt '{self.id}' v{self.version} unfilled placeholders: {leftover}")
        return body


class MinisterRegistry:
    """扫描式注册表：目录里躺一个合法 YAML = 上线一位大臣（FR-E10 零代码）。"""

    def __init__(self, assets_dir: str) -> None:
        self._assets_dir = assets_dir
        self._versions: Dict[str, Dict[int, MinisterSpec]] = {}
        self._pinned: Dict[str, int] = {}
        self.load_errors: Dict[str, str] = {}   # 文件路径 → 解析/校验错误（CI 必须为空）
        self.reload()

    # ---- 加载 ---------------------------------------------------------------
    def reload(self) -> int:
        """重扫目录。返回当前注册的大臣数。坏文件记入 load_errors，不炸主链路。"""
        self._versions.clear()
        self._pinned.clear()
        self.load_errors.clear()
        if not os.path.isdir(self._assets_dir):
            return 0
        for minister_dir in sorted(os.listdir(self._assets_dir)):
            mdir = os.path.join(self._assets_dir, minister_dir)
            if not os.path.isdir(mdir):
                continue
            for fname in sorted(os.listdir(mdir)):
                m = re.fullmatch(r"v(\d+)\.ya?ml", fname)
                if not m:
                    continue
                path = os.path.join(mdir, fname)
                try:
                    spec = self._load_file(path)
                    if spec is None:
                        self.load_errors[path] = "empty or non-mapping document"
                        continue
                except (ValueError, yaml.YAMLError, OSError) as exc:
                    self.load_errors[path] = f"{type(exc).__name__}: {exc}"
                    continue
                self._versions.setdefault(spec.id, {})[spec.version] = spec
        for mid, vers in self._versions.items():
            self._pinned[mid] = max(vers)  # 默认最新版
        return len(self._versions)

    @staticmethod
    def _load_file(path: str) -> Optional[MinisterSpec]:
        try:
            with open(path, encoding="utf-8") as f:
                d = yaml.safe_load(f)
        except (OSError, yaml.YAMLError):
            return None
        if not isinstance(d, dict):
            return None
        missing = [
            k for k in ("id", "name", "version", "voice_id", "light_color", "system_prompt")
            if not d.get(k)
        ]
        if missing:
            raise ValueError(f"minister file {path} missing fields: {missing}")
        spec = MinisterSpec(
            id=str(d["id"]),
            name=str(d["name"]),
            version=int(d["version"]),
            voice_id=str(d["voice_id"]),
            light_color=str(d["light_color"]),
            personality=str(d.get("personality", "")),
            tone=str(d.get("tone", "")),
            catchphrases=[str(x) for x in d.get("catchphrases", [])],
            prohibitions=[str(x) for x in d.get("prohibitions", [])],
            style_rules=[str(x) for x in d.get("style_rules", [])],
            system_prompt=str(d["system_prompt"]),
            blind_markers=[str(x) for x in d.get("blind_markers", [])],
            source_path=path,
        )
        # id 必须与目录一致，防「文件搬家后路由指错人」
        parent = os.path.basename(os.path.dirname(path))
        if parent not in (spec.id, "_pending"):
            raise ValueError(f"minister dir '{parent}' != spec.id '{spec.id}' ({path})")
        return spec

    # ---- 查询 ---------------------------------------------------------------
    def ids(self) -> List[str]:
        return sorted(self._versions)

    def get(self, minister_id: str, version: Optional[int] = None) -> MinisterSpec:
        vers = self._versions.get(minister_id)
        if not vers:
            raise KeyError(f"minister '{minister_id}' not registered")
        v = version if version is not None else self._pinned[minister_id]
        if v not in vers:
            raise KeyError(f"minister '{minister_id}' has no version {v}")
        return vers[v]

    def pinned_version(self, minister_id: str) -> int:
        return self._pinned[minister_id]

    def versions(self, minister_id: str) -> List[int]:
        return sorted(self._versions.get(minister_id, {}))

    # ---- 运维 ---------------------------------------------------------------
    def pin(self, minister_id: str, version: int) -> None:
        """线上切换版本；回滚 = pin 回旧版本号（文件一直在库里）。"""
        if version not in self._versions.get(minister_id, {}):
            raise KeyError(f"no version {version} for '{minister_id}'")
        self._pinned[minister_id] = version

    def rollback(self, minister_id: str, version: int) -> None:
        self.pin(minister_id, version)

    def register_file(self, path: str) -> MinisterSpec:
        """FR-E10：DLC 热注册一个提示词文件（可放 _pending 目录再转正）。"""
        spec = self._load_file(path)
        if spec is None:
            raise ValueError(f"cannot register {path}")
        self._versions.setdefault(spec.id, {})[spec.version] = spec
        self._pinned[spec.id] = max(self._versions[spec.id])
        return spec
