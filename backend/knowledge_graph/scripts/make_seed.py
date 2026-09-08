#!/usr/bin/env python3
"""W1 整理: Cambridge YL 词表(Starters/Movers/Flyers) + CEFR-J A1 补充 → data/seed.csv

输入(已下载到 raw/):
  - raw/yle-vocabulary-dataset.csv      Cambridge YLE 词表镜像(含 POS/级别/主题标记)
  - raw/cefrj-vocabulary-profile-1.5.csv CEFR-J 词表(A1 内容词补充, 保证 ≥1500 词)

产出:
  - data/seed.csv                三列: word,level,pos (level ∈ starters/movers/flyers/a1/a2)
  - data/word_variants.csv       英美拼写映射(内部用, 供 ConceptNet 匹配: colour→color)
  - data/reports/level_distribution.csv  级别分布统计(W1-2 要求)

规则:
  - 同词多词性合并(pos 用 | 连接), 级别取最低
  - YLE 词为权威来源; CEFR-J 只补 A1 内容词(名词/动词/形容词/副词/数词)
"""
import csv
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "raw"
DATA = ROOT / "data"
REPORTS = DATA / "reports"

# 儿童安全政策: 官方 YL 词表里出现、但儿童产品不教的词(与 cleaning.ADULT_TAILS 同源)。
# 移出教学词表, 计入 excluded_words.csv 备查。
POLICY_EXCLUDE = {
    "beer", "wine", "whisky", "alcohol", "cocktail", "cigarette", "cigarettes",
    "tobacco", "drug", "drugs", "blood", "death", "funeral", "war", "gun", "guns",
    "kill", "murder", "suicide", "casino", "gambling", "prison", "jail", "sexy",
    "sex", "naked", "affair", "adultery", "divorce", "poverty", "slavery", "slave",
    "cancer", "virus", "terrorist", "terrorism", "bomb", "weapon", "weapons",
    "champagne", "brandy", "vodka", "sherry", "lager",
}


def norm(w: str) -> str:
    w = w.strip().lower()
    return re.sub(r"\s+", " ", w)


def base_form(w: str) -> str:
    """剥离 YL 词表的义类括号: 'band (music)' → 'band'。"""
    return norm(re.sub(r"\s*\([^)]*\)\s*", " ", w))


def unaccent(w: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", w)
                   if not unicodedata.combining(c))

POS_COLS = ["adjective", "adverb", "conjunction", "determiner", "discourse_marker",
            "exclamation", "interrogative", "noun", "possessive", "preposition",
            "pronoun", "title", "verb"]
THEME_COLS = ["animals", "body_and_face", "clothes", "colours", "family_and_friends",
              "food_and_drink", "health", "home", "materials", "names", "numbers",
              "places_and_directions", "school", "sports_and_leisure", "time", "toys",
              "transport", "weather", "work", "world_around_us"]
LEVEL_RANK = {"starters": 0, "movers": 1, "flyers": 2, "a1": 3, "a2": 4}
# CEFR 级别映射到与 YL 同一体系(用于打包 L0-L5 与去重)
CEFR_ACCEPT = {"A1": "a1", "A2": "a2"}
CEFRJ_POS_ACCEPT = {"noun", "verb", "adjective", "adverb", "number"}


def norm(w: str) -> str:
    w = w.strip().lower()
    return re.sub(r"\s+", " ", w)


def truthy(v: str) -> bool:
    return str(v).strip().upper() == "TRUE"


