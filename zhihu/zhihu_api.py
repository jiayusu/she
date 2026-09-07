#!/usr/bin/env python3
"""zhihu_api.py — 知乎开放平台 Provider 层 (§8 风险对策: 可切换降级)。

  ZhihuProvider  官方 REST: Bearer + X-Request-Timestamp (秒级), 全部服务端调用
  ManualProvider 人工导入降级: 把导出的 JSON 放 inbox/ (接口下线/未开通时照常运转)

统一出口 normalize 后的 item:
  {title, content_type, content_id, text, url, comment_count, vote_up,
   authority, edit_time, author, comments}

额度查询 /api/v1/quota 不消耗业务额度, 用于平台侧余额核对。
"""
import hashlib
import json
import shutil
import time
from pathlib import Path

import requests

import config

ROOT = Path(__file__).resolve().parent
INBOX = ROOT / "inbox"


class ZhihuAPIError(Exception):
    def __init__(self, code, message, endpoint=""):
        super().__init__(f"zhihu api {endpoint} code={code}: {message}")
        self.code = code
        self.message = message
        self.endpoint = endpoint


def _headers():
    return {"Authorization": f"Bearer {config.ZHIHU_API}",
            "X-Request-Timestamp": str(int(time.time())),
            "Content-Type": "application/json"}


def _get(endpoint, params, retries=2):
    """GET {API_BASE}/{endpoint}; Code!=0 抛 ZhihuAPIError; 30001 限频退避重试。"""
    url = f"{config.API_BASE}/{endpoint}"
    last = None
    for i in range(retries + 1):
        try:
            r = requests.get(url, params=params, headers=_headers(),
                             timeout=config.ZHIHU_TIMEOUT)
            r.raise_for_status()
            body = r.json()
        except requests.RequestException as e:
            last = ZhihuAPIError(-1, f"http_error:{e}", endpoint)
            if i < retries:
                time.sleep(2 * (i + 1))
                continue
            raise last
        code = body.get("Code", -1)
        if code == 0:
            return body.get("Data") or {}
        if code == 30001 and i < retries:  # 频率限制: 退避重试
            time.sleep(5 * (i + 1))
            continue
        raise ZhihuAPIError(code, body.get("Message", "unknown"), endpoint)
    raise last


def _norm(item):
    """API item → 统一结构。"""
    return {"title": (item.get("Title") or "").strip(),
            "content_type": item.get("ContentType", ""),
            "content_id": str(item.get("ContentID", "")),
            "text": item.get("ContentText", "") or "",
            "url": item.get("Url", ""),
            "comment_count": int(item.get("CommentCount") or 0),
            "vote_up": int(item.get("VoteUpCount") or 0),
            "authority": str(item.get("AuthorityLevel") or ""),
            "edit_time": int(item.get("EditTime") or 0),
            "author": item.get("AuthorName", ""),
            "comments": [c.get("Content", "") for c in (item.get("CommentInfoList") or [])]}


# ---------------------------------------------------------------- 官方 Provider
class ZhihuProvider:
    name = "zhihu_api"

    def search(self, query, count=10):
        """zhihu_search: 知乎站内搜索 (Count≤10, 超出服务端截断)。"""
        data = _get("content/zhihu_search", {"Query": query, "Count": min(count, 10)})
        return [_norm(i) for i in (data.get("Items") or [])]

    def global_search(self, query, count=10, search_db="all"):
        data = _get("content/global_search",
                    {"Query": query, "Count": min(count, 20), "SearchDB": search_db})
        return [_norm(i) for i in (data.get("Items") or [])]

    def hot_list(self, limit=30):
        data = _get("content/hot_list", {"Limit": min(limit, 30)})
        return [{"title": (i.get("Title") or "").strip(), "url": i.get("Url", ""),
                 "summary": i.get("Summary", "")}
                for i in (data.get("Items") or [])]

    def quota(self, api_ids=None):
        """平台侧额度 (不消耗业务额度)。api_ids: zhihu_search,hot_list,global_search"""
        params = {"APIIDs": api_ids} if api_ids else {}
        rows = _get("quota", params)
        if isinstance(rows, dict):  # 兼容 Data 再包一层的情况
            rows = rows.get("Data") or []
        return {r["APIID"]: {"total": r["TotalQuota"], "used": r["TotalUsed"],
                             "remaining": r["RemainingQuota"]} for r in rows}


# ---------------------------------------------------------------- 人工导入 Provider
class ManualProvider:
    """降级模式 (§8): 运营把手工导出的 JSON 投进 inbox/ 后运行 import。

    文件格式 (与官方响应 Data 同构, 一文件一查询):
      {"Query": "孩子 问倒 家长", "Items": [ {Title/ContentType/...}, ... ]}
    hot_list 导出可放 inbox/hotlist.json: {"Items": [...]}。
    导入成功的文件移入 inbox/imported/ 留痕。
    """
    name = "manual"

    def __init__(self):
        INBOX.mkdir(exist_ok=True)
        (INBOX / "imported").mkdir(exist_ok=True)

    def _load(self):
        items_by_query, hot = {}, []
        for p in sorted(INBOX.glob("*.json")):
            try:
                body = json.loads(p.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue  # 坏文件留在 inbox, 由 /intel/import 报告
            if p.name == "hotlist.json" or "hot" in p.stem:
                hot.extend(body.get("Items") or [])
            else:
                q = body.get("Query") or p.stem
                items_by_query.setdefault(q, []).extend(body.get("Items") or [])
            shutil.move(str(p), str(INBOX / "imported" / p.name))
        return items_by_query, hot

    def search(self, query, count=10):
        items, _ = self._load()
        return [_norm(i) for i in items.get(query, [])][:count]

    def hot_list(self, limit=30):
        _, hot = self._load()
        return [{"title": (i.get("Title") or "").strip(), "url": i.get("Url", ""),
                 "summary": i.get("Summary", "")} for i in hot[:limit]]

    def quota(self, api_ids=None):
        return {}


def provider():
    """Provider 工厂。未配置密钥时自动降级为 manual (§8)。"""
    if config.ZHIHU_PROVIDER == "manual" or not config.ZHIHU_API:
        return ManualProvider()
    return ZhihuProvider()
