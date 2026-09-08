"""HTTP e2e: §6 接口 + 管理端点, 真实 server.py 子进程 + KG 桩。"""
import json
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from conftest import KGStub  # noqa: E402


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def http(method, url, payload=None):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    if data:
        req.add_header("content-type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


@pytest.fixture(scope="module")
def server(tmp_path_factory):
    kg = KGStub().start()
    data_dir = tmp_path_factory.mktemp("srv") / "data"
    port = free_port()
    env = {**__import__("os").environ,
           "STORE_PORT": str(port), "STORE_DATA": str(data_dir),
           "KG_URL": kg.url, "AUTO_JOBS": "0"}
    proc = subprocess.Popen([sys.executable, str(ROOT / "server.py")], env=env,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    base = f"http://127.0.0.1:{port}"
    for _ in range(50):  # 等待启动
        try:
            code, h = http("GET", f"{base}/healthz")
            if code == 200:
                break
        except Exception:
            time.sleep(0.2)
    else:
        proc.kill()
        raise RuntimeError("server.py 启动失败")
    yield base, kg
    proc.terminate()
    proc.wait(timeout=5)
    kg.stop()


def test_healthz_five_stores(server):
    base, _ = server
    code, h = http("GET", f"{base}/healthz")
    assert code == 200 and h["ok"]
    assert set(h["stores"]) == {"working", "episodic", "semantic", "salience",
                                "procedural"}


def test_six_contract_endpoints(server):
    """§6 冻结接口全链路: 写入→召回→巩固→程序性→快照/回滚。"""
    base, kg = server
    # 1. POST /memory/episodes
    code, ep = http("POST", f"{base}/memory/episodes", {
        "utterance": "I baked cookies with mom", "scene": "kitchen",
        "assess": 88, "emotion": "happy", "salience": 0.6,
        "session_id": "http-s1"})
    assert code == 201 and ep["id"] > 0 and "write_ms" in ep
    # 2. GET /memory/recall
    code, out = http("GET", f"{base}/memory/recall?query=cookies%20kitchen&k=3")
    assert code == 200 and any("cookies" in r["utterance"] for r in out["results"])
    assert "latency_ms" in out
    # 3. POST /memory/consolidate
    code, con = http("POST", f"{base}/memory/consolidate", {
        "memories": [{"scene": "kitchen", "words": ["cookie", "milk"],
                      "assess": 85}], "threshold": 1})
    assert code == 200 and con["promoted"] >= 1
    # 4. GET /memory/procedural/due
    code, _ = http("POST", f"{base}/memory/procedural", {
        "name": "朝会提醒", "trigger": {"type": "time", "time": "20:30",
                                        "repeat": "daily"},
        "action": {"type": "remind", "text": "朝会"}})
    assert code == 201
    code, due = http("GET", f"{base}/memory/procedural/due"
                            "?now=2026-09-04T20:30:00")
    assert code == 200 and due["count"] == 1
    # 5. POST /memory/snapshot + /memory/rollback/{v}
    code, snap = http("POST", f"{base}/memory/snapshot", {"note": "e2e"})
    assert code == 201 and snap["version"] > 0
    code, ep2 = http("POST", f"{base}/memory/episodes",
                     {"utterance": "after snapshot noise"})
    code, rb = http("POST", f"{base}/memory/rollback/{snap['version']}")
    assert code == 200 and rb["rolled_back_to"] == snap["version"]
    code, out = http("GET", f"{base}/memory/recall?query=after%20snapshot")
    assert not any("after snapshot" in r["utterance"] for r in out["results"])


def test_error_paths(server):
    base, _ = server
    code, e = http("POST", f"{base}/memory/episodes", {"scene": "x"})
    assert code == 400 and "utterance" in e["error"]
    code, e = http("GET", f"{base}/memory/recall")
    assert code == 400
    code, e = http("POST", f"{base}/memory/rollback/424242")
    assert code == 404


def test_admin_aux_endpoints(server):
    base, kg = server
    code, w = http("POST", f"{base}/memory/whitelist", {
        "ref_id": "mw-http-1", "reason": "家长标记", "content": "第一次自己穿衣"})
    assert code == 201
    code, wl = http("GET", f"{base}/memory/whitelist")
    assert wl["count"] >= 1
    code, met = http("GET", f"{base}/memory/metrics")
    assert code == 200 and "ep_write" in met["counters"]
    code, aud = http("GET", f"{base}/memory/audit?limit=5")
    assert code == 200 and aud["count"] <= 5
    code, jobs = http("GET", f"{base}/memory/erase/jobs")
    assert code == 200
    code, snaps = http("GET", f"{base}/memory/snapshots")
    assert code == 200 and snaps["count"] >= 1


def test_erase_endpoint(server):
    base, _ = server
    code, ep = http("POST", f"{base}/memory/episodes",
                    {"utterance": "to be erased", "child_id": "child-erase"})
    code, out = http("POST", f"{base}/memory/erase",
                     {"child_id": "child-erase", "requested_by": "parent"})
    assert code == 200 and out["status"] == "completed"
    assert Path(out["manifest"]).exists()
