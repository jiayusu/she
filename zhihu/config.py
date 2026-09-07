#!/usr/bin/env python3
"""config.py — 配置中心。全部环境变量可覆盖, 默认值对齐 PRD《06 数据情报 V1.0》。

密钥只从 .env / 环境变量读取, 不进代码库 (§5 非功能)。
"""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def _load_dotenv():
    """极简 .env 装载 (避免引入 python-dotenv 依赖); 已存在的环境变量优先。"""
    env = ROOT / ".env"
    if not env.exists():
        return
    for line in env.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        k, v = k.strip(), v.strip().strip('"').strip("'")
        if k and k not in os.environ:
            os.environ[k] = v


_load_dotenv()


def env(key, default=""):
    return os.environ.get(key, default)


def env_int(key, default):
    try:
        return int(os.environ.get(key, default))
    except (TypeError, ValueError):
        return default


def env_float(key, default):
    try:
        return float(os.environ.get(key, default))
    except (TypeError, ValueError):
        return default


# ---------------------------------------------------------------- 平台
ZHIHU_API = env("ZHIHU_API")                       # Access Secret, Bearer 用
ZHIHU_PROVIDER = env("ZHIHU_PROVIDER", "zhihu_api")  # zhihu_api | manual
API_BASE = env("ZHIHU_API_BASE", "https://developer.zhihu.com/api/v1")
ZHIHU_TIMEOUT = env_float("ZHIHU_TIMEOUT", 30)     # 单请求超时(秒)

# ---------------------------------------------------------------- FR-I07 额度治理
# 三用途共用日配额, 优先级 问题池 > 舆情 > 雷达; 超额降级为隔日补跑并告警
ZHIHU_DAILY_LIMIT = env_int("ZHIHU_DAILY_LIMIT", 1000)
PURPOSE_PRIORITY = {"question_pool": 0, "sentiment": 1, "radar": 2}  # 小者优先

# ---------------------------------------------------------------- FR-I01 问题池采集
# ≥6 个查询词, 可配置 (逗号分隔)
QUESTION_QUERIES = [q.strip() for q in env(
    "QUESTION_QUERIES",
    "孩子 问倒 家长,儿童 十万个为什么,孩子 总是问 为什么,孩子 奇怪的问题,"
    "娃 的灵魂拷问,孩子 提问 家长答不上,儿童 好奇 提问,孩子 为什么 十万"
).split(",") if q.strip()]
FETCH_TOP_N = env_int("FETCH_TOP_N", 20)        # FR-I02 取 top-20
SEARCH_COUNT = env_int("SEARCH_COUNT", 10)       # zhihu_search 单次条数 (≤10)

# ---------------------------------------------------------------- FR-I02 质量排序
# API 不返回回答数/浏览量, 用可得互动量代理: 赞同(≈浏览质量)×评论(≈讨论度), 对数压尾
RANK_W_VOTE = env_float("RANK_W_VOTE", 1.0)
RANK_W_COMMENT = env_float("RANK_W_COMMENT", 0.6)
RANK_W_AUTHORITY = env_float("RANK_W_AUTHORITY", 0.3)
DEDUP_SIM_THRESHOLD = env_float("DEDUP_SIM_THRESHOLD", 0.8)  # 标题相似度>0.8 合并
DEDUP_RATE_TARGET = 0.05                          # 验收: 重复率 ≤5%

# ---------------------------------------------------------------- FR-I03 LLM 结构化
STRUCT_BATCH = env_int("STRUCT_BATCH", 8)         # 每次LLM调用打包条数

# ---------------------------------------------------------------- FR-I04 审核
KG_URL = env("KG_URL", "http://127.0.0.1:8787").rstrip("/")
KG_SOURCE = "zhihu_intel"                         # /kg/edges:batch 的 source 标识
KG_EDGE_RELS = {"RelatedTo", "UsedFor", "HasProperty", "AtLocation", "MadeOf",
                "CapableOf", "PartOf", "Synonym", "FormOf", "IsA"}  # 对齐 kb/cleaning.py

