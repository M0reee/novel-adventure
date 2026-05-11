#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from collections import defaultdict
from typing import Any

from common import (
    FACT_TYPES,
    load_world_profile,
    load_manifest,
    read_jsonl,
    save_manifest,
    sentence_split,
    sha1_text,
    text_window,
    world_dir,
    write_jsonl,
)


BAD_NAME_PREFIXES = (
    "一个",
    "一些",
    "一种",
    "一道",
    "一名",
    "那",
    "这",
    "他们",
    "我们",
    "已经",
    "若非",
    "却",
    "以及",
    "因为",
    "似乎",
    "终于",
    "只是",
    "继续",
    "我在",
    "当年",
    "帮助",
    "怪今日",
    "会出现",
    "可远远",
    "萧炎",
    "药老",
)
BAD_NAME_PARTS = ("，", "。", "！", "？", "“", "”", "：", "；", "的", "了", "着", "而", "便是", "已经", "忽然", "时候")

KEYWORDS: dict[str, list[str]] = {
    "world_law": ["规则", "限制", "不可", "不能", "必须", "代价", "血脉", "灵魂", "斗气大陆", "异火榜"],
    "cultivation_rule": ["修炼", "突破", "瓶颈", "境界", "功法", "斗气", "斗技", "炼药", "丹药", "异火", "经脉"],
    "event": ["退婚", "三年之约", "拍卖", "招生", "试炼", "追杀", "大战", "陨落", "复仇", "结盟"],
    "relationship": ["师父", "老师", "弟子", "族长", "未婚妻", "同伴", "敌人", "盟友", "父亲", "兄长"],
    "playable_hook": ["悬赏", "委托", "试炼", "拍卖", "残图", "线索", "追杀", "招收", "争夺", "寻药", "炼药"],
}

ITEM_PATTERNS = [
    r"([\u4e00-\u9fff]{2,12}(?:丹|散|灵液|药|火|异火|卷轴|纳戒|重尺|残图|令牌|药鼎))",
]
TECHNIQUE_PATTERNS = [
    r"([\u4e00-\u9fff]{2,12}(?:诀|功|掌|尺|指|身法|斗技|秘法|火莲|雷动|玄变|天怒))",
]


def fact_id(row: dict[str, Any]) -> str:
    basis = f"{row['type']}|{row['name']}|{row['claim']}|{','.join(row['evidence_chunk_ids'])}"
    return "fact_" + sha1_text(basis, 16)


def clean_name(name: str) -> str:
    return re.sub(r"\s+", "", name.strip(" “‘”《》、，。！？；：:.()[]【】\n\t"))


def valid_name(name: str, ftype: str, profile: dict[str, Any]) -> bool:
    name = clean_name(name)
    if len(name) < 2 or len(name) > 10:
        return False
    if any(name.startswith(prefix) for prefix in BAD_NAME_PREFIXES):
        return False
    if any(part in name for part in BAD_NAME_PARTS):
        return False
    if ftype == "npc":
        if profile.get("name") == "doupo":
            return name in profile["known_npcs"]
        return name in profile["known_npcs"] or re.fullmatch(r"[\u4e00-\u9fff]{2,4}", name) is not None
    if ftype == "faction":
        return name in profile["known_factions"] or name.endswith(tuple(profile["faction_suffixes"]))
    if ftype == "location":
        return name in profile["known_locations"] or name.endswith(tuple(profile["location_suffixes"]))
    return True


def add_fact(
    facts: list[dict[str, Any]],
    ftype: str,
    name: str,
    claim: str,
    chunk_id: str,
    confidence: float,
    aliases: list[str] | None = None,
    quality: float | None = None,
) -> None:
    if ftype not in FACT_TYPES:
        return
    name = clean_name(name)
    claim = claim.strip()
    if not name or not claim:
        return
    row = {
        "type": ftype,
        "name": name,
        "claim": claim[:360],
        "aliases": aliases or [],
        "evidence_chunk_ids": [chunk_id],
        "confidence": round(confidence, 2),
        "quality": round(quality if quality is not None else confidence, 2),
    }
    row["fact_id"] = fact_id(row)
    facts.append(row)


def add_known_terms(facts: list[dict[str, Any]], text: str, chunk_id: str, profile: dict[str, Any]) -> None:
    term_sets = [
        ("power_realm", profile["realm_terms"], 0.94),
        ("npc", profile["known_npcs"], 0.93),
        ("faction", profile["known_factions"], 0.94),
        ("location", profile["known_locations"], 0.93),
        ("item", profile["known_items"], 0.9),
        ("technique", profile["known_techniques"], 0.9),
    ]
    for ftype, terms, confidence in term_sets:
        for term in terms:
            start = text.find(term)
            if start >= 0:
                add_fact(facts, ftype, term, text_window(text, start, start + len(term)), chunk_id, confidence, quality=confidence)


