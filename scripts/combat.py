#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import random
from copy import deepcopy
from typing import Any

from common import migrate_player_state, read_json, write_json, world_dir
from combat_profiles import combat_profile_for, combat_risk_note
from game_math import computed_stats, damage_roll, skill_by_id, tick_effects
from rpg_profile import apply_rpg_profile_to_state, load_rpg_profile
from runtime_effects import apply_effects


ENEMY_TEMPLATES: dict[str, dict[str, Any]] = {
    "training_dummy": {
        "enemy_id": "training_dummy",
        "name": "练武木桩",
        "level": 1,
        "stats": {
            "hp": 35,
            "max_hp": 35,
            "mp": 0,
            "max_mp": 0,
            "attack": 0,
            "defense": 2,
            "speed": 0,
            "hit_rate": 0.0,
            "dodge_rate": 0.0,
            "crit_rate": 0.0,
            "crit_damage": 1.0,
            "damage_bonus": 0.0,
            "damage_reduction": 0.0,
        },
        "rewards": {"exp": 5, "coins": [0, 0], "items": []},
    },
    "low_thug": {
        "enemy_id": "low_thug",
        "name": "低阶混混",
        "level": 1,
        "stats": {
            "hp": 45,
            "max_hp": 45,
            "mp": 10,
            "max_mp": 10,
            "attack": 8,
            "defense": 2,
            "speed": 5,
            "hit_rate": 0.9,
            "dodge_rate": 0.02,
            "crit_rate": 0.03,
            "crit_damage": 1.4,
            "damage_bonus": 0.0,
            "damage_reduction": 0.0,
        },
        "rewards": {
            "exp": 20,
            "coins": [3, 8],
            "items": [{"item_id": "minor_healing_powder", "name": "粗制止血粉", "drop_rate": 0.15}],
        },
    },
}


def enemy_stats(enemy: dict[str, Any]) -> dict[str, float]:
    return {key: float(value) for key, value in enemy.get("stats", {}).items()}


def apply_rewards(state: dict[str, Any], rewards: dict[str, Any], rng: random.Random, rpg_profile: dict[str, Any]) -> list[str]:
    player = state.setdefault("player", {})
    stats = player.setdefault("stats", {})
    currencies = player.setdefault("currencies", {"coins": 0})
    inventory = player.setdefault("inventory", [])
    messages: list[str] = []
    terms = rpg_profile.get("terminology", {})
    exp_label = terms.get("exp", "经验")
    level_label = terms.get("level", "等级")
    currency_label = rpg_profile.get("systems", {}).get("currency_name", "货币")

    exp = int(rewards.get("exp", 0))
    if exp:
        stats["exp"] = int(stats.get("exp", 0)) + exp
        messages.append(f"获得{exp_label} {exp}")
        while int(stats.get("exp", 0)) >= int(stats.get("exp_to_next", 100)):
            stats["exp"] = int(stats["exp"]) - int(stats.get("exp_to_next", 100))
            stats["level"] = int(stats.get("level", 1)) + 1
            stats["exp_to_next"] = int(round(int(stats.get("exp_to_next", 100)) * 1.25))
            stats["max_hp"] = int(stats.get("max_hp", 100)) + 10
            stats["max_mp"] = int(stats.get("max_mp", 40)) + 4
            stats["attack"] = int(stats.get("attack", 12)) + 2
            stats["defense"] = int(stats.get("defense", 5)) + 1
            stats["hp"] = stats["max_hp"]
            stats["mp"] = stats["max_mp"]
            messages.append(f"{level_label}提升到 {stats['level']}")

    coins_range = rewards.get("coins", [0, 0])
    if isinstance(coins_range, list) and len(coins_range) == 2:
        coins = rng.randint(int(coins_range[0]), int(coins_range[1]))
    else:
        coins = int(coins_range or 0)
    if coins:
        currencies["coins"] = int(currencies.get("coins", 0)) + coins
        messages.append(f"获得{currency_label} {coins}")

    for item in rewards.get("items", []):
        if rng.random() <= float(item.get("drop_rate", 1.0)):
            inventory.append({key: value for key, value in item.items() if key != "drop_rate"})
            messages.append(f"获得物品 {item.get('name', item.get('item_id', '未知物品'))}")
    return messages


def resolve_combat_round(state: dict[str, Any], enemy: dict[str, Any], skill_id: str | None, seed: int | None = None) -> dict[str, Any]:
    state = migrate_player_state(state, state.get("meta", {}).get("world", "unknown"))
    rpg_profile = load_rpg_profile(state.get("meta", {}).get("world", "unknown"))
    state = apply_rpg_profile_to_state(state, rpg_profile)
    genre_profile = combat_profile_for(rpg_profile)
    rng = random.Random(seed)
    player = state["player"]
    skill = skill_by_id(player, skill_id)
    p_stats = computed_stats(state)
    e_stats = enemy_stats(enemy)
    resource_label = rpg_profile.get("systems", {}).get("resource_name", "能量")

    if p_stats.get("mp", 0) < float(skill.get("mp_cost", 0)):
        return {"status": "blocked", "messages": [f"{resource_label}不足，无法使用 {skill.get('name')}。"], "state": state}
    player["stats"]["mp"] = max(0, float(player["stats"].get("mp", 0)) - float(skill.get("mp_cost", 0)))

    player_attack = damage_roll(p_stats, e_stats, skill, rng)
    enemy["stats"]["hp"] = max(0, int(enemy["stats"].get("hp", 0)) - int(player_attack["damage"]))
    messages = [
        f"你使用 {skill.get('name')}。",
        "攻击未命中。" if not player_attack["hit"] else f"造成 {player_attack['damage']} 点伤害" + ("（暴击）。" if player_attack["critical"] else "。"),
        combat_risk_note(genre_profile),
    ]
    effect_messages = apply_effects(state.get("meta", {}).get("world", "unknown"), state, genre_profile.get("effects_on_attack", []), "题材化战斗后果")

    rewards: list[str] = []
    if int(enemy["stats"].get("hp", 0)) <= 0:
        messages.append(f"{enemy.get('name')} 被击败。")
        if genre_profile.get("victory_note"):
            messages.append(str(genre_profile["victory_note"]))
        rewards = apply_rewards(state, enemy.get("rewards", {}), rng, rpg_profile)
    elif float(e_stats.get("attack", 0)) > 0:
        enemy_attack = damage_roll(e_stats, computed_stats(state), {"name": "反击", "power": 1.0}, rng)
        player["stats"]["hp"] = max(0, int(player["stats"].get("hp", 0)) - int(enemy_attack["damage"]))
        messages.append("敌人反击未命中。" if not enemy_attack["hit"] else f"敌人反击造成 {enemy_attack['damage']} 点伤害。")

    tick_effects(player)
    return {
        "status": "resolved",
        "messages": messages + effect_messages + rewards,
        "player_stats": computed_stats(state),
        "enemy": enemy,
        "skill": skill,
        "state": state,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Resolve one deterministic RPG combat round.")
    parser.add_argument("--world", required=True)
    parser.add_argument("--enemy", default="training_dummy", choices=sorted(ENEMY_TEMPLATES))
    parser.add_argument("--skill")
    parser.add_argument("--seed", type=int)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    wdir = world_dir(args.world)
    state_path = wdir / "player_state.json"
    state = read_json(state_path, {})
    enemy = deepcopy(ENEMY_TEMPLATES[args.enemy])
    result = resolve_combat_round(state, enemy, args.skill, args.seed)
    if not args.dry_run:
        write_json(state_path, result["state"])
    printable = {key: value for key, value in result.items() if key != "state"}
    print(json.dumps(printable, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
