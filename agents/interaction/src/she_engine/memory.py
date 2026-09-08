"""记忆存储适配器 —— PRD §6 依赖之一（真实实现在 04 模块，本模块只定形状）。

引擎只通过本协议读写：最近 10 轮工作记忆 / 今日已学词 / 剧本状态。
提供两个参考实现：
- :class:`InMemoryStore` —— 测试用；
- :class:`FileMemoryStore` —— JSONL + JSON 快照落盘，演示「关机重开接续剧情」。
"""

from __future__ import annotations

import datetime as _dt
import json
import os
import threading
from typing import Any, Dict, List, Optional, Protocol

from .types import MemoryWrite


class MemoryStore(Protocol):
    def append_turn(self, speaker: str, text: str) -> None: ...

    def recent_turns(self, n: int = 10) -> List[Dict[str, str]]: ...

    def add_learned_word(self, word: str) -> None: ...

    def learned_words_today(self) -> List[str]: ...

    def save_script_state(self, state: Dict[str, Any]) -> None: ...

    def load_script_state(self) -> Optional[Dict[str, Any]]: ...

    def write_memory(self, items: List[MemoryWrite]) -> None:
        """FR-E06 的 memory_write 统一入口（learned_word 之外的类型也落在这）。"""


def _today() -> str:
    return _dt.date.today().isoformat()


class InMemoryStore:
    """线程安全的内存实现（参考实现 + 单测）。"""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._turns: List[Dict[str, str]] = []
        self._words: Dict[str, List[str]] = {}
        self._state: Optional[Dict[str, Any]] = None
        self._notes: List[Dict[str, str]] = []

    def append_turn(self, speaker: str, text: str) -> None:
        with self._lock:
            self._turns.append({"speaker": speaker, "text": text, "date": _today()})

    def recent_turns(self, n: int = 10) -> List[Dict[str, str]]:
        with self._lock:
            return [dict(t) for t in self._turns[-n:]]

    def add_learned_word(self, word: str) -> None:
        word = (word or "").strip()
        if not word:
            return
        with self._lock:
            self._words.setdefault(_today(), [])
            if word not in self._words[_today()]:
                self._words[_today()].append(word)

    def learned_words_today(self) -> List[str]:
        with self._lock:
            return list(self._words.get(_today(), []))

    def save_script_state(self, state: Dict[str, Any]) -> None:
        with self._lock:
            self._state = dict(state)

    def load_script_state(self) -> Optional[Dict[str, Any]]:
        with self._lock:
            return dict(self._state) if self._state else None

    def write_memory(self, items: List[MemoryWrite]) -> None:
        with self._lock:
            for w in items:
                if w.type == "learned_word":
                    # Daily context may show an observed word, but this is not a
                    # mastery promotion. Promotion belongs to Assessment/shared state.
                    self.add_learned_word(w.value)
                    self._notes.append({
                        "date": _today(), **w.to_dict(),
                        "evidence_status": w.evidence_status,
                    })
                else:
                    self._notes.append({
                        "date": _today(), **w.to_dict(),
                        "evidence_status": w.evidence_status,
                    })

    # 测试辅助
    @property
    def notes(self) -> List[Dict[str, str]]:
        return list(self._notes)


class FileMemoryStore(InMemoryStore):
    """JSONL/JSON 落盘实现：data 目录里 child.jsonl（对话）+ state.json（剧本）。

    重启 → Engine 构造时 load_script_state() 拿回「昨天讲到哪」（FR-E03 验收）。
    """

    def __init__(self, data_dir: str) -> None:
        super().__init__()
        os.makedirs(data_dir, exist_ok=True)
        self._turns_path = os.path.join(data_dir, "turns.jsonl")
        self._state_path = os.path.join(data_dir, "script_state.json")
        self._words_path = os.path.join(data_dir, "learned_words.json")
        self._load()

    def _load(self) -> None:
        if os.path.isfile(self._turns_path):
            with open(self._turns_path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            self._turns.append(json.loads(line))
                        except json.JSONDecodeError:
                            continue
        if os.path.isfile(self._state_path):
            try:
                with open(self._state_path, encoding="utf-8") as f:
                    self._state = json.load(f)
            except (OSError, json.JSONDecodeError):
                self._state = None
        if os.path.isfile(self._words_path):
            try:
                with open(self._words_path, encoding="utf-8") as f:
                    self._words = {k: list(v) for k, v in json.load(f).items()}
            except (OSError, json.JSONDecodeError, ValueError):
                self._words = {}

    def append_turn(self, speaker: str, text: str) -> None:
        super().append_turn(speaker, text)
        with self._lock:
            with open(self._turns_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(self._turns[-1], ensure_ascii=False) + "\n")

    def save_script_state(self, state: Dict[str, Any]) -> None:
        super().save_script_state(state)
        with self._lock:
            with open(self._state_path, "w", encoding="utf-8") as f:
                json.dump(state, f, ensure_ascii=False, indent=1)

    def add_learned_word(self, word: str) -> None:
        super().add_learned_word(word)
        with self._lock:
            with open(self._words_path, "w", encoding="utf-8") as f:
                json.dump(self._words, f, ensure_ascii=False, indent=1)
