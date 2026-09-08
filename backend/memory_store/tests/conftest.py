"""conftest.py — 测试夹具: 临时数据目录的 MemoryService + KG 热更新桩服务。"""
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

import pytest

from memstore import Config, MemoryService


@pytest.fixture()
def cfg(tmp_path):
    return Config(data_dir=tmp_path / "data", auto_jobs=False, port=0)


@pytest.fixture()
def svc(cfg):
    s = MemoryService(cfg)
    yield s
    s.close()


class KGStub:
    """KG 热更新桩: 记录调用, 版本单调递增, 可注入冲突/宕机。"""

    def __init__(self):
        self.calls = []
        self.version = 1
        self.conflicts_to_return = []
        self.down = False
        self.server = None
        self.port = None

    def start(self):
        stub = self

        class Handler(BaseHTTPRequestHandler):
            def _reply(self, obj, code=200):
                data = json.dumps(obj).encode()
                self.send_response(code)
                self.send_header("content-type", "application/json")
                self.send_header("content-length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def do_POST(self):
                length = int(self.headers.get("content-length", 0))
                payload = json.loads(self.rfile.read(length) or b"{}")
                path = urlparse(self.path).path
                if stub.down:
                    stub.calls.append({"path": path, "payload": payload,
                                       "error": "down"})
                    self.send_error(503)
                    return
                stub.calls.append({"path": path, "payload": payload})
                if path == "/kg/runtime-consolidate":
                    memories = payload.get("memories", [])
                    threshold = int(payload.get("threshold", 3))
                    from collections import Counter
                    co = Counter()
                    for m in memories:
                        words = sorted({str(w).lower() for w in m.get("words", [])})
                        for i in range(len(words)):
                            for j in range(i + 1, len(words)):
                                co[(words[i], words[j])] += 1
                    promoted = sum(1 for n in co.values() if n >= threshold)
                    stub.version += 1
                    self._reply({"promoted": promoted, "version": stub.version,
                                 "conflicts": stub.conflicts_to_return})
                elif path == "/kg/edges:batch":
                    applied = len([e for e in payload.get("edges", [])
                                   if e.get("op", "add") == "add"])
                    stub.version += 1
                    self._reply({"applied": applied, "version": stub.version,
                                 "conflicts": stub.conflicts_to_return})
                elif path.startswith("/kg/conflicts/") and path.endswith("/resolve"):
                    self._reply({"resolved": path.split("/")[3], "action":
                                 payload.get("action")})
                else:
                    self._reply({"error": "unknown"}, 404)

            def log_message(self, *a):  # 静默
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.port = self.server.server_address[1]
        t = threading.Thread(target=self.server.serve_forever, daemon=True)
        t.start()
        return self

    @property
    def url(self):
        return f"http://127.0.0.1:{self.port}"

    def stop(self):
        if self.server:
            self.server.shutdown()
            self.server = None


@pytest.fixture()
def kg():
    stub = KGStub().start()
    yield stub
    stub.stop()


def make_svc(tmp_path, kg_url=None, name="data", **cfg_kw):
    cfg = Config(data_dir=tmp_path / name, auto_jobs=False, port=0, **cfg_kw)
    if kg_url:
        cfg.kg_url = kg_url
    return MemoryService(cfg)
