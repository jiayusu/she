#!/usr/bin/env python3
"""清洗规则层 (W2 第一层): 纯规则审边, 不依赖任何模型。

规则(对齐 READMD.md):
  - 非英文 / 边长>40 / 成人歧义(apple→computer) / 品牌与成人话题 / 自环 / 关系白名单

rule_check() 返回 (ok, reason), 被 build_kg.py 与 server.py 的热更链共用。
"""
import csv
import re
import unicodedata

RELEDGE_RE = re.compile(r"^[a-z][a-z_]{0,39}$")
MAX_EDGE_LEN = 40
MAX_TOKENS = 3

RELATIONS = {"RelatedTo", "UsedFor", "HasProperty", "AtLocation", "MadeOf",
             "CapableOf", "PartOf", "Synonym", "FormOf", "IsA"}

# 成人/不宜儿童话题: 任一端命中即删
ADULT_TAILS = {
    "sex", "sexy", "sexual", "porn", "pornography", "naked", "nude", "nudity",
    "beer", "wine", "vodka", "whisky", "whiskey", "alcohol", "cocktail", "rum",
    "cigarette", "cigarettes", "tobacco", "cigar", "vaping", "marijuana", "cannabis",
    "heroin", "cocaine", "drug", "drugs", "drug_addiction", "needle",
    "gun", "guns", "rifle", "pistol", "bullet", "ammunition", "weapon", "weapons",
    "war", "warfare", "battlefield", "terrorism", "terrorist", "bomb", "grenade",
    "kill", "killing", "murder", "murderer", "assassin", "suicide", "torture",
    "blood", "bloodshed", "gore", "corpse", "dead_body", "slaughter",
    "death", "dying", "funeral", "coffin",
    "casino", "gambling", "betting", "lottery", "roulette", "poker",
    "prison", "jail", "gaol", "handcuffs", "execution", "electric_chair",
    "hatred", "hate", "racism", "slur", "insult",
    "prostitute", "prostitution", "brothel", "strip_club", "escort",
    "divorce", "adultery", "affair",
    "satan", "devil_worship", "occult", "witchcraft", "black_magic",
    "poverty", "starvation", "famine", "genocide", "slavery", "slave",
}

# 品牌/科技产品等成人向歧义端: 儿童词表里这些是品牌义而非词义
BRAND_HEADS = {
    "apple_inc", "microsoft", "google", "facebook", "instagram", "twitter",
    "youtube", "tiktok", "amazon", "netflix", "samsung", "nike", "adidas",
    "puma", "lego", "disney", "warner_bros", "coca_cola", "pepsi", "mcdonalds",
    "mcdonald", "starbucks", "kfc", "burger_king", "toyota", "honda", "ford",
    "bmw", "mercedes", "ferrari", "sony", "nintendo", "playstation", "xbox",
    "windows", "android", "iphone", "ipad", "macbook", "blackberry",
    "facebook_inc", "wikipedia", "ebay", "paypal", "visa", "mastercard",
}

# 已知"同形异义"词: 这些尾概念是成人义/品牌义, 与儿童词义冲突 → 删
AMBIGUOUS = {
    "apple": {"computer", "computers", "laptop", "macintosh", "company", "company_",
              "brand", "product", "corporation", "tech_company", "software",
              "operating_system", "iphone", "record_label", "iphone_model"},
    "amazon": {"company", "river", "rainforest", "jungle"},  # amazon 本身非 YL 词, 保险
    "windows": {"operating_system", "software", "microsoft_windows", "os",
                "computer_operating_system"},
    "blackberry": {"smartphone", "phone", "mobile_phone", "cell_phone", "brand"},
    "raspberry": {"computer", "single_board_computer", "microcontroller"},
    "python": {"programming_language", "snake_species", "code", "software"},
    "jaguar": {"car", "automobile", "motor_car", "luxury_car", "brand"},
    "shell": {"oil_company", "gas_station", "petrol_station", "company", "brand"},
    "mouse": {"computer_mouse", "pointing_device", "input_device"},
    "orange": {"mobile_network", "telecom_company", "phone_network", "brand"},
    "mango": {"phone", "mobile_phone", "smartphone", "brand"},
    "tomtom": {"gps"},
    "polo": {"car", "automobile", "brand", "sport"},
    "corona": {"beer", "virus", "crown_of_virus"},
    "galaxy": {"phone", "smartphone", "samsung_galaxy", "brand"},
    "nile": {"river_in_africa"},  # 保留普通概念即可
    "twitter": {"social_network", "website", "company"},
    "victoria": {"queen", "state", "waterfall", "city"},  # 人名课程词, 只留普适义
}


def _fold(side: str) -> str:
    """比较用折叠: 去重音(café→cafe)、空格/连字符→下划线。"""
    s = "".join(c for c in unicodedata.normalize("NFKD", side)
                if not unicodedata.combining(c))
    return s.strip().lower().replace(" ", "_").replace("-", "_")


# "酒饮"补充(官方词表有但儿童产品不教, 概念端也不留)
ADULT_TAILS |= {"cider", "sherry", "champagne", "brandy", "vodka", "lager", "sake", "mead"}


# ---------------------------------------------------------------- 常用词白名单
# W2 人工抽检发现的系统性问题: 词表词 ↔ 生僻概念(velocipede/palinism 等)的边
# 对儿童 KG 无价值。加严规则: 非词表一侧必须是常用词(词表 ∪ CEFR-J 全级别)。
COMMON_LEXICON = None  # frozenset, 由 build_lexicon() 装载


def build_lexicon(seed_path, cefrj_path):
    """词表词 ∪ CEFR-J 全级别词 → 规则层的常用词白名单。"""
    global COMMON_LEXICON
    lex = set()
    with open(seed_path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            w = row["word"].strip().lower()
            lex.update({w, w.replace(" ", "_")})
    with open(cefrj_path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            w = row["headword"].strip().lower()
            if "/" in w or "(" in w:
                continue
            lex.update({w, w.replace(" ", "_")})
    COMMON_LEXICON = frozenset(lex)
    return COMMON_LEXICON


def rule_check(head: str, rel: str, tail: str,
               head_sense: str = "", tail_sense: str = "",
               weight: float = 1.0, relations=None):
    """返回 (ok, reason)。reason 为删除原因, ok=True 时为 ''。"""
    relations = relations or RELATIONS
    if rel not in relations:
        return False, f"rel_not_allowed:{rel}"
    if not head or not tail:
        return False, "empty_side"
    if head == tail or _fold(head) == _fold(tail):
        return False, "self_loop"
    if head_sense.startswith("internet_slang") or tail_sense.startswith("internet_slang"):
        return False, "internet_slang"
    for side in (head, tail):
        folded = _fold(side)
        if not RELEDGE_RE.match(folded):
            return False, f"non_english:{side}"
        if len(folded) > MAX_EDGE_LEN or len(folded.split("_")) > MAX_TOKENS:
            return False, f"too_long:{side}"
    if head in ADULT_TAILS or tail in ADULT_TAILS:
        return False, "adult_topic"
    if head in BRAND_HEADS or tail in BRAND_HEADS:
        return False, "brand_or_product"
    amb = AMBIGUOUS.get(head)
    if amb and tail in amb:
        return False, f"adult_ambiguity:{head}->{tail}"
    if COMMON_LEXICON is not None:
        for side in (head, tail):
            if side not in COMMON_LEXICON and _fold(side) not in COMMON_LEXICON:
                return False, f"not_common_word:{side}"
    if weight is not None and weight < 0.5:
        return False, "too_weak"
    return True, ""
