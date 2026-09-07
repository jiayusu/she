"""§7 架构纪律红线 (评审红线) 守卫测试。

1. zhihu_search 不得注册为小智/Agent 的任何 MCP 工具 → 全仓不出现 MCP 服务端注册。
2. 知乎原文不直接进任何面向孩子的输出 → KG 推送载荷只含英文知识三元组。
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

MCP_PATTERNS = [
    r"FastMCP\(", r"@mcp\.tool", r"@server\.list_tools", r"mcp\.server",
    r"MCPServer", r"stdio_server",
]


def test_no_mcp_tool_registration_anywhere():
    """红线 1: 本仓任何源码不得注册 MCP 工具 (孩子对话不实时联网)。"""
    offenders = []
    for py in ROOT.rglob("*.py"):
        if ".tmp" in py.parts or "__pycache__" in py.parts:
            continue
        if py.name == "test_guard.py":  # 守卫测试自身包含模式串, 跳过自匹配
            continue
        text = py.read_text(encoding="utf-8", errors="ignore")
        for pat in MCP_PATTERNS:
            if re.search(pat, text):
                offenders.append(f"{py.name}: {pat}")
    assert not offenders, f"检测到 MCP 服务端注册, 违反 §7 红线: {offenders}"


def test_kg_payload_contains_only_english_edges(env):
    """红线 2: 入 KG 的只有结构化三元组, 知乎原文/中文长句不出现在 KG 载荷。"""
    import config
    from kg_bridge import _kg_payload
    row = {"id": 42,
           "kg_edges": json_dumps([{"head": "sky", "rel": "HasProperty",
                                    "tail": "blue", "weight": 2.0}])}
    payload = _kg_payload(row)
    assert payload["source"] == "zhihu_intel:42"
    assert all(re.fullmatch(r"[a-z_]+", e["head"]) and re.fullmatch(r"[a-z_]+", e["tail"])
               for e in payload["edges"])
    assert all(e["rel"] in config.KG_EDGE_RELS for e in payload["edges"])


def json_dumps(x):
    import json
    return json.dumps(x)
