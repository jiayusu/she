"""conftest — 测试环境: 临时库/归档目录, Fake Provider/LLM, KG 桩服务。"""
import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

TEST_DATA = ROOT / ".tmp" / "test_data"


@pytest.fixture()
def env(monkeypatch):
    """隔离的配置环境 (每个测试独立)。"""
    import shutil
    import time
    for _ in range(6):  # Windows: 上一个用例的 WAL 句柄释放有延迟
        try:
            if TEST_DATA.exists():
                shutil.rmtree(TEST_DATA)
            break
        except PermissionError:
            time.sleep(0.4)
    TEST_DATA.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("ZHIHU_API", "test-secret")
    monkeypatch.setenv("ZHIHU_PROVIDER", "zhihu_api")
    monkeypatch.setenv("LLM_API_KEY", "test-llm")
    monkeypatch.setenv("WECOM_WEBHOOK", "")
    monkeypatch.setenv("INTEL_DATA", str(TEST_DATA))
    monkeypatch.setenv("INTEL_DB", str(TEST_DATA / "intel.db"))
    monkeypatch.setenv("ZHIHU_DAILY_LIMIT", "1000")
    import importlib
    import config
    importlib.reload(config)
    config.OUTBOX_DIR = TEST_DATA / "outbox"   # 推送落盘也隔离到测试目录
    config.ZHIHU_TIMEOUT = 3                   # 保险丝: 漏网的真实网络调用不挂起测试
    config.ensure_dirs()
    yield config
    monkeypatch.undo()


@pytest.fixture()
def conn(env):
    import db
    c = db.connect()
    yield c
    c.close()


class FakeProvider:
    """确定性 Provider: 按查询词返回固定条目 (含重复标题与敏感词用例)。"""
    name = "fake"

    ITEMS = {
        "孩子 问倒 家长": [
            {"Title": "孩子为什么天空是蓝色的？家长被问倒了", "ContentType": "Question",
             "ContentID": "q100", "ContentText": "四岁的孩子一直问为什么天空是蓝色的，家长该怎么回答？",
             "Url": "https://www.zhihu.com/question/q100", "CommentCount": 30,
             "VoteUpCount": 500, "AuthorityLevel": "2", "EditTime": 1756000000},
            {"Title": "孩子问为什么下雨之前云会变黑怎么解释", "ContentType": "Question",
             "ContentID": "q101", "ContentText": "孩子对乌云很好奇", "Url": "https://www.zhihu.com/question/q101",
             "CommentCount": 10, "VoteUpCount": 120, "AuthorityLevel": "1", "EditTime": 1756000100},
        ],
        "儿童 十万个为什么": [
            # q102 与 q100 标题高度相似 (应被去重合并)
            {"Title": "孩子问为什么天空是蓝色的？家长被问倒了怎么办", "ContentType": "Question",
             "ContentID": "q102", "ContentText": "同款问题", "Url": "https://www.zhihu.com/question/q102",
             "CommentCount": 5, "VoteUpCount": 40, "AuthorityLevel": "1", "EditTime": 1756000200},
            {"Title": "孩子问死亡是什么，家长要怎么回答", "ContentType": "Question",
             "ContentID": "q103", "ContentText": "死亡话题", "Url": "https://www.zhihu.com/question/q103",
             "CommentCount": 8, "VoteUpCount": 66, "AuthorityLevel": "1", "EditTime": 1756000300},
        ],
        "英语启蒙 焦虑": [
            {"Title": "英语启蒙两年，孩子还是不开口，我焦虑到失眠", "ContentType": "Question",
             "ContentID": "r200", "ContentText": "磨耳朵、绘本都做了", "Url": "https://www.zhihu.com/question/r200",
             "CommentCount": 44, "VoteUpCount": 300, "AuthorityLevel": "2", "EditTime": 1756000400},
        ],
        "AI 英语玩具": [
            {"Title": "某AI英语玩具翻车了，识别全错还死机", "ContentType": "Answer",
             "ContentID": "s300", "ContentText": "亲测翻车，售后也差", "Url": "https://www.zhihu.com/answer/s300",
             "CommentCount": 12, "VoteUpCount": 90, "AuthorityLevel": "1", "EditTime": 1756000500},
            {"Title": "AI英语学习机值得买吗？", "ContentType": "Question",
             "ContentID": "s301", "ContentText": "求建议", "Url": "https://www.zhihu.com/question/s301",
             "CommentCount": 3, "VoteUpCount": 15, "AuthorityLevel": "1", "EditTime": 1756000600},
        ],
    }

    def search(self, query, count=10):
        import zhihu_api
        return [zhihu_api._norm(dict(x)) for x in self.ITEMS.get(query, [])][:count]

    def hot_list(self, limit=30):
        return [{"title": "热榜: 英语启蒙到底几岁开始", "url": "https://www.zhihu.com/hot1",
                 "summary": "讨论激烈"}][:limit]

    def quota(self, api_ids=None):
        return {}


