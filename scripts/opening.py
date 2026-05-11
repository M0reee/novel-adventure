#!/usr/bin/env python3
from __future__ import annotations

import argparse
from typing import Any

from common import default_background, load_manifest, read_json, save_manifest, world_dir, write_json


def _first_names(rows: list[dict[str, Any]], limit: int = 4) -> list[str]:
    return [str(row.get("name")) for row in rows[:limit] if row.get("name")]


def build_opening(world: str) -> dict[str, Any]:
    wdir = world_dir(world)
    manifest = load_manifest(wdir, world)
    locations = read_json(wdir / "locations.json", {}).get("locations", [])
    factions = read_json(wdir / "factions.json", {}).get("factions", [])
    npcs = read_json(wdir / "npcs.json", {}).get("npcs", [])
    hooks = read_json(wdir / "adventure_hooks.json", {}).get("hooks", [])
    background = default_background(world)

    display_name = manifest.get("display_name") or world
    starting_location = _first_names(locations, 1)[0] if locations else "未确定起点"
    primary_faction = _first_names(factions, 1)[0] if factions else "本地势力"
    first_npc = _first_names(npcs, 1)[0] if npcs else "本地人"
    hook_names = _first_names(hooks, 4) or background["starting_hooks"]

    if manifest.get("profile") == "doupo" or "doupo" in world:
        opening = {
            "world": world,
            "display_name": display_name,
            "player_background": background,
            "starting_location": "乌坦城",
            "starting_time": "第一日 清晨",
            "initial_options": [
                "观察萧家练武场，确认自己能接触哪些修炼机会。",
                "去乌坦城拍卖场打听低阶修炼资源。",
                "寻找可靠的人询问如何开始修炼斗气。",
                "自定义行动。",
            ],
        }
    else:
        opening = {
            "world": world,
            "display_name": display_name,
            "player_background": {
                "origin": background["origin"],
                "opening_scene": f"你来到「{starting_location}」，这里与「{primary_faction}」关系密切，{first_npc}等人物可能影响你的第一步选择。",
                "motivation": background["motivation"],
                "starting_conflict": "你缺少可靠资源、关系和情报，需要先确认世界规则，再寻找安全成长路径。",
                "starting_hooks": hook_names,
            },
            "starting_location": starting_location,
            "starting_time": "第一日 清晨",
            "initial_options": [
                f"观察「{starting_location}」周围环境，确认风险。",
                f"打听「{primary_faction}」的规矩和可接任务。",
                "寻找可靠 NPC，询问这个世界的基础生存方式。",
                "自定义行动。",
            ],
        }
    write_json(wdir / "opening.json", opening)
    manifest["opening"] = "opening.json"
    save_manifest(wdir, manifest)
    return opening


def ensure_opening(world: str) -> dict[str, Any]:
    wdir = world_dir(world)
    existing = read_json(wdir / "opening.json", {})
    return existing or build_opening(world)


def format_opening(opening: dict[str, Any]) -> str:
    bg = opening.get("player_background", {})
    options = opening.get("initial_options", [])
    lines = [
        f"# {opening.get('display_name', opening.get('world', '未知世界'))}",
        "",
        "## 你是谁",
        str(bg.get("origin", "无名旅人")),
        "",
        "## 开场",
        str(bg.get("opening_scene", "")),
        "",
        "## 你想要什么",
        str(bg.get("motivation", "")),
        "",
        "## 当前困难",
        str(bg.get("starting_conflict", "")),
        "",
        "## 可选开局行动",
    ]
    lines.extend(f"{idx}. {option}" for idx, option in enumerate(options, 1))
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate or print a world's opening scene.")
    parser.add_argument("--world", required=True)
    parser.add_argument("--rebuild", action="store_true")
    args = parser.parse_args()
    opening = build_opening(args.world) if args.rebuild else ensure_opening(args.world)
    print(format_opening(opening))


if __name__ == "__main__":
    main()