def add_suffix_entities(facts: list[dict[str, Any]], text: str, chunk_id: str, profile: dict[str, Any]) -> None:
    faction_suffix = "|".join(re.escape(suffix) for suffix in sorted(profile["faction_suffixes"], key=len, reverse=True))
    location_suffix = "|".join(re.escape(suffix) for suffix in sorted(profile["location_suffixes"], key=len, reverse=True))
    patterns = [
        ("faction", rf"([\u4e00-\u9fff]{{2,8}}(?:{faction_suffix}))", 0.72),
        ("location", rf"([\u4e00-\u9fff]{{2,8}}(?:{location_suffix}))", 0.7),
    ]
    seen: set[tuple[str, str]] = set()
    for ftype, pattern, confidence in patterns:
        count = 0
        for match in re.finditer(pattern, text):
            name = clean_name(match.group(1))
            if (ftype, name) in seen or not valid_name(name, ftype, profile):
                continue
            seen.add((ftype, name))
            add_fact(facts, ftype, name, text_window(text, match.start(), match.end()), chunk_id, confidence, [ftype], quality=0.66)
            count += 1
            if count >= 10:
                break


def add_dialogue_npcs(facts: list[dict[str, Any]], text: str, chunk_id: str, profile: dict[str, Any]) -> None:
    pattern = r"([\u4e00-\u9fff]{2,4})(?:低声|淡淡|沉声|冷笑|笑着|笑道|喝|问|说|道|叹道|怒道)"
    count = 0
    for match in re.finditer(pattern, text):
        name = clean_name(match.group(1))
        if not valid_name(name, "npc", profile):
            continue
        add_fact(facts, "npc", name, text_window(text, match.start(), match.end()), chunk_id, 0.68, quality=0.6)
        count += 1
        if count >= 8:
            break


def add_pattern_terms(facts: list[dict[str, Any]], text: str, chunk_id: str) -> None:
    for ftype, patterns, confidence in [
        ("item", ITEM_PATTERNS, 0.68),
        ("technique", TECHNIQUE_PATTERNS, 0.68),
    ]:
        seen: set[str] = set()
        for pattern in patterns:
            for match in re.finditer(pattern, text):
                name = clean_name(match.group(1))
                if name in seen or len(name) > 10 or any(part in name for part in BAD_NAME_PARTS):
                    continue
                seen.add(name)
                add_fact(facts, ftype, name, text_window(text, match.start(), match.end()), chunk_id, confidence, quality=0.58)
                if len(seen) >= 8:
                    break


def add_keyword_claims(facts: list[dict[str, Any]], sentences: list[str], chunk_id: str) -> None:
    per_type_count: defaultdict[str, int] = defaultdict(int)
    for sentence in sentences:
        if len(sentence) < 8 or len(sentence) > 260:
            continue
        for ftype, words in KEYWORDS.items():
            if per_type_count[ftype] >= 6:
                continue
            hits = [word for word in words if word in sentence]
            if hits:
                add_fact(facts, ftype, hits[0], sentence, chunk_id, 0.68 + min(len(hits), 3) * 0.05, hits[1:], quality=0.62)
                per_type_count[ftype] += 1


def extract_chunk(chunk: dict[str, Any], profile: dict[str, Any]) -> list[dict[str, Any]]:
    text = chunk["text"]
    chunk_id = chunk["chunk_id"]
    sentences = sentence_split(text)
    facts: list[dict[str, Any]] = []
    add_known_terms(facts, text, chunk_id, profile)
    add_suffix_entities(facts, text, chunk_id, profile)
    add_dialogue_npcs(facts, text, chunk_id, profile)
    add_pattern_terms(facts, text, chunk_id)
    add_keyword_claims(facts, sentences, chunk_id)

    dialogue_marks = text.count("“") + text.count('"')
    if dialogue_marks > 6:
        add_fact(facts, "style_signal", "对白密度", "该片段对白密度较高，运行时可增加人物交锋和短句推进。", chunk_id, 0.6, quality=0.55)
    if any(word in text for word in ("冷笑", "杀意", "威压", "追杀", "退婚", "三年之约")):
        add_fact(facts, "style_signal", "高压冲突", "该片段包含强冲突或压迫感，运行时应保留紧张感和后果压力。", chunk_id, 0.64, quality=0.58)

    dedup: dict[str, dict[str, Any]] = {}
    for row in facts:
        existing = dedup.get(row["fact_id"])
        if not existing or float(row.get("quality", 0.0)) > float(existing.get("quality", 0.0)):
            dedup[row["fact_id"]] = row
    return list(dedup.values())


def extract(world: str, profile_name: str | None = None) -> None:
    wdir = world_dir(world)
    manifest = load_manifest(wdir, world)
    profile = load_world_profile(wdir, profile_name or manifest.get("profile", "generic"))
    chunks = read_jsonl(wdir / "chunks.jsonl")
    if not chunks:
        raise SystemExit("No chunks found. Run ingest.py first.")

    facts: list[dict[str, Any]] = []
    for chunk in chunks:
        facts.extend(extract_chunk(chunk, profile))

    write_jsonl(wdir / "facts.jsonl", facts)
    manifest["profile"] = profile["name"]
    manifest["fact_count"] = len(facts)
    manifest["extractor"] = "profiled_heuristic_v2"
    save_manifest(wdir, manifest)
    print(f"Extracted {len(facts)} fact(s) into {wdir / 'facts.jsonl'} with profile={profile['name']}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract structured canon facts from chunks.")
    parser.add_argument("--world", required=True)
    parser.add_argument("--profile", help="Built-in profile name or generated profile from world_profile.json.")
    args = parser.parse_args()
    extract(args.world, args.profile)


if __name__ == "__main__":
    main()
