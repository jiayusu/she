"""端到端: 服务接口 → 管线 → 审核硬闸门 → KG 推送 → 舆情 → 周报 → 存档 → 埋点。"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def client():
    import server
    server.app.config["TESTING"] = True
    return server.app.test_client()


def test_health_self_declares_no_mcp(env):
    r = client().get("/intel/health")
    assert r.status_code == 200
    h = r.get_json()
    assert h["mcp_exposed"] is False            # §7 红线自证
    assert h["provider"] in ("zhihu_api", "manual")


def test_full_question_pool_flow(env, fake_provider, fake_llm, fake_kg):
    c = client()
    # 1) 采集+结构化
    r = c.post("/intel/pipeline/run")
    assert r.status_code == 200
    body = r.get_json()
    assert body["fetch"]["inserted"] >= 3
    assert body["structure"]["ok"] >= 2

    # 2) 工作台数据源
    pool = c.get("/intel/question-pool").get_json()
    ids = {i["id"]: i for i in pool["items"]}
    q100 = next(i for i in pool["items"] if i["content_id"] == "q100")
    assert q100["status"] == "structured"
    assert "ContentText" not in json.dumps(pool)  # 合规: 不下发原文全文字段

    # 3) 未结构化不得入 KG: approve 一个 pending_struct 的条目应被拒
    pending = [i for i in pool["items"] if i["status"] == "pending_struct"]
    if pending:
        r = c.post(f"/intel/question-pool/{pending[0]['id']}/approve",
                   json={"reviewer": "甲"})
        assert r.status_code == 400

    # 4) 修改留痕 + 通过 → KG
    edits = {"fact": "天空的蓝色来自阳光被空气散射，蓝光波长短散射最强。",
             "kg_edges": [{"head": "sky", "rel": "HasProperty", "tail": "blue",
                           "weight": 1.5}]}
    r = c.post(f"/intel/question-pool/{q100['id']}/approve",
               json={"reviewer": "甲", "edits": edits})
    assert r.status_code == 200 and r.get_json()["ok"]
    assert fake_kg.last_body["source"].endswith(f"zhihu_intel:{q100['id']}")
    assert fake_kg.last_body["edges"][0]["head"] == "sky"

    detail = c.get(f"/intel/question-pool/{q100['id']}").get_json()
    actions = [l["action"] for l in detail["review_log"]]
    assert "modify" in actions and "approve" in actions and "kg_push" in actions
    mod = next(l for l in detail["review_log"] if l["action"] == "modify")
    assert "天空呈现蓝色" in mod["before_json"] and "散射" in mod["after_json"]
    assert detail["status"] == "kg_pushed"

    # 5) 敏感条目硬闸门 (含敏感过滤条目拉取后仍不可通过)
    pool_all = c.get("/intel/question-pool?include_filtered=1").get_json()
    q103 = next((i for i in pool_all["items"] if i["content_id"] == "q103"), None)
    assert q103 and q103["status"] == "filtered"
    r = c.post(f"/intel/question-pool/{q103['id']}/approve", json={"reviewer": "甲"})
    assert r.status_code == 400 and "filtered" in r.get_json()["error"]

    # 6) 丢弃
    q101 = next(i for i in pool["items"] if i["content_id"] == "q101")
    r = c.post(f"/intel/question-pool/{q101['id']}/discard",
               json={"reviewer": "乙", "note": "超纲"})
    assert r.status_code == 200


def test_sentiment_negative_push_and_listing(env, fake_provider, fake_llm):
    c = client()
    r = c.post("/intel/sentiment/poll", json={})
    assert r.status_code == 200
    out = r.get_json()
    assert out["fresh"] == 2                    # s300 负面 + s301 中性
    assert out["negative"] == 1 and out["pushed"] == 1
    lst = c.get("/intel/sentiment?sentiment=negative").get_json()
    assert lst["count"] == 1 and lst["items"][0]["content_id"] == "s300"
    assert lst["items"][0]["issue_tag"] == "quality"
    # webhook 未配置 → 落盘 outbox (§5 不丢消息)
    import config
    assert list(config.OUTBOX_DIR.glob("*.md")), "负面告警应落盘 outbox"
    # 重复轮询: content_id 去重, 不再新增
    r = c.post("/intel/sentiment/poll", json={})
    assert r.get_json()["fresh"] == 0


def test_weekly_report_flow(env, fake_provider, fake_llm):
    c = client()
    r = c.post("/intel/weekly-report/run", json={"force": True})
    assert r.status_code == 200
    out = r.get_json()
    assert out["ok"] and out["samples"] >= 1
    latest = c.get("/intel/reports/latest").get_json()
    assert "家长语言雷达周报" in latest["markdown"]
    assert "zhihu.com/question/r200" in latest["markdown"]  # §8 附原始样本链接
    payload = json.loads(latest["payload"])
    assert len(payload["anxiety_top5"]) == 2


def test_metrics_events_schema(env, fake_provider, fake_llm):
    c = client()
    c.post("/intel/pipeline/run")
    c.post("/intel/sentiment/poll", json={})
    m = c.get("/intel/metrics").get_json()
    for ev in ("intel_fetched", "intel_structured"):
        assert ev in m["today"] and m["today"][ev] > 0
    # fake provider 不打真实平台 → 台账不记账 (FR-I07 实际调用口径)
    assert "intel_quota_used" not in m["today"]
    assert set(m["events_schema"]) == {"intel_fetched", "intel_structured",
                                       "intel_approved", "intel_report_sent",
                                       "intel_quota_used"}


def test_archive_search_and_raw_tracing(env, fake_provider, fake_llm):
    c = client()
    c.post("/intel/pipeline/run")
    r = c.get("/intel/archive?q=天空").get_json()
    assert r["count"] >= 1
    raw_path = c.get("/intel/question-pool").get_json()["items"][0]["raw_path"]
    r = c.get("/intel/archive/raw", query_string={"path": raw_path})
    assert r.status_code == 200 and "items" in r.get_json()["data"]
    r = c.get("/intel/archive/raw", query_string={"path": "../.env"})
    assert r.status_code == 404                  # 目录穿越防护


def test_token_guard(env, fake_provider, monkeypatch):
    import server
    monkeypatch.setattr(server.config, "INTEL_TOKEN", "s3cret")
    c = server.app.test_client()
    assert c.post("/intel/pipeline/run", json={}).status_code == 403
    r = c.post("/intel/pipeline/run", json={}, headers={"X-Intel-Token": "s3cret"})
    assert r.status_code == 200
