#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections import defaultdict
from typing import Any

from common import default_player_state, load_manifest, read_json, read_jsonl, save_manifest, write_json, write_jsonl, world_dir


NEGATIVE_WORDS = ("不可", "不能", "无法", "禁止", "不许")
POSITIVE_WORDS = ("可以", "能够", "可", "允许", "能")


def norm_name(name: str) -> str:
    return name.strip().replace("　", "").lower()


def group_facts(facts: list[dict[str, Any]]) -> dict[str, dict[str, dict[str, Any]]]:
    grouped: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for fact in facts:
        ftype = fact["type"]
        key = norm_name(fact["name"])
        if key not in grouped[ftype]:
            grouped[ftype][key] = {
                "name": fact["name"],
                "type": ftype,
                "aliases": set(),
                "claims": [],
                "evidence_chunk_ids": set(),
                "confidence": 0.0,
            }
        item = grouped[ftype][key]
        item["aliases"].update(fact.get("aliases", []))
        item["claims"].append(
            {
                "claim": fact["claim"],
                "confidence": fact.get("confidence", 0.5),
                "evidence_chunk_ids": fact.get("evidence_chunk_ids", []),
            }
        )
        item["evidence_chunk_ids"].update(fact.get("evidence_chunk_ids", []))
        item["confidence"] = max(item["confidence"], fact.get("confidence", 0.5))
    return grouped


def finalize_entity(item: dict[str, Any]) -> dict[str, Any]:
    claims = item["claims"]
    unique_claims = []
    seen = set()
    has_negative = False
    has_positive = False
    for claim in claims:
        text = claim["claim"]
        if text not in seen:
            unique_claims.append(claim)
            seen.add(text)
        has_negative = has_negative or any(word in text for word in NEGATIVE_WORDS)
        has_positive = has_positive or any(word in text for word in POSITIVE_WORDS)
    entity = {
        "name": item["name"],
        "aliases": sorted(alias for alias in item["aliases"] if alias and alias != item["name"]),
        "summary": unique_claims[0]["claim"] if unique_claims else "",
        "claims": unique_claims[:8],
        "evidence_chunk_ids": sorted(item["evidence_chunk_ids"]),
        "confidence": round(item["confidence"], 2),
        "conflict_status": "unresolved" if has_negative and has_positive and len(unique_claims) > 1 else "clear",
    }
    return entity


def entities(grouped: dict[str, dict[str, dict[str, Any]]], ftype: str) -> list[dict[str, Any]]:
    return sorted((finalize_entity(item) for item in grouped.get(ftype, {}).values()), key=lambda row: row["name"])


def build_game_rules(grouped: dict[str, dict[str, dict[str, Any]]]) -> dict[str, Any]:
    cultivation = entities(grouped, "cultivation_rule")
    locations = entities(grouped, "location")
    items = entities(grouped, "item")
    hooks = entities(grouped, "playable_hook")
    return {
        "action_rules": [
            {
                "action": "修炼/突破",
                "requirements": ["满足当前境界条件", "安全地点", "足够资源或机缘"],
                "risks": ["失败反噬", "心魔", "资源损耗", "暴露气息"],
                "rewards": ["境界提升", "能力边界扩大", "解锁新地点或身份"],
                "source_entities": [row["name"] for row in cultivation[:20]],
            },
            {
                "action": "探索地点",
                "requirements": ["知道入口或路线", "具备最低自保能力"],
                "risks": ["遭遇敌对势力", "陷阱", "时间流逝", "错过其他事件"],
                "rewards": ["资源", "情报", "NPC关系", "新任务"],
                "source_entities": [row["name"] for row in locations[:20]],
            },
            {
                "action": "交易/炼制/使用物品",
                "requirements": ["拥有货币、材料或对应技艺"],
                "risks": ["赝品", "价格波动", "副作用", "引人觊觎"],
                "rewards": ["恢复", "增益", "突破辅助", "剧情线索"],
                "source_entities": [row["name"] for row in items[:20]],
            },
        ],
        "hooks_to_surface": [row["summary"] for row in hooks[:30]],
    }


def merge(world: str) -> None:
    wdir = world_dir(world)
    facts = read_jsonl(wdir / "facts.jsonl")
    if not facts:
        raise SystemExit("No facts found. Run extract.py first.")

    grouped = group_facts(facts)
    world_bible = {
        "world": world,
        "world_laws": entities(grouped, "world_law"),
        "style_signals": entities(grouped, "style_signal"),
    }
    power_system = {
        "realms": entities(grouped, "power_realm"),
        "cultivation_rules": entities(grouped, "cultivation_rule"),
    }
    factions = {"factions": entities(grouped, "faction")}
    locations = {"locations": entities(grouped, "location")}
    npcs = {"npcs": entities(grouped, "npc")}
    timeline = {"events": entities(grouped, "event")}
    adventure_hooks = {"hooks": entities(grouped, "playable_hook")}
    game_rules = build_game_rules(grouped)

    write_json(wdir / "world_bible.json", world_bible)
    write_json(wdir / "power_system.json", power_system)
    write_json(wdir / "factions.json", factions)
    write_json(wdir / "locations.json", locations)
    write_json(wdir / "npcs.json", npcs)
    write_json(wdir / "timeline.json", timeline)
    write_json(wdir / "game_rules.json", game_rules)
    write_json(wdir / "adventure_hooks.json", adventure_hooks)

    patches_path = wdir / "canon_patches.jsonl"
    if not patches_path.exists():
        write_jsonl(patches_path, [])
    player_state_path = wdir / "player_state.json"
    if not player_state_path.exists():
        write_json(player_state_path, default_player_state(world))
    else:
        state = read_json(player_state_path, {})
        if "action_log" in state:
            state["action_log"] = state["action_log"][-30:]
            write_json(player_state_path, state)

    manifest = load_manifest(wdir, world)
    manifest["merged_files"] = [
        "world_bible.json",
        "power_system.json",
        "factions.json",
        "locations.json",
        "npcs.json",
        "timeline.json",
        "game_rules.json",
        "adventure_hooks.json",
    ]
    save_manifest(wdir, manifest)
    print(f"Merged {len(facts)} fact(s) into structured canon files in {wdir}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Merge extracted facts into structured world canon.")
    parser.add_argument("--world", required=True)
    args = parser.parse_args()
    merge(args.world)


if __name__ == "__main__":
    main()

