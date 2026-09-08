#!/usr/bin/env python3
"""llm_client.py — LLM 客户端 (OpenAI 兼容), 供结构化/舆情分类/雷达聚类使用。

对齐 kb/llm_client.py 的工程约定:
  - 全局限速节流 (免费档 RPM 低, 请求起始间隔排队)
  - 429 指数退避
  - LLMUnavailable: 未配 key 或不可用时调用方优雅降级 (条目挂起重试, 不阻塞管线)
"""
import json
import re
import threading
import time

import config

_throttle_lock = threading.Lock()
_last_call_start = [0.0]


class LLMUnavailable(Exception):
    pass


def available():
    return bool(config.LLM_API_KEY)


def _chat(messages, temperature=0.0, max_tokens=8000, retries=4, timeout=180):
    if not config.LLM_API_KEY:
        raise LLMUnavailable("未配置 LLM_API_KEY/OPENAI_API_KEY, LLM 层跳过")
    import requests
    last = None
    for i in range(retries + 1):
        try:
            with _throttle_lock:
                wait = config.LLM_MIN_INTERVAL - (time.time() - _last_call_start[0])
                if wait > 0:
                    time.sleep(wait)
                _last_call_start[0] = time.time()
            r = requests.post(f"{config.OPENAI_BASE_URL}/chat/completions", timeout=timeout,
                              headers={"Authorization": f"Bearer {config.LLM_API_KEY}",
                                       "Content-Type": "application/json"},
                              json={"model": config.LLM_MODEL, "temperature": temperature,
                                    "max_tokens": max_tokens, "messages": messages})
            if r.status_code == 429:
                last = LLMUnavailable("429 Too Many Requests")
                time.sleep(min(60, 8 * (i + 1)))
                continue
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"]
        except requests.HTTPError as e:
            last = LLMUnavailable(f"LLM 调用失败: {e}")
            if e.response is not None and e.response.status_code < 500:
                raise last
            time.sleep(3 * (i + 1))
        except LLMUnavailable:
            raise
        except Exception as e:  # noqa: BLE001
            last = LLMUnavailable(f"LLM 调用失败: {e}")
            time.sleep(3 * (i + 1))
    raise last


def extract_json(text, container="object"):
    """从 LLM 回复中提取 JSON (容忍代码围栏/前后缀)。container: object|array"""
    pattern = r"\{.*\}" if container == "object" else r"\[.*\]"
    m = re.search(pattern, text or "", re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return None
