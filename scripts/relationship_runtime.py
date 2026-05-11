#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from typing import Any

from common import load_manifest, read_json, save_manifest, world_dir, write_json


def build_relationship_rules(world: str) -> dict[str, Any]:
    wdir = world_dir(world)
    npcs = read_json(wdir / "npcs.json", {}).get("npcs", [])
    factions = read_json(wdir / "factions.json", {}).get("factions", [])
    rules = {
        "world": world,
        "scale": {"hostile": -50, "wary": -10, "neutral": 0, "friendly": 25, "trusted": 60},
        "npcs": [{"name": row.get("name"), "default_score": 0, "notes": row.get("summary", "")} for row in npcs if row.get("name")],
        "factions": [{"name": row.get("name"), "default_score": 0, "notes": row.get("summary", "")} for row in factions if row.get("name")],
        "policy": "Relationship scores affect help, prices, information access, hostility, and debt.",
    }
    write_json(wdir / "relationship_rules.json", rules)
    manifest = load_manifest(wdir, world)
    manifest["relationship_rules"] = "relationship_rules.json"
    save_manifest(wdir, manifest)
    print(f"Built relationship_rules.json npcs={len(rules['npcs'])} factions={len(rules['factions'])}")
    return rules


def load_relationship_rules(world: str) -> dict[str, Any]:
    wdir = world_dir(world)
    rules = read_json(wdir / "relationship_rules.json", {})
    return rules if rules else build_relationship_rules(world)


def relationship_bucket(score: int) -> str:
    if score <= -50:
        return "hostile"
    if score < -10:
        return "wary"
    if score >= 60:
        return "trusted"
    if score >= 25:
        return "friendly"
    return "neutral"


def adjust_relationship(state: dict[str, Any], target: str, delta: int, reason: str) -> str:
    if not target:
        return ""
    relationships = state.setdefault("relationships", [])
    row = next((item for item in relationships if item.get("target") == target), None)
    if not row:
        row = {"target": target, "score": 0, "bucket": "neutral", "notes": []}
        relationships.append(row)
    before = int(row.get("score", 0))
    after = max(-100, min(100, before + delta))
    row["score"] = after
    row["bucket"] = relationship_bucket(after)
    row.setdefault("notes", []).append(reason)
    row["notes"] = row["notes"][-10:]
    return f"{target}关系：{before} -> {after}（{row['bucket']}）"


def detect_target(player_input: str, canon_rows: list[dict[str, Any]], rules: dict[str, Any]) -> str:
    names = [row.get("name", "") for row in canon_rows if row.get("type") in {"npc", "faction"}]
    names.extend(row.get("name", "") for row in rules.get("npcs", []) + rules.get("factions", []))
    for name in names:
        if name and name in player_input:
            return name
    return ""


def main() -> None:
    parser = argparse.ArgumentParser(description="Build or inspect relationship rules.")
    parser.add_argument("--world", required=True)
    parser.add_argument("--rebuild", action="store_true")
    args = parser.parse_args()
    rules = build_relationship_rules(args.world) if args.rebuild else load_relationship_rules(args.world)
    print(json.dumps(rules, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
