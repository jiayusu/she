"""埋点（PRD §8）：engine_routed / engine_recast / engine_fallback / engine_latency。

加一条 engine_stuck 支撑 FR-E09「卡壳检测→降级的链路可观测」，
加 engine_cost_warn 支撑「模板占比 >30% 时报警」同类成本护栏。
Sink 可插拔：默认内存收集（测试/演示），线上接报表系统。
"""

from __future__ import annotations

import time
from collections import Counter
from typing import Any, Callable, Dict, List, Optional, Protocol


class EventSink(Protocol):
    def emit(self, name: str, payload: Dict[str, Any]) -> None: ...


class InMemorySink:
    """把事件收进内存列表，测试可直接断言；``count()`` 给监控面板用。"""

    def __init__(self) -> None:
        self.events: List[Dict[str, Any]] = []

    def emit(self, name: str, payload: Dict[str, Any]) -> None:
        self.events.append({"name": name, "ts": time.time(), **payload})

    def of(self, name: str) -> List[Dict[str, Any]]:
        return [e for e in self.events if e["name"] == name]

    def count(self, name: str) -> int:
        return len(self.of(name))

    def counter(self, name: str, key: str) -> Counter:
        return Counter(str(e.get(key)) for e in self.of(name))


def CallbackSink(fn: Callable[[str, Dict[str, Any]], None]) -> EventSink:  # noqa: N802
    """一行接线上埋点管道，例如 ``CallbackSink(lambda n,p: statsd.incr(n, **p))``。"""

    class _Cb:
        def emit(self, name: str, payload: Dict[str, Any]) -> None:
            fn(name, payload)

    return _Cb()


class EventBus:
    """引擎内唯一的事件出口；sink 挂了也不许影响主链路（埋点静默降级）。"""

    def __init__(self, sink: Optional[EventSink] = None) -> None:
        self._sink = sink if sink is not None else InMemorySink()

    @property
    def sink(self) -> EventSink:
        return self._sink

    def emit(self, name: str, **payload: Any) -> None:
        try:
            self._sink.emit(name, payload)
        except Exception:  # noqa: BLE001 —— 埋点永不打断剧情
            pass

    # ---- PRD §8 语义化封装 -------------------------------------------------
    def routed(self, intent: str, minister: str, confidence: float = 1.0) -> None:
        self.emit("engine_routed", intent=intent, minister=minister, confidence=round(confidence, 3))

    def recast(self, assess_used: bool, error_type: str = "") -> None:
        self.emit("engine_recast", assess_used=assess_used, error_type=error_type)

    def fallback(self, template_hit: bool, minister: str = "", scene: str = "") -> None:
        self.emit("engine_fallback", template_hit=template_hit, minister=minister, scene=scene)

    def latency(self, ttft: float, total: float) -> None:
        self.emit("engine_latency", ttft=round(ttft, 1), total=round(total, 1))

    def stuck(self, streak: int, level: int, downgraded: bool) -> None:
        self.emit("engine_stuck", streak=streak, level=level, downgraded=downgraded)

    def cost_warn(self, session_yuan: float) -> None:
        self.emit("engine_cost_warn", session_yuan=round(session_yuan, 4))