def load_yle():
    """返回 words: {word: {level,pos}}, variants: {us_spelling: uk_word}, excluded"""
    words, variants, excluded = {}, {}, []
    path = RAW / "yle-vocabulary-dataset.csv"
    with open(path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            uk, us = base_form(row["british"]), base_form(row["american"])
            if not uk:
                continue
            if uk in POLICY_EXCLUDE:
                excluded.append((uk, "yle", "kid_safety_policy"))
                continue
            pos = "|".join(c for c in POS_COLS if truthy(row.get(c, ""))) or "noun"
            levels = [lv for lv in ("starters", "movers", "flyers") if truthy(row.get(lv, ""))]
            level = min(levels, key=lambda x: LEVEL_RANK[x]) if levels else "starters"
            theme = next((c for c in THEME_COLS if truthy(row.get(c, ""))), "")
            if uk in words:
                # 同词多词性/多级别合并, 级别取最低
                merged = set(words[uk]["pos"].split("|")) | set(pos.split("|"))
                words[uk]["pos"] = "|".join(sorted(merged))
                if LEVEL_RANK[level] < LEVEL_RANK[words[uk]["level"]]:
                    words[uk]["level"] = level
            else:
                words[uk] = {"level": level, "pos": pos, "source": "yle", "theme": theme}
            # 变体: 美式拼写 / 下划线形式 / 去重音, 供 ConceptNet 归一匹配
            for v in {us, uk.replace(" ", "_"), unaccent(uk), unaccent(us).replace(" ", "_")}:
                if v and v != uk:
                    variants.setdefault(v, uk)
    return words, variants, excluded


def load_cefrj(existing):
    """CEFR-J A1/A2 内容词补充。跳过多变体/短语过长的条目。"""
    words = {}
    path = RAW / "cefrj-vocabulary-profile-1.5.csv"
    with open(path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            head, pos, cefr = norm(row["headword"]), row["pos"].strip(), row["CEFR"].strip().upper()
            if cefr not in CEFR_ACCEPT or pos not in CEFRJ_POS_ACCEPT:
                continue
            if "/" in head or "(" in head or "." in head:
                continue  # a.m./A.M./am/AM 这类多变体跳过
            if len(head.split()) > 2 or not re.fullmatch(r"[a-z][a-z' -]*", head):
                continue
            if head in POLICY_EXCLUDE:
                continue
            if head in existing or head in words:
                continue
            words[head] = {"level": CEFR_ACCEPT[cefr], "pos": pos,
                           "source": f"cefrj-{cefr}", "theme": ""}
    return words


def add_variants(variants, word):
    """为多词短语/重音词补匹配变体: alarm clock → alarm_clock; café → cafe。"""
    for v in {word.replace(" ", "_"), unaccent(word),
              unaccent(word).replace(" ", "_")}:
        if v and v != word:
            variants.setdefault(v, word)


def main():
    REPORTS.mkdir(parents=True, exist_ok=True)
    yle_words, variants, excluded = load_yle()
    for word in yle_words:
        add_variants(variants, word)
    all_words = dict(yle_words)
    cefr_words = load_cefrj(set(all_words))
    for word in cefr_words:
        add_variants(variants, word)
    all_words.update(cefr_words)

    seed_path = DATA / "seed.csv"
    with open(seed_path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["word", "level", "pos"])
        for word in sorted(all_words):
            meta = all_words[word]
            w.writerow([word, meta["level"], meta["pos"]])

    with open(DATA / "word_variants.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["variant", "word"])
        for v in sorted(variants):
            w.writerow([v, variants[v]])

    with open(REPORTS / "excluded_words.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["word", "source", "reason"])
        for row in excluded:
            w.writerow(row)

    dist = Counter(m["level"] for m in all_words.values())
    with open(REPORTS / "level_distribution.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["level", "count"])
        for lv in ("starters", "movers", "flyers", "a1", "a2"):
            w.writerow([lv, dist.get(lv, 0)])

    print(f"seed.csv: {len(all_words)} 词 (YLE {len(yle_words)} + CEFR-J 补充 {len(cefr_words)}; "
          f"政策排除 {len(excluded)})")
    print("级别分布:", dict(sorted(dist.items(), key=lambda kv: LEVEL_RANK[kv[0]])))
    if len(all_words) < 1500:
        print("!! 少于 1500 词, W1 不达标", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
