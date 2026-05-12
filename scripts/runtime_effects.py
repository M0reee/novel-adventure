#!/usr/bin/env python3
from __future__ import annotations

from typing import Any

from common import read_json, world_dir, write_json


def apply_effects(world: str, state: dict[str, Any], effects: list[dict[str, Any]], reason: str, dry_run: bool = False) -> list[str]:
    messages: list[str] = []
    for effect in effects:
        etype = effect.get("type")
        if etype == "relationship":
            messages.extend(apply_relationship_effect(state, effect, reason))
        elif etype == "market":
            messages.extend(apply_market_effect(world, effect, reason, dry_run))
        elif etype == "location":
            messages.extend(apply_location_effect(world, effect, reason, dry_run))
        elif etype == "state":
            messages.extend(apply_state_effect(state, effect, reason))
        elif etype == "create_event":
            messages.append("生成后续世界事件。")
    return messages


def apply_relationship_effect(state: dict[str, Any], effect: dict[str, Any], reason: str) -> list[str]:
    target = str(effect.get("target", "")).strip()
    if not target:
        return []
    delta = int(effect.get("delta", 0))
    relationships = state.setdefault("relationships", [])
    row = next((item for item in relationships if item.get("target") == target), None)
    if not row:
        row = {"target": target, "score": 0, "bucket": "neutral", "notes": []}
        relationships.append(row)
    before = int(row.get("score", 0))
    after = max(-100, min(100, before + delta))
    row["score"] = after
    row["bucket"] = "hostile" if after <= -50 else "wary" if after < -10 else "trusted" if after >= 60 else "friendly" if after >= 25 else "neutral"
    row.setdefault("notes", []).append(reason)
    row["notes"] = row["notes"][-10:]
    return [f"{target}关系：{before} -> {after}（{row['bucket']}）"]


def apply_market_effect(world: str, effect: dict[str, Any], reason: str, dry_run: bool = False) -> list[str]:
    wdir = world_dir(world)
    path = wdir / "item_market.json"
    market = read_json(path, {})
    if not market:
        return []
    item_name = str(effect.get("item", "")).strip()
    multiplier = float(effect.get("price_multiplier", 1.0))
    availability = effect.get("availability")
    messages: list[str] = []
    for item in market.get("items", []):
        if item_name and item.get("name") != item_name:
            continue
        if multiplier != 1.0 and item.get("price_range"):
            before = list(item["price_range"])
            item["price_range"] = [max(0, int(round(value * multiplier))) for value in before]
            messages.append(f"{item.get('name')}价格：{before} -> {item['price_range']}")
        if availability:
            item["availability"] = availability
            messages.append(f"{item.get('name')}供应状态：{availability}")
        item.setdefault("runtime_notes", []).append(reason)
    if messages and not dry_run:
        write_json(path, market)
    return messages


def apply_location_effect(world: str, effect: dict[str, Any], reason: str, dry_run: bool = False) -> list[str]:
    wdir = world_dir(world)
    path = wdir / "location_runtime.json"
    data = read_json(path, {})
    if not data:
        return []
    location_name = str(effect.get("location", "")).strip()
    messages: list[str] = []
    for location in data.get("locations", []):
        if location_name and location.get("name") != location_name:
            continue
        if effect.get("risk_level"):
            before = location.get("risk_level")
            location["risk_level"] = effect["risk_level"]
            messages.append(f"{location.get('name')}风险：{before} -> {location['risk_level']}")
        for action in effect.get("add_actions", []):
            location.setdefault("available_actions", [])
            if action not in location["available_actions"]:
                location["available_actions"].append(action)
                messages.append(f"{location.get('name')}新增行动：{action}")
        location.setdefault("runtime_notes", []).append(reason)
    if messages and not dry_run:
        write_json(path, data)
    return messages


def apply_state_effect(state: dict[str, Any], effect: dict[str, Any], reason: str) -> list[str]:
    meta = state.setdefault("meta", {})
    world_flags = meta.setdefault("world_flags", {})
    key = str(effect.get("key", "")).strip()
    if not key:
        return []
    before = world_flags.get(key)
    world_flags[key] = effect.get("value", True)
    return [f"世界标记 {key}：{before} -> {world_flags[key]}（{reason}）"]
