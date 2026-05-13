#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from typing import Any

from common import load_manifest, read_json, read_jsonl, save_manifest, sha1_text, world_dir, write_json


CARD_SOURCES = (
    "playable_canon.json",
    "ability_boundaries.json",
    "story_arcs.json",
    "event_chains.json",
    "skill_tree.json",
    "acquisition_routes.json",
)
BAD_NAMES = {"不会", "没有理会", "这种等级", "听得药", "当前", "对方", "什么", "卷轴", "方才", "轻声"}
RAW_NOISE = ("目光", "脸庞", "微微", "手掌", "笑道", "说道", "袖袍", "缓缓", "身体", "直接动手吧", "这才", "先前")


def good_name(name: str) -> bool:
    value = str(name or "").strip()
    if not value or value in BAD_NAMES:
        return False
    if value.startswith(("当", "这", "那", "其", "而")) and len(value) > 4:
        return False
    if len(value) > 18:
        return False
    return not any(mark in value for mark in ("。", "，", "；", "：", "？", "！", "\n"))


def compact(value: Any, limit: int = 120) -> str:
    text = " ".join(str(value or "").replace("\n", " ").split()).strip(" ，。；：")
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip("，。；： ") + "…"


def looks_like_excerpt(text: str) -> bool:
    value = str(text or "").strip()
    if not value:
        return True
    if value.startswith(("，", "。", "；", "：", "“", "”", "\"", "'", "兴叹", "这废物")):
        return True
    quote_count = value.count("“") + value.count("”") + value.count("\"")
    if len(value) > 90 and quote_count >= 2:
        return True
    return len(value) > 100 and any(noise in value for noise in RAW_NOISE)


def rows_from_json(filename: str, data: dict[str, Any]) -> list[dict[str, Any]]:
    buckets = {
        "power_system.json": [("power_realm", data.get("realms", [])), ("cultivation_rule", data.get("cultivation_rules", []))],
        "items.json": [("item", data.get("items", []))],
        "techniques.json": [("technique", data.get("techniques", []))],
        "locations.json": [("location", data.get("locations", []))],
        "npcs.json": [("npc", data.get("npcs", []))],
        "factions.json": [("faction", data.get("factions", []))],
        "playable_canon.json": [("playable", data.get("entries", []))],
        "ability_boundaries.json": [("ability_boundary", data.get("abilities", []))],
        "story_arcs.json": [("story_arc", data.get("arcs", []))],
        "event_chains.json": [("event_chain", data.get("chains", []))],
        "skill_tree.json": [("skill", data.get("nodes", []))],
        "acquisition_routes.json": [("acquisition_route", data.get("routes", []))],
    }
    rows: list[dict[str, Any]] = []
    for row_type, entries in buckets.get(filename, []):
        for entry in entries:
            if isinstance(entry, dict):
                row = dict(entry)
                row["_type"] = row_type
                rows.append(row)
    return rows


def card_from_row(filename: str, row: dict[str, Any]) -> dict[str, Any] | None:
    name = str(row.get("name") or row.get("target") or row.get("npc") or row.get("arc_id") or row.get("chain_id") or "").strip()
    if not good_name(name):
        return None
    summary = (
        row.get("summary")
        or row.get("claim")
        or row.get("description")
        or row.get("public_goal")
        or row.get("objective")
        or row.get("rule")
        or row.get("ooc_policy")
        or (row.get("canon_gate") or {}).get("ooc_policy")
        or ""
    )
    rule = compact(summary)
    if not rule or looks_like_excerpt(rule):
        return None
    row_type = str(row.get("_type") or row.get("type") or "canon")
    return {
        "card_id": "ecard_" + sha1_text(f"{filename}:{row_type}:{name}:{rule}", 14),
        "type": row_type,
        "name": name,
        "source": filename,
        "rule": rule,
        "limits": [compact(item, 72) for item in row.get("cannot_do", [])[:3] if item]
        or [compact(item, 72) for item in row.get("risks", [])[:3] if item],
        "requirements": [compact(item, 72) for item in row.get("requirements", [])[:3] if item]
        or [compact(item, 72) for item in row.get("unlock_conditions", [])[:3] if item],
        "confidence": row.get("confidence") or row.get("canon_strength") or row.get("canon_confidence") or "medium",
    }


def build_evidence_cards(world: str) -> dict[str, Any]:
    wdir = world_dir(world)
    cards: list[dict[str, Any]] = []
    seen: set[str] = set()
    for filename in CARD_SOURCES:
        data = read_json(wdir / filename, {})
        for row in rows_from_json(filename, data):
            card = card_from_row(filename, row)
            if not card or card["card_id"] in seen:
                continue
            seen.add(card["card_id"])
            cards.append(card)
    for row in read_jsonl(wdir / "canon_patches.jsonl"):
        card = card_from_row("canon_patches.jsonl", {"_type": "canon_patch", "name": row.get("target"), "rule": row.get("rule"), "confidence": "hard"})
        if card and card["card_id"] not in seen:
            cards.insert(0, card)
            seen.add(card["card_id"])
    output = {
        "world": world,
        "policy": "Evidence cards are short canon-facing summaries for runtime explanation. They do not replace source files or grant new abilities.",
        "cards": cards[:600],
    }
    write_json(wdir / "evidence_cards.json", output)
    manifest = load_manifest(wdir, world)
    manifest["evidence_cards"] = "evidence_cards.json"
    save_manifest(wdir, manifest)
    print(f"Built evidence_cards.json cards={len(output['cards'])}")
    return output


def load_evidence_cards(world: str) -> dict[str, Any]:
    data = read_json(world_dir(world) / "evidence_cards.json", {})
    return data if data else build_evidence_cards(world)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build compact canon evidence cards.")
    parser.add_argument("--world", required=True)
    parser.add_argument("--rebuild", action="store_true")
    args = parser.parse_args()
    data = build_evidence_cards(args.world) if args.rebuild else load_evidence_cards(args.world)
    print(json.dumps(data, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