@pytest.fixture()
def fake_provider(monkeypatch):
    import zhihu_api
    monkeypatch.setattr(zhihu_api, "provider", lambda: FakeProvider())
    return FakeProvider


class FakeLLM:
    """确定性 LLM 桩: 按系统提示词路由 (structure/sentiment/radar)。"""

    def __call__(self, messages, **kw):
        system = messages[0]["content"]
        user = messages[-1]["content"]
        if "structure_v1" in system or "结构化提炼" in system:
            return self._structure(user)
        if "舆情" in system or "sentiment" in system.lower():
            return self._sentiment(user)
        if "雷达" in system or "洞察分析师" in system:
            return self._radar()
        raise AssertionError("unknown prompt routed to FakeLLM")

    def _structure(self, user):
        import re
        out = []
        for m in re.finditer(r"\[(\d+)\] 标题: (.+)", user):
            idx, title = int(m.group(1)), m.group(2)
            out.append({
                "idx": idx, "sensitive": False, "skip_reason": "",
                "phenomenon": f"家长被「{title[:12]}」问倒",
                "child_question": title[:20],
                "fact": "天空呈现蓝色是因为空气分子对阳光中蓝光的散射更强（瑞利散射）。",
                "difficulty": 2,
                "related_objects": ["sky", "light"],
                "kg_edges": [{"head": "sky", "rel": "HasProperty", "tail": "blue"}]})
        return json.dumps(out, ensure_ascii=False)

    def _sentiment(self, user):
        items = []
        for m in __import__("re").finditer(r"\[(\d+)\] 监控命中: .+?\n标题: (.+)", user):
            idx, title = int(m.group(1)), m.group(2)
            neg = "翻车" in title or "差" in title
            items.append({"idx": idx, "sentiment": "negative" if neg else "neutral",
                          "issue_tag": "quality" if neg else "",
                          "confidence": 0.9 if neg else 0.6})
        return json.dumps({"items": items}, ensure_ascii=False)

    def _radar(self):
        return json.dumps({
            "anxiety_top5": [
                {"theme": "启蒙两年不开口", "summary": "家长普遍焦虑输入两年无输出",
                 "heat": 88, "sample_titles": ["英语启蒙两年不开口"],
                 "sample_links": ["https://www.zhihu.com/question/r200"]},
                {"theme": "几岁开始启蒙", "summary": "起步年龄之争", "heat": 70,
                 "sample_titles": [], "sample_links": []}],
            "emerging_methods": [{"word": "可理解性输入", "why": "本周讨论升温",
                                  "evidence": "磨耳朵无用论"}],
            "suggested_actions": ["选题: 输入到输出的过渡期"]}, ensure_ascii=False)


@pytest.fixture()
def fake_llm(monkeypatch):
    import llm_client
    f = FakeLLM()
    monkeypatch.setattr(llm_client, "_chat", f)
    return f


class _KGHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        n = self.rfile.read(int(self.headers["Content-Length"]))
        body = json.loads(n)
        self.server.last_body = body
        out = {"version": 7, "applied": len(body.get("edges", [])),
               "rejected": [], "skipped": [], "conflicts": [], "inc_train": {}}
        data = json.dumps(out).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *a):  # 静默
        pass


@pytest.fixture()
def fake_kg(monkeypatch):
    srv = HTTPServer(("127.0.0.1", 0), _KGHandler)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    import config
    monkeypatch.setattr(config, "KG_URL", f"http://127.0.0.1:{srv.server_port}")
    yield srv
    srv.shutdown()
