#!/usr/bin/env python3
from __future__ import annotations

import argparse

from common import default_player_state, migrate_player_state, read_json
from equipment_sets import refresh_player_set_bonuses
from list_worlds import discover_worlds, format_worlds
from opening import ensure_opening, format_opening
from rpg_profile import apply_rpg_profile_to_state, format_stat_block, load_rpg_profile
from save_manager import save_path, write_save


def infer_initial_option_intent(option: str) -> str:
    text = str(option)
    if any(word in text for word in ("管事", "伙计", "NPC", "搭话", "询问")):
        return "social"
    if any(word in text for word in ("观察", "判断", "确认", "打听", "木牌")):
        return "info"
    if any(word in text for word in ("杂务", "跑腿", "任务", "账单", "报酬")):
        return "quest"
    if any(word in text for word in ("修炼", "突破", "吐纳")):
        return "cultivation"
    if any(word in text for word in ("购买", "交易", "坊市", "价格")):
        return "trade"
    return "general"


def sync_opening_options(state: dict, opening: dict) -> None:
    options = [str(option) for option in opening.get("initial_options", []) if str(option).strip()]
    if not options:
        return
    state.setdefault("meta", {})["last_options"] = [
        {
            "index": idx,
            "id": f"opening_option_{idx}",
            "text": option,
            "intent": infer_initial_option_intent(option),
        }
        for idx, option in enumerate(options, 1)
    ]


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


def initialize_state(world: str, reset: bool = False, slot: str | None = None) -> dict:
    opening = ensure_opening(world)
    rpg_profile = load_rpg_profile(world)
    state_path = save_path(world, slot)
    if reset or not state_path.exists():
        state = default_player_state(world)
        state = apply_rpg_profile_to_state(state, rpg_profile, force_starter=True)
        refresh_player_set_bonuses(world, state)
        state["background"] = opening.get("player_background", state.get("background", {}))
        opening_identity = state["background"].get("identity") or state["background"].get("origin")
        if opening_identity:
            state.setdefault("player", {})["identity"] = opening_identity
        state["meta"]["current_location"] = opening.get("starting_location", state["meta"].get("current_location", "未确定起点"))
        state["meta"]["current_time"] = opening.get("starting_time", state["meta"].get("current_time", "第一日 清晨"))
        state["meta"]["current_stage"] = "开局选择"
        sync_opening_options(state, opening)
        write_save(world, slot, state)
    else:
        state = migrate_player_state(read_json(state_path, {}), world)
        state = apply_rpg_profile_to_state(state, rpg_profile)
        refresh_player_set_bonuses(world, state)
        if not state.get("background"):
            state["background"] = opening.get("player_background", {})
        if not state.get("meta", {}).get("last_options"):
            sync_opening_options(state, opening)
        write_save(world, slot, state)
    return state


def main() -> None:
    parser = argparse.ArgumentParser(description="Choose a world, initialize a save, and print the opening scene.")
    parser.add_argument("--world")
    parser.add_argument("--slot", help="Named save slot. Default uses player_state.json.")
    parser.add_argument("--reset", action="store_true", help="Reset player_state.json before starting.")
    args = parser.parse_args()
    world = args.world or choose_world()
    state = initialize_state(world, args.reset, args.slot)
    opening = ensure_opening(world)
    print(format_opening(opening))
    print("")
    print("## 当前角色")
    player = state.get("player", {})
    print(f"- 身份：{player.get('identity')}")
    print(f"- 境界/等级：{player.get('realm_or_level')}")
    print(f"- 存档：{state.get('meta', {}).get('save_slot', 'default')}")
    for line in format_stat_block(player.get("stats", {}), load_rpg_profile(world)):
        print(line)
    print("")
    print("输入下一步行动，例如：")
    slot_arg = f" --slot {args.slot}" if args.slot else ""
    print(f"python scripts/run_turn.py --world {world}{slot_arg} --input \"观察周围环境\"")


if __name__ == "__main__":
    main()
