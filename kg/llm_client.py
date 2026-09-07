#!/usr/bin/env python3
"""llm_client.py — LLM 层客户端 (OpenAI 兼容接口), 用于:

  1. build_kg.py --llm-clean  批量审边, 只输出"要删的行" (提示词冻结版见 prompts/edge_review_v1.md)
  2. server.py /kg/retrieve   FAISS→PPR 之后的 LLM 重排

环境变量:
  OPENAI_API_KEY / KG_LLM_API_KEY   API 密钥 (缺省时功能优雅降级: 跳过并告警)
  OPENAI_BASE_URL                   默认 https://api.openai.com/v1
  KG_LLM_MODEL                      默认 gpt-4o-mini
"""
import json
import os
import re
import threading
import time
from pathlib import Path

PROMPT_PATH = Path(__file__).resolve().parent / "prompts" / "edge_review_v1.md"
PROMPT_VERSION = "edge_review_v1"

VALID_REASONS = {"false_fact", "brand_sense", "adult_content", "wrong_relation",
                 "uninformative", "reversed"}

# 限流节流: 免费档 RPM 很低, 请求起始时刻全局按最小间隔排队(比 429 退避风暴更高效)
_MIN_CALL_INTERVAL = float(os.environ.get("KG_LLM_MIN_INTERVAL", "10.5"))
_throttle_lock = threading.Lock()
_last_call_start = [0.0]


class LLMUnavailable(Exception):
    pass


def _cfg():
    key = os.environ.get("KG_LLM_API_KEY") or os.environ.get("OPENAI_API_KEY")
    base = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    model = os.environ.get("KG_LLM_MODEL", "gpt-4o-mini")
    return key, base, model


def available() -> bool:
    return bool(_cfg()[0])


def model() -> str:
    return _cfg()[2]


def _chat(messages, temperature=0.0, retries=5):
    key, base, model = _cfg()
    if not key:
        raise LLMUnavailable("未配置 OPENAI_API_KEY/KG_LLM_API_KEY, LLM 层跳过")
    import requests
    last = None
    for i in range(retries + 1):
        try:
            with _throttle_lock:  # 全局节奏化: 请求起始间隔 ≥ MIN_CALL_INTERVAL
                wait = _MIN_CALL_INTERVAL - (time.time() - _last_call_start[0])
                if wait > 0:
                    time.sleep(wait)
                _last_call_start[0] = time.time()
            r = requests.post(f"{base}/chat/completions", timeout=float(os.environ.get("KG_LLM_TIMEOUT", "120")), headers={
                "Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json={"model": model, "temperature": temperature, "max_tokens": 16000,
                      "messages": messages})
            if r.status_code == 429:  # 限流: 指数退避后重试
                last = f"429 Too Many Requests"
                time.sleep(min(60, 8 * (i + 1)))
                continue
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"]
        except requests.HTTPError as e:
            last = e
            if e.response is not None and e.response.status_code < 500:
                raise LLMUnavailable(f"LLM 调用失败: {e}") from e
            time.sleep(3 * (i + 1))
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(3 * (i + 1))
    raise LLMUnavailable(f"LLM 调用失败: {last}")


def _load_prompt() -> str:
    text = PROMPT_PATH.read_text(encoding="utf-8")
    # 取正文(去掉说明头与分隔线后的最后一段为提示词本体)
    body = text.split("---", 1)[-1]
    return body.strip()


def _parse_json_list(text: str) -> list:
    """解析审边输出。兼容紧凑二元组 [[idx, reason], ...] 与 {"idx", "reason"} 两种形式。"""
    text = text.strip()
    m = re.search(r"\[.*\]", text, re.S)
    if not m:
        return []
    try:
        data = json.loads(m.group(0))
    except json.JSONDecodeError:
        return []
    out = []
    for item in data if isinstance(data, list) else []:
        if isinstance(item, (list, tuple)) and len(item) >= 2:
            idx, reason = item[0], item[1]
        elif isinstance(item, dict) and "idx" in item:
            idx, reason = item.get("idx"), item.get("reason", "uninformative")
        else:
            continue
        if reason not in VALID_REASONS:
            reason = "uninformative"
        out.append({"idx": int(idx), "reason": reason})
    return out


def review_edges(edges: list, batch_note: str = "") -> list:
    """批量审边: 返回要删除的 [{idx, reason}]。edges: [{head,rel,tail}, ...]"""
    lines = "\n".join(f'{i}. {e["head"]} | {e["rel"]} | {e["tail"]}'
                      for i, e in enumerate(edges))
    user = (f"待审边 {len(edges)} 条{batch_note}:\n{lines}\n"
            f"按提示词契约只输出紧凑 JSON 数组(二元组)。")
    raw = _chat([{"role": "system", "content": _load_prompt()},
                 {"role": "user", "content": user}])
    return _parse_json_list(raw)


def rerank(query: str, candidates: list, top_k: int = 8) -> list:
    """/kg/retrieve 的 LLM 重排: candidates=[{word, score, edges:[str]}...]
    返回按儿童学习相关性重排的 word 列表(截断 top_k)。失败/不可用时返回原序。
    """
    if not available():
        return [c["word"] for c in candidates][:top_k]
    lines = "\n".join(
        f"{i}. {c['word']} (向量分 {c.get('score', 0):.3f})"
        + (f" — 依据: {'; '.join(c.get('edges', [])[:3])}" if c.get("edges") else "")
        for i, c in enumerate(candidates[:30]))
    user = (f"查询词: {query}\n候选词:\n{lines}\n\n"
            f"为 5-12 岁儿童选 {top_k} 个与「{query}」最相关、最值得先学的词, "
            f"优先具体名词/动作/感官属性, 避免抽象词。只输出 JSON: "
            f'[{{"word": "...", "why": "..."}}] 且按从优到劣排序。')
    try:
        raw = _chat([{"role": "system",
                      "content": "你是儿童英语教研专家, 只输出 JSON。"},
                     {"role": "user", "content": user}])
        m = re.search(r"\[.*\]", raw, re.S)
        data = json.loads(m.group(0)) if m else []
        words = [d.get("word") for d in data if isinstance(d, dict) and d.get("word")]
        known = {c["word"] for c in candidates}
        words = [w for w in words if w in known]
        # LLM 可能漏掉一些候选, 补回保持完整性
        for c in candidates:
            if c["word"] not in words:
                words.append(c["word"])
        return words[:top_k]
    except Exception:  # noqa: BLE001 — 重排是增强项, 失败退回原序
        return [c["word"] for c in candidates][:top_k]