# ---------------------------------------------------------------- FR-I05 家长语言雷达
RADAR_QUERIES = [q.strip() for q in env(
    "RADAR_QUERIES",
    "英语启蒙 焦虑,孩子 英语 启蒙 方法,英语启蒙 踩坑,幼儿 英语 启蒙 太早,"
    "英语启蒙 路线,自然拼读 焦虑,英语 磨耳朵 有用吗"
).split(",") if q.strip()]
RADAR_WEEKLY_CRON = env("RADAR_WEEKLY_CRON", "mon 09:00")   # 每周一 9:00
REPORT_RECIPIENTS = env("REPORT_RECIPIENTS", "运营群")

# ---------------------------------------------------------------- FR-I06 舆情监控
SENTIMENT_INTERVAL_MIN = env_int("SENTIMENT_INTERVAL_MIN", 30)  # 负面2h内推送→30min轮询
# 品牌词|竞品词|品类词 (kind:brand|competitor|category)
WATCHWORDS = [tuple(w.split(":", 1)) for w in env(
    "WATCHWORDS",
    "小智:brand,王冠:brand,牛娃机:brand,斑马:competitor,叽里呱啦:competitor,"
    "51Talk:competitor,伴鱼:competitor,AI 英语玩具:category,英语学习机:category,"
    "AI 伴学:category"
).split(",") if ":" in w]
NEGATIVE_PUSH = True                              # 负面即时推送
NEGATIVE_SLA_HOURS = 2

# ---------------------------------------------------------------- FR-I08 存档
RAW_RETENTION_DAYS = env_int("RAW_RETENTION_DAYS", 90)   # 原始 JSON 存 90 天
DATA_DIR = Path(env("INTEL_DATA", ROOT / "data"))
RAW_DIR = DATA_DIR / "raw"                        # data/raw/YYYYMMDD/<purpose>/*.json

# ---------------------------------------------------------------- 通知
WECOM_WEBHOOK = env("WECOM_WEBHOOK", "")
OUTBOX_DIR = ROOT / "outbox"                      # webhook 未配置时落盘待发
DIGEST_CRON = env("DIGEST_CRON", "daily 18:30")   # 日报汇总 (§5 不告警风暴)

# ---------------------------------------------------------------- 定时任务
FETCH_CRON = env("FETCH_CRON", "daily 02:00")     # 问题池每日抓取
PURGE_CRON = env("PURGE_CRON", "daily 03:30")     # 90 天归档清理

# ---------------------------------------------------------------- LLM
LLM_API_KEY = env("LLM_API_KEY") or env("OPENAI_API_KEY") or env("KG_LLM_API_KEY")
OPENAI_BASE_URL = env("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
LLM_MODEL = env("LLM_MODEL", env("KG_LLM_MODEL", "gpt-4o-mini"))
LLM_MIN_INTERVAL = env_float("LLM_MIN_INTERVAL", 10.5)

# ---------------------------------------------------------------- 服务
INTEL_PORT = env_int("INTEL_PORT", 8788)
INTEL_TOKEN = env("INTEL_TOKEN", "")              # 设非空则变更接口需 X-Intel-Token
DB_PATH = Path(env("INTEL_DB") or (DATA_DIR / "intel.db"))

# ---------------------------------------------------------------- §8 过滤清单(前置)
# 抓回内容含不当话题(死亡/暴力提问): FR-I03 过滤清单前置 + FR-I04 人工闸门双保险
SENSITIVE_WORDS = [w.strip() for w in env(
    "SENSITIVE_WORDS",
    "死亡,自杀,杀人,暴力,血腥,性,色情,自杀式,虐待,拐卖,坠楼,车祸,凶杀,尸体,"
    "遗书,轻生,毒品,赌博,自杀率,家暴,猥亵,强暴,坠亡,溺亡"
).split(",") if w.strip()]

# ---------------------------------------------------------------- 埋点 (§9)
METRIC_EVENTS = {"intel_fetched", "intel_structured", "intel_approved",
                 "intel_report_sent", "intel_quota_used"}


def ensure_dirs():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    OUTBOX_DIR.mkdir(parents=True, exist_ok=True)
