#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from copy import deepcopy
from typing import Any

from combat import ENEMY_TEMPLATES
from common import load_manifest, read_json, save_manifest, world_dir, write_json


def default_encounter_state(world: str) -> dict[str, Any]:
    return {
        "world": world,
        "active": None,
        "history": [],
        "policy": "Active enemies persist between turns until defeated, escaped, or cleared.",
    }


def build_encounter_state(world: str) -> dict[str, Any]:
    wdir = world_dir(world)
    state = read_json(wdir / "encounter_state.json", default_encounter_state(world))
    state.setdefault("world", world)
    state.setdefault("active", None)
    state.setdefault("history", [])
    state.setdefault("policy", "Active enemies persist between turns until defeated, escaped, or cleared.")
    write_json(wdir / "encounter_state.json", state)
    manifest = load_manifest(wdir, world)
    manifest["encounter_state"] = "encounter_state.json"
    save_manifest(wdir, manifest)
    print("Built encounter_state.json")
    return state


def load_encounters(world: str) -> dict[str, Any]:
    wdir = world_dir(world)
    state = read_json(wdir / "encounter_state.json", {})
    return state if state else build_encounter_state(world)


def choose_enemy_id(player_input: str) -> str:
    if any(word in player_input for word in ("木桩", "练武", "训练", "切磋")):
        return "training_dummy"
    return "low_thug"


def start_or_get_encounter(encounters: dict[str, Any], player_input: str) -> tuple[dict[str, Any], bool]:
    active = encounters.get("active")
    if active and active.get("enemy", {}).get("stats", {}).get("hp", 0) > 0:
        return active["enemy"], False
    enemy_id = choose_enemy_id(player_input)
    enemy = deepcopy(ENEMY_TEMPLATES[enemy_id])
    encounters["active"] = {
        "encounter_id": f"enc_{len(encounters.get('history', [])) + 1:04d}",
        "enemy": enemy,
        "round": 0,
        "status": "active",
    }
    return enemy, True


def record_combat_result(encounters: dict[str, Any], enemy: dict[str, Any], messages: list[str]) -> list[str]:
    active = encounters.setdefault("active", {})
    active["enemy"] = enemy
    active["round"] = int(active.get("round", 0)) + 1
    enemy_hp = int(enemy.get("stats", {}).get("hp", 0))
    changes = [f"遭遇轮次：{active['round']}"]
    if enemy_hp <= 0:
        active["status"] = "defeated"
        active["result"] = "enemy_defeated"
        active["messages"] = messages[-6:]
        encounters.setdefault("history", []).append(active)
        encounters["history"] = encounters["history"][-20:]
        encounters["active"] = None
        changes.append("遭遇结束：敌人被击败。")
    else:
        active["status"] = "active"
        changes.append(f"敌方剩余生命：{enemy_hp}/{enemy.get('stats', {}).get('max_hp', enemy_hp)}")
    return changes


def clear_encounter(world: str) -> None:
    wdir = world_dir(world)
    state = load_encounters(world)
    if state.get("active"):
        state.setdefault("history", []).append({**state["active"], "status": "cleared"})
    state["active"] = None
    write_json(wdir / "encounter_state.json", state)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build or inspect persistent encounter state.")
    parser.add_argument("--world", required=True)
    parser.add_argument("--clear", action="store_true")
    args = parser.parse_args()
    if args.clear:
        clear_encounter(args.world)
    state = load_encounters(args.world)
    print(json.dumps(state, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
