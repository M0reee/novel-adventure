#!/usr/bin/env python3
from __future__ import annotations

from typing import Any


def hp_ratio(stats: dict[str, Any]) -> float:
    max_hp = max(1.0, float(stats.get("max_hp", stats.get("hp", 1)) or 1))
    return max(0.0, min(1.0, float(stats.get("hp", 0)) / max_hp))


def choose_enemy_action(enemy: dict[str, Any], player_stats: dict[str, float], round_no: int) -> dict[str, Any]:
    stats = enemy.get("stats", {})
    ratio = hp_ratio(stats)
    profile = enemy.get("ai_profile", {})
    style = str(profile.get("style") or enemy.get("role") or "balanced")
    name = str(enemy.get("name") or "敌人")

    if ratio <= 0.25 and profile.get("can_retreat", True):
        return {"action": "retreat_or_guard", "name": "退守", "skill": {"name": "退守", "power": 0.0}, "message": f"{name}气息不稳，转为退守，试图拉开距离。"}
    if style in {"aggressive", "beast"} or round_no % 3 == 0:
        return {"action": "heavy_attack", "name": "强攻", "skill": {"name": "强攻", "power": 1.2, "accuracy_modifier": -0.05, "crit_modifier": 0.02}, "message": f"{name}抓住空隙强攻。"}
    if style in {"cautious", "defensive"} and ratio < 0.6:
        return {"action": "guard", "name": "防守", "skill": {"name": "防守", "power": 0.0}, "message": f"{name}不再冒进，先稳住架势。"}
    if player_stats.get("hp", 0) <= player_stats.get("max_hp", 100) * 0.35:
        return {"action": "press", "name": "压制", "skill": {"name": "压制", "power": 1.05, "accuracy_modifier": 0.02, "crit_modifier": 0.0}, "message": f"{name}看出你状态下滑，试图压制。"}
    return {"action": "attack", "name": "反击", "skill": {"name": "反击", "power": 1.0, "accuracy_modifier": 0.0, "crit_modifier": 0.0}, "message": f"{name}立刻反击。"}
