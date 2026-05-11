#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from typing import Any

from common import load_manifest, read_json, save_manifest, world_dir, write_json


SAFE_HINTS = ("城", "家", "学院", "公会", "拍卖场")
HIGH_RISK_HINTS = ("山脉", "沙漠", "黑角域", "遗迹", "禁地", "中州", "魂界")


def risk_level(name: str, summary: str) -> str:
    text = f"{name} {summary}"
    if any(word in text for word in HIGH_RISK_HINTS):
        return "high"
    if any(word in text for word in SAFE_HINTS):
        return "low"
    return "medium"


def location_entry(location: dict[str, Any]) -> dict[str, Any]:
    name = str(location.get("name", "未知地点"))
    summary = str(location.get("summary") or location.get("claim") or "")
    risk = risk_level(name, summary)
    return {
        "name": name,
        "summary": summary,
        "risk_level": risk,
        "entry_conditions": ["知道路线", "具备最低自保能力"] if risk != "low" else ["知道地点", "未被当地势力驱逐"],
        "available_actions": ["打听情报", "交易", "寻找 NPC"] if risk == "low" else ["探索", "采集资源", "遭遇敌人", "撤退"],
        "resources": ["情报", "低阶资源"] if risk == "low" else ["药材", "魔核", "机缘", "危险情报"],
        "failure_consequences": ["消耗时间"] if risk == "low" else ["受伤", "迷路", "遭遇强敌", "资源损耗"],
    }


def build_locations(world: str) -> dict[str, Any]:
    wdir = world_dir(world)
    locations = read_json(wdir / "locations.json", {}).get("locations", [])
    entries = [location_entry(row) for row in locations if row.get("name")]
    output = {
        "world": world,
        "policy": "Locations define entry conditions, risk, local resources, and default actions.",
        "locations": entries,
    }
    write_json(wdir / "location_runtime.json", output)
    manifest = load_manifest(wdir, world)
    manifest["location_runtime"] = "location_runtime.json"
    save_manifest(wdir, manifest)
    print(f"Built location_runtime.json locations={len(entries)}")
    return output


def load_locations(world: str) -> dict[str, Any]:
    wdir = world_dir(world)
    locations = read_json(wdir / "location_runtime.json", {})
    return locations if locations else build_locations(world)


def find_location(player_input: str, canon_rows: list[dict[str, Any]], locations: dict[str, Any]) -> dict[str, Any] | None:
    names = [row.get("name", "") for row in canon_rows if "location" in str(row.get("type", ""))]
    names.extend(row.get("name", "") for row in locations.get("locations", []))
    for name in names:
        if name and name in player_input:
            return next((row for row in locations.get("locations", []) if row.get("name") == name), None)
    return None


def move_to_location(state: dict[str, Any], location: dict[str, Any]) -> list[str]:
    meta = state.setdefault("meta", {})
    before = meta.get("current_location", "未知地点")
    meta["current_location"] = location.get("name", before)
    meta["current_stage"] = f"{location.get('name')}行动中"
    return [f"地点：{before} -> {meta['current_location']}", f"地点风险：{location.get('risk_level')}"]


def main() -> None:
    parser = argparse.ArgumentParser(description="Build or inspect location runtime data.")
    parser.add_argument("--world", required=True)
    parser.add_argument("--rebuild", action="store_true")
    args = parser.parse_args()
    data = build_locations(args.world) if args.rebuild else load_locations(args.world)
    print(json.dumps(data, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
