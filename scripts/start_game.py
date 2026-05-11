#!/usr/bin/env python3
from __future__ import annotations

import argparse

from common import default_player_state, migrate_player_state, read_json, write_json, world_dir
from list_worlds import discover_worlds, format_worlds
from opening import ensure_opening, format_opening
from rpg_profile import apply_rpg_profile_to_state, format_stat_block, load_rpg_profile


def choose_world() -> str:
    rows = discover_worlds()
    if not rows:
        raise SystemExit("No playable worlds found. Build one with scripts/build_world.py first.")
    print(format_worlds(rows))
    choice = input("请选择要游玩的世界编号或 slug: ").strip()
    if choice.isdigit():
        idx = int(choice)
        if 1 <= idx <= len(rows):
            return rows[idx - 1]["slug"]
    for row in rows:
        if choice == row["slug"]:
            return row["slug"]
    raise SystemExit(f"Unknown world choice: {choice}")


def initialize_state(world: str, reset: bool = False) -> dict:
    wdir = world_dir(world)
    opening = ensure_opening(world)
    rpg_profile = load_rpg_profile(world)
    state_path = wdir / "player_state.json"
    if reset or not state_path.exists():
        state = default_player_state(world)
        state = apply_rpg_profile_to_state(state, rpg_profile, force_starter=True)
        state["background"] = opening.get("player_background", state.get("background", {}))
        state["meta"]["current_location"] = opening.get("starting_location", state["meta"].get("current_location", "未确定起点"))
        state["meta"]["current_time"] = opening.get("starting_time", state["meta"].get("current_time", "第一日 清晨"))
        write_json(state_path, state)
    else:
        state = migrate_player_state(read_json(state_path, {}), world)
        state = apply_rpg_profile_to_state(state, rpg_profile)
        if not state.get("background"):
            state["background"] = opening.get("player_background", {})
        write_json(state_path, state)
    return state


def main() -> None:
    parser = argparse.ArgumentParser(description="Choose a world, initialize a save, and print the opening scene.")
    parser.add_argument("--world")
    parser.add_argument("--reset", action="store_true", help="Reset player_state.json before starting.")
    args = parser.parse_args()
    world = args.world or choose_world()
    state = initialize_state(world, args.reset)
    opening = ensure_opening(world)
    print(format_opening(opening))
    print("")
    print("## 当前角色")
    player = state.get("player", {})
    print(f"- 身份：{player.get('identity')}")
    print(f"- 境界/等级：{player.get('realm_or_level')}")
    for line in format_stat_block(player.get("stats", {}), load_rpg_profile(world)):
        print(line)
    print("")
    print("输入下一步行动，例如：")
    print(f"python scripts/run_turn.py --world {world} --input \"观察周围环境\"")


if __name__ == "__main__":
    main()
