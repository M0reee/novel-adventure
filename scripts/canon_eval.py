#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from typing import Any

from common import load_manifest, read_json, save_manifest, sha1_text, world_dir, write_json


def build_canon_eval(world: str) -> dict[str, Any]:
    wdir = world_dir(world)
    skill_tree = read_json(wdir / "skill_tree.json", {}).get("nodes", [])
    equipment_sets = read_json(wdir / "equipment_sets.json", {}).get("sets", [])
    ability_boundaries = read_json(wdir / "ability_boundaries.json", {}).get("abilities", [])
    quests = read_json(wdir / "quest_templates.json", {}).get("quests", [])
    cases: list[dict[str, Any]] = []
    for node in skill_tree[:8]:
        name = node.get("name")
        if name:
            cases.append(
                {
                    "case_id": "eval_" + sha1_text(f"skill:{name}", 10),
                    "type": "skill_gate",
                    "input": f"我直接学会{name}",
                    "expected": "blocked_or_conditional_until_source",
                    "source": "skill_tree.json",
                }
            )
    for row in equipment_sets[:6]:
        name = row.get("name")
        if name:
            cases.append(
                {
                    "case_id": "eval_" + sha1_text(f"equipment:{name}", 10),
                    "type": "equipment_gate",
                    "input": f"我直接获得{name}套装效果",
                    "expected": "blocked_unless_enabled_and_equipped",
                    "source": "equipment_sets.json",
                }
            )
    for ability in ability_boundaries[:8]:
        name = ability.get("name")
        if name:
            cases.append(
                {
                    "case_id": "eval_" + sha1_text(f"ability:{name}", 10),
                    "type": "ability_boundary",
                    "input": f"我用{name}直接解决所有问题",
                    "expected": "must_check_cost_risk_requirement",
                    "source": "ability_boundaries.json",
                }
            )
    for quest in quests[:8]:
        name = quest.get("name")
        if name:
            cases.append(
                {
                    "case_id": "eval_" + sha1_text(f"quest:{name}", 10),
                    "type": "quest_lifecycle",
                    "input": f"我瞬间完成{name}并领取奖励",
                    "expected": "must_progress_lifecycle_before_reward",
                    "source": "quest_templates.json",
                }
            )
    output = {
        "world": world,
        "policy": "Regression cases are generated from canon-derived projections. They test anti-OOC behavior and do not encode a fixed genre template.",
        "cases": cases,
    }
    write_json(wdir / "canon_eval.json", output)
    manifest = load_manifest(wdir, world)
    manifest["canon_eval"] = "canon_eval.json"
    save_manifest(wdir, manifest)
    print(f"Built canon_eval.json cases={len(cases)}")
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description="Build canon regression eval cases.")
    parser.add_argument("--world", required=True)
    parser.add_argument("--rebuild", action="store_true")
    args = parser.parse_args()
    data = build_canon_eval(args.world) if args.rebuild else read_json(world_dir(args.world) / "canon_eval.json", {})
    print(json.dumps(data, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
