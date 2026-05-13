#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from typing import Any

from common import read_json, world_dir, write_json


def check_world(world: str) -> dict[str, Any]:
    wdir = world_dir(world)
    skill_tree = read_json(wdir / "skill_tree.json", {})
    equipment_sets = read_json(wdir / "equipment_sets.json", {})
    routes = read_json(wdir / "acquisition_routes.json", {})
    issues: list[str] = []

    for node in skill_tree.get("nodes", []):
        name = node.get("name", "未命名技能")
        gate = node.get("canon_gate")
        if not gate:
            issues.append(f"技能缺 canon_gate：{name}")
            continue
        if gate.get("acquisition_required", True) and gate.get("availability") == "learned_at_start":
            issues.append(f"技能 acquisition_required 与 learned_at_start 冲突：{name}")
        if not gate.get("ooc_policy"):
            issues.append(f"技能缺 OOC 策略：{name}")

    for row in equipment_sets.get("sets", []):
        name = row.get("name", "未命名装备协同")
        gate = row.get("canon_gate")
        if gate is None or "enabled" not in row:
            issues.append(f"装备协同缺 gate/enabled：{name}")
            continue
        if row.get("enabled") and gate.get("canon_confidence") == "low":
            issues.append(f"低证据装备协同不应启用：{name}")

    route_targets = {(route.get("target_type"), route.get("target")) for route in routes.get("routes", [])}
    for node in skill_tree.get("nodes", []):
        if ("skill", node.get("name")) not in route_targets:
            issues.append(f"技能缺获取路线：{node.get('name')}")
    for item in read_json(wdir / "item_market.json", {}).get("items", []):
        if ("item", item.get("name")) not in route_targets:
            issues.append(f"物品缺获取路线：{item.get('name')}")

    report = {
        "world": world,
        "score": max(0, 100 - len(issues) * 5),
        "passed": not issues,
        "issues": issues,
        "policy": "OOC QA blocks direct grants of skills/equipment without canon gate and acquisition route.",
    }
    write_json(wdir / "ooc_report.json", report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Run OOC/canon-gate QA checks.")
    parser.add_argument("--world", required=True)
    args = parser.parse_args()
    print(json.dumps(check_world(args.world), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
