#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import random
from copy import deepcopy
from typing import Any

from common import default_stats, migrate_player_state, read_json, world_dir


STAT_KEYS = set(default_stats())
PERCENT_STATS = {"hit_rate", "dodge_rate", "crit_rate", "crit_damage", "damage_bonus", "damage_reduction"}


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _add_stat(stats: dict[str, float], key: str, value: Any) -> None:
    if key not in STAT_KEYS:
        return
    stats[key] = float(stats.get(key, 0)) + float(value)


def base_player_stats(state: dict[str, Any]) -> dict[str, float]:
    player = state.get("player", {})
    base = deepcopy(default_stats())
    for key, value in player.get("stats", {}).items():
        if key in STAT_KEYS:
            base[key] = float(value)
    return base


def equipment_modifiers(player: dict[str, Any]) -> dict[str, float]:
    mods: dict[str, float] = {}
    equipment = player.get("equipment", {})
    if isinstance(equipment, dict):
        items = [item for item in equipment.values() if isinstance(item, dict)]
    else:
        items = [item for item in equipment if isinstance(item, dict)]
    for item in items:
        for key, value in item.get("stats", {}).items():
            _add_stat(mods, key, value)
    return mods


def effect_modifiers(player: dict[str, Any]) -> dict[str, float]:
    mods: dict[str, float] = {}
    for effect in player.get("active_effects", []):
        if not isinstance(effect, dict):
            continue
        for key, value in effect.get("modifiers", {}).items():
            _add_stat(mods, key, value)
    return mods


def equipment_set_modifiers(player: dict[str, Any]) -> dict[str, float]:
    mods: dict[str, float] = {}
    for row in player.get("equipment_set_bonuses", []):
        if not isinstance(row, dict):
            continue
        for key, value in row.get("modifiers", {}).items():
            _add_stat(mods, key, value)
    return mods


def computed_stats(state: dict[str, Any]) -> dict[str, float]:
    state = migrate_player_state(state, state.get("meta", {}).get("world", "unknown"))
    player = state["player"]
    stats = base_player_stats(state)
    for mods in (equipment_modifiers(player), equipment_set_modifiers(player), effect_modifiers(player)):
        for key, value in mods.items():
            _add_stat(stats, key, value)
    stats["hp"] = clamp(stats["hp"], 0, stats["max_hp"])
    stats["mp"] = clamp(stats["mp"], 0, stats["max_mp"])
    for key in PERCENT_STATS:
        if key in stats and key != "crit_damage":
            stats[key] = clamp(stats[key], 0.0, 1.0)
    stats["crit_damage"] = max(1.0, stats.get("crit_damage", 1.5))
    return {key: round(value, 4) for key, value in stats.items()}


def skill_by_id(player: dict[str, Any], skill_id: str | None) -> dict[str, Any]:
    skills = [skill for skill in player.get("skills", []) if isinstance(skill, dict)]
    if skill_id:
        for skill in skills:
            if skill.get("skill_id") == skill_id:
                return skill
    return skills[0] if skills else {"skill_id": "basic_attack", "name": "普通攻击", "power": 1.0, "mp_cost": 0, "effects": []}


def hit_chance(attacker: dict[str, float], defender: dict[str, float], skill: dict[str, Any]) -> float:
    return clamp(attacker.get("hit_rate", 0.95) + float(skill.get("accuracy_modifier", 0.0)) - defender.get("dodge_rate", 0.0), 0.05, 0.98)


def damage_roll(attacker: dict[str, float], defender: dict[str, float], skill: dict[str, Any], rng: random.Random) -> dict[str, Any]:
    chance = hit_chance(attacker, defender, skill)
    if rng.random() > chance:
        return {"hit": False, "critical": False, "damage": 0, "hit_chance": round(chance, 4)}
    base = max(1.0, attacker.get("attack", 1.0) * float(skill.get("power", 1.0)) - defender.get("defense", 0.0))
    crit_rate = clamp(attacker.get("crit_rate", 0.0) + float(skill.get("crit_modifier", 0.0)), 0.0, 1.0)
    critical = rng.random() < crit_rate
    if critical:
        base *= attacker.get("crit_damage", 1.5)
    damage = base * (1 + attacker.get("damage_bonus", 0.0)) * (1 - defender.get("damage_reduction", 0.0))
    return {"hit": True, "critical": critical, "damage": max(1, int(round(damage))), "hit_chance": round(chance, 4)}


def tick_effects(player: dict[str, Any]) -> None:
    kept = []
    for effect in player.get("active_effects", []):
        if not isinstance(effect, dict):
            continue
        duration = int(effect.get("duration_turns", 0)) - 1
        if duration > 0:
            effect["duration_turns"] = duration
            kept.append(effect)
    player["active_effects"] = kept


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect computed RPG stats for a world save.")
    parser.add_argument("--world", required=True)
    args = parser.parse_args()
    wdir = world_dir(args.world)
    state = read_json(wdir / "player_state.json", {})
    print(json.dumps(computed_stats(state), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
