#!/usr/bin/env python3
from __future__ import annotations

from typing import Any


def economy_readiness(state: dict[str, Any]) -> dict[str, Any]:
    player = state.get("player", {})
    coins = int(player.get("currencies", {}).get("coins", 0))
    checked_resources = []
    for scene in state.get("runtime", {}).get("scenes", {}).values():
        for name, row in scene.get("known_resources", {}).items():
            if row.get("checked"):
                checked_resources.append(name)
    return {
        "coins": coins,
        "checked_resources": checked_resources[-6:],
        "can_shop": coins > 0,
        "policy": "购买必须检查 item_market.json 的价格、供应、真假风险和当前金币。",
    }


def combat_readiness(state: dict[str, Any]) -> dict[str, Any]:
    player = state.get("player", {})
    stats = player.get("stats", {})
    hp = float(stats.get("hp", 0))
    max_hp = max(1.0, float(stats.get("max_hp", 1)))
    mp = float(stats.get("mp", 0))
    max_mp = max(1.0, float(stats.get("max_mp", 1)))
    return {
        "hp_ratio": round(hp / max_hp, 2),
        "resource_ratio": round(mp / max_mp, 2),
        "skills": [skill.get("name") for skill in player.get("skills", []) if isinstance(skill, dict)],
        "policy": "战斗和训练必须走 combat.py/game_math.py，装备、技能和 Buff 会进入属性计算。",
    }


def runtime_summary_lines(state: dict[str, Any]) -> list[str]:
    economy = economy_readiness(state)
    combat = combat_readiness(state)
    lines = [
        f"- 经济：金币 {economy['coins']}；已调查资源：{('、'.join(economy['checked_resources']) or '无')}",
        f"- 战斗/训练：生命 {combat['hp_ratio'] * 100:.0f}%；资源 {combat['resource_ratio'] * 100:.0f}%；技能：{('、'.join(combat['skills']) or '无')}",
    ]
    return lines
