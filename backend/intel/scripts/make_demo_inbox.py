#!/usr/bin/env python3
""">>> 用法: python scripts/make_demo_inbox.py — 生成 inbox/ 人工导入样例 (§8 降级演示)。

接口下线/未开通时, 运营从知乎 Web 端复制检索结果存成此格式投进 inbox/,
POST /intel/import 即走完整管线 (去重/结构化/待审)。
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import zhihu_api

SAMPLE = {
    "Query": "孩子 问倒 家长",
    "Items": [
        {"Title": "孩子问为什么先看到闪电后听到雷声？我该怎么解释",
         "ContentType": "Question", "ContentID": "demo_q1",
         "ContentText": "四岁娃每次打雷都问, 光和声音到底是什么关系?",
         "Url": "https://www.zhihu.com/question/demo_q1",
         "CommentCount": 42, "VoteUpCount": 380, "AuthorityLevel": "2",
         "EditTime": 1757000000},
        {"Title": "孩子问为什么冰箱会制冷",
         "ContentType": "Question", "ContentID": "demo_q2",
         "ContentText": "家里冰箱嗡嗡响, 娃问它是怎么变冷的",
         "Url": "https://www.zhihu.com/question/demo_q2",
         "CommentCount": 15, "VoteUpCount": 96, "AuthorityLevel": "1",
         "EditTime": 1757000100},
        {"Title": "孩子问人死了去哪里", "ContentType": "Question", "ContentID": "demo_q3",
         "ContentText": "敏感话题样例, 应被过滤清单拦下",
         "Url": "https://www.zhihu.com/question/demo_q3",
         "CommentCount": 9, "VoteUpCount": 60, "AuthorityLevel": "1",
         "EditTime": 1757000200},
    ],
}

if __name__ == "__main__":
    import config
    config.ensure_dirs()
    inbox = config.ROOT / "inbox"
    inbox.mkdir(exist_ok=True)
    p = inbox / "demo_孩子问倒家长.json"
    p.write_text(json.dumps(SAMPLE, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"样例已写入 {p}")
    print("下一步: ZHIHU_PROVIDER=manual 后 POST /intel/import (或 python -m … server)")
