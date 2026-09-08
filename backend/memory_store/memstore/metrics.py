"""metrics.py — §8 埋点: ep_write / recall_hit(k, latency) / prune_count /
consolidate_edges / snapshot_ok, 附关键延迟分位。GET /memory/metrics 快照。"""
import threading
import time
from collections import deque


def quantile(xs, q):
    if not xs:
        return 0.0
    xs = sorted(xs)
    idx = min(len(xs) - 1, max(0, int(round(q * (len(xs) - 1)))))
    return round(xs[idx], 2)


class Metrics:
    def __init__(self, window: int = 2000):
        self._lock = threading.Lock()
        self.counters: dict[str, int] = {}
        self._lat: dict[str, deque] = {}
        self._window = window
        self.started = time.time()

    def incr(self, name: str, n: int = 1):
        with self._lock:
            self.counters[name] = self.counters.get(name, 0) + n

    def observe(self, name: str, ms: float):
        with self._lock:
            dq = self._lat.setdefault(name, deque(maxlen=self._window))
            dq.append(float(ms))

    def ep_write(self, ms: float, ok: bool = True):
        self.incr("ep_write" if ok else "ep_write_fail")
        if ok:
            self.observe("ep_write_ms", ms)

    def recall_hit(self, k: int, ms: float, hits: int):
        self.incr("recall_hit", hits)
        self.incr("recall_total")
        self.observe("recall_ms", ms)
        self.observe("recall_k", k)

    def prune(self, n: int = 1):
        self.incr("prune_count", n)

    def consolidate_edges(self, n: int = 1):
        self.incr("consolidate_edges", n)

    def snapshot_ok(self, ok: bool, ms: float = 0.0):
        self.incr("snapshot_ok" if ok else "snapshot_fail")
        if ok:
            self.observe("snapshot_ms", ms)

    def snapshot(self) -> dict:
        with self._lock:
            out = {
                "uptime_s": round(time.time() - self.started, 1),
                "counters": dict(self.counters),
                "latency_ms": {name: {"p50": quantile(dq, 0.5), "p95": quantile(dq, 0.95),
                                      "n": len(dq)}
                               for name, dq in self._lat.items()},
            }
        return out
