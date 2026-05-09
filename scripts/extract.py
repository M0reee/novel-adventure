#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from collections import defaultdict
from typing import Any

from common import FACT_TYPES, load_manifest, read_jsonl, save_manifest, sentence_split, sha1_text, world_dir, write_jsonl


PATTERNS: dict[str, list[tuple[str, str]]] = {
    "power_realm": [
        ("境界", r"(凡体|练气|炼气|筑基|金丹|元婴|化神|炼虚|合体|大乘|渡劫|练虚|合道|真仙|玄仙|金仙|仙王|仙帝)(?:境|期|阶|层)?"),
    ],
    "faction": [
        ("势力", r"([\u4e00-\u9fff]{2,14}(?:宗|门|派|宫|阁|楼|殿|教|盟|族|家|王朝|皇朝|商会|帮|寨|堂|司))"),
    ],
    "location": [
        ("地点", r"([\u4e00-\u9fff]{2,16}(?:山|岭|谷|城|镇|村|坊市|秘境|洞府|禁地|森林|荒原|海|江|河|湖|峰|岛|矿|涧|州|域|界))"),
    ],
    "item": [
        ("物品", r"([\u4e00-\u9fff]{2,16}(?:丹|符|剑|刀|枪|鼎|炉|珠|令|玉|草|药|石|灵石|法宝|阵盘|残图|卷轴))"),
    ],
    "technique": [
        ("功法", r"([\u4e00-\u9fff]{2,16}(?:诀|经|功|法|术|掌|拳|剑法|刀法|阵|咒|印))"),
    ],
}

KEYWORDS: dict[str, list[str]] = {
    "world_law": ["天道", "因果", "禁忌", "规则", "限制", "不可", "不能", "必须", "代价", "灵气", "心魔", "天劫"],
    "cultivation_rule": ["修炼", "突破", "瓶颈", "境界", "闭关", "丹药", "功法", "灵根", "经脉", "走火入魔"],
    "event": ["大战", "开启", "大比", "拍卖", "追杀", "陨落", "灭门", "秘境", "围攻", "悬赏", "招收"],
    "relationship": ["师父", "师尊", "弟子", "师兄", "师姐", "仇", "敌", "盟友", "道侣", "血脉", "同门", "背叛"],
    "playable_hook": ["悬赏", "委托", "秘境", "拍卖", "遗宝", "追杀", "试炼", "招收", "争夺", "线索", "残图"],
}

SAID_RE = re.compile(r"([\u4e00-\u9fff]{2,4})(?:冷声|淡淡|沉声|笑道|说道|问道|喝道|低声|叹道|怒道|开口)")


def fact_id(row: dict[str, Any]) -> str:
    basis = f"{row['type']}|{row['name']}|{row['claim']}|{','.join(row['evidence_chunk_ids'])}"
    return "fact_" + sha1_text(basis, 16)


def add_fact(facts: list[dict[str, Any]], ftype: str, name: str, claim: str, chunk_id: str, confidence: float, aliases: list[str] | None = None) -> None:
    if ftype not in FACT_TYPES:
        return
    name = name.strip(" ：:，,。！？!?\n\t ")
    claim = claim.strip()
    if not name or not claim or len(name) > 40:
        return
    row = {
        "type": ftype,
        "name": name,
        "claim": claim[:260],
        "aliases": aliases or [],
        "evidence_chunk_ids": [chunk_id],
        "confidence": round(confidence, 2),
    }
    row["fact_id"] = fact_id(row)
    facts.append(row)


def extract_chunk(chunk: dict[str, Any]) -> list[dict[str, Any]]:
    text = chunk["text"]
    chunk_id = chunk["chunk_id"]
    sentences = sentence_split(text)
    facts: list[dict[str, Any]] = []
    per_type_count: defaultdict[str, int] = defaultdict(int)

    for sentence in sentences:
        if len(sentence) < 8:
            continue
        for ftype, words in KEYWORDS.items():
            if per_type_count[ftype] >= 12:
                continue
            hits = [word for word in words if word in sentence]
            if hits:
                name = hits[0]
                add_fact(facts, ftype, name, sentence, chunk_id, 0.66 + min(len(hits), 3) * 0.06, hits[1:])
                per_type_count[ftype] += 1

    for ftype, entries in PATTERNS.items():
        seen: set[str] = set()
        for label, pattern in entries:
            for match in re.finditer(pattern, text):
                name = match.group(1)
                if name in seen or per_type_count[ftype] >= 16:
                    continue
                seen.add(name)
                start = max(0, match.start() - 80)
                end = min(len(text), match.end() + 120)
                claim = text[start:end].replace("\n", " ")
                add_fact(facts, ftype, name, claim, chunk_id, 0.72, [label])
                per_type_count[ftype] += 1

    for match in SAID_RE.finditer(text):
        if per_type_count["npc"] >= 12:
            break
        name = match.group(1)
        start = max(0, match.start() - 60)
        end = min(len(text), match.end() + 120)
        add_fact(facts, "npc", name, text[start:end].replace("\n", " "), chunk_id, 0.62)
        per_type_count["npc"] += 1

    dialogue_marks = text.count("“") + text.count('"')
    if dialogue_marks > 6:
        add_fact(facts, "style_signal", "对白密度", "该片段对白密度较高，运行时可增加人物交锋和短句推进。", chunk_id, 0.6)
    if any(word in text for word in ("冷笑", "杀意", "威压", "血腥", "追杀")):
        add_fact(facts, "style_signal", "压迫冲突", "该片段包含强压迫或斗争风格，运行时可保留紧张感和后果压力。", chunk_id, 0.64)

    dedup: dict[str, dict[str, Any]] = {}
    for row in facts:
        dedup[row["fact_id"]] = row
    return list(dedup.values())


def extract(world: str) -> None:
    wdir = world_dir(world)
    chunks = read_jsonl(wdir / "chunks.jsonl")
    if not chunks:
        raise SystemExit("No chunks found. Run ingest.py first.")

    facts: list[dict[str, Any]] = []
    for chunk in chunks:
        facts.extend(extract_chunk(chunk))

    write_jsonl(wdir / "facts.jsonl", facts)
    manifest = load_manifest(wdir, world)
    manifest["fact_count"] = len(facts)
    manifest["extractor"] = "heuristic_v1"
    save_manifest(wdir, manifest)
    print(f"Extracted {len(facts)} fact(s) into {wdir / 'facts.jsonl'}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract structured canon facts from chunks.")
    parser.add_argument("--world", required=True)
    args = parser.parse_args()
    extract(args.world)


if __name__ == "__main__":
    main()

