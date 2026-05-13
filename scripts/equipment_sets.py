#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from typing import Any

from common import load_manifest, read_json, save_manifest, world_dir, write_json
from rpg_profile import load_rpg_profile


WEAPON_WORDS = ("剑", "刀", "枪", "尺", "棍", "杖", "弓", "刃", "武器")
ARMOR_WORDS = ("甲", "衣", "袍", "盾", "护", "防具")
ACCESSORY_WORDS = ("戒", "符", "令牌", "坠", "环", "骨", "模块", "插件", "封印物")
BAD_ITEM_NAMES = {"卷轴", "丹药", "药材", "一些药", "两种丹药", "四品炼药", "传出药", "其纳戒", "当筑基灵液", "第一瓶筑基灵液"}
COMBO_WORDS = ("套装", "成套", "组合", "共鸣", "联动", "五件", "组件", "阵眼", "魂骨套装", "模块联动")


def stable_id(prefix: str, name: str) -> str:
    digest = hashlib.sha1(name.encode("utf-8")).hexdigest()[:10]
    return f"{prefix}_{digest}"


def infer_slot(name: str, summary: str) -> str:
    if any(word in name for word in WEAPON_WORDS):
        return "weapon"
    if any(word in name for word in ARMOR_WORDS):
        return "armor"
    if any(word in name for word in ACCESSORY_WORDS):
        return "accessory"
    return "special"


def valid_item(name: str) -> bool:
    if not name or len(name) > 14:
        return False
    if name in BAD_ITEM_NAMES or name.startswith(("这", "那", "其", "当", "第一", "一瓶", "七瓶")):
        return False
    return not any(mark in name for mark in ("。", "，", "；", "：", "\n", "听得", "什么"))


def combo_supported(*texts: str) -> bool:
    joined = " ".join(texts)
    return any(word in joined for word in COMBO_WORDS)


def gate(enabled: bool, reason: str, source: str = "items.json") -> dict[str, Any]:
    return {
        "enabled": enabled,
        "canon_status": "confirmed" if enabled else "inferred_disabled",
        "canon_confidence": "high" if enabled else "low",
        "playable_confidence": "medium" if enabled else "low",
        "source": source,
        "numeric_source": "canon_supported_playable" if enabled else "disabled_no_canon_support",
        "ooc_policy": reason,
    }


def build_equipment_sets(world: str) -> dict[str, Any]:
    wdir = world_dir(world)
    profile = load_rpg_profile(world)
    items = read_json(wdir / "items.json", {}).get("items", [])
    candidates: list[dict[str, Any]] = []
    for item in items:
        name = str(item.get("name", "")).strip()
        summary = str(item.get("summary") or item.get("claim") or "")
        if not valid_item(name):
            continue
        slot = infer_slot(name, summary)
        if slot in {"weapon", "armor", "accessory"}:
            candidates.append({"item_id": item.get("item_id") or stable_id("item", name), "name": name, "slot": slot, "summary": summary})

    starter_name = f"入门{profile.get('systems', {}).get('equipment_name', '装备')}组合"
    starter_equipment = profile.get("starter_kit", {}).get("equipment", {})
    starter_required = {
        slot: item.get("name")
        for slot, item in starter_equipment.items()
        if isinstance(item, dict) and item.get("name")
    } or {"weapon": "旧练习木棍", "armor": "粗布衣"}
    sets = [
        {
            "set_id": "starter_training_set",
            "name": starter_name,
            "enabled": False,
            "canon_gate": gate(False, "起步装备已经各自提供基础属性；没有原著证据时不额外启用套装加成。", "starter_equipment"),
            "required_slots": starter_required,
            "piece_count": len(starter_required),
            "bonuses": {"attack": 1, "defense": 1},
            "notes": "默认起步组合仅作为 UI/结构展示，默认不启用额外属性。",
            "source": "starter_equipment",
        }
    ]

    by_slot: dict[str, list[dict[str, Any]]] = {"weapon": [], "armor": [], "accessory": []}
    for item in candidates:
        by_slot.setdefault(item["slot"], []).append(item)
    if by_slot["weapon"] and by_slot["armor"]:
        weapon = by_slot["weapon"][0]
        armor = by_slot["armor"][0]
        set_name = f"{weapon['name']}与{armor['name']}"
        enabled = combo_supported(weapon.get("summary", ""), armor.get("summary", ""))
        sets.append(
            {
                "set_id": stable_id("set", set_name),
                "name": set_name,
                "enabled": enabled,
                "canon_gate": gate(enabled, "只有原文明确支持成套、共鸣、组合或模块联动时才启用数值加成。"),
                "required_slots": {"weapon": weapon["name"], "armor": armor["name"]},
                "piece_count": 2,
                "bonuses": {"attack": 2, "defense": 1},
                "notes": "从原著物品名推导的潜在装备协同；未启用时不进入属性计算。",
                "source": "items.json",
            }
        )
    if by_slot["accessory"]:
        accessory = by_slot["accessory"][0]
        enabled = combo_supported(accessory.get("summary", ""))
        sets.append(
            {
                "set_id": stable_id("set", accessory["name"]),
                "name": f"{accessory['name']}专精",
                "enabled": enabled,
                "canon_gate": gate(enabled, "单件器物只有在原文明确说明特殊加成、共鸣或代价时才启用数值效果。"),
                "required_slots": {"accessory": accessory["name"]},
                "piece_count": 1,
                "bonuses": {"damage_reduction": 0.02},
                "notes": "特殊器物潜在效果；默认不把储物、身份或剧情用途转成战斗加成。",
                "source": "items.json",
            }
        )

    output = {
        "world": world,
        "policy": "Equipment sets are derived from distilled items and starter equipment. Bonuses are structured playable parameters and can be overridden by canon patches.",
        "equipment_name": profile.get("systems", {}).get("equipment_name", "装备"),
        "sets": sets,
    }
    write_json(wdir / "equipment_sets.json", output)
    manifest = load_manifest(wdir, world)
    manifest["equipment_sets"] = "equipment_sets.json"
    save_manifest(wdir, manifest)
    print(f"Built equipment_sets.json sets={len(sets)}")
    return output


def load_equipment_sets(world: str) -> dict[str, Any]:
    data = read_json(world_dir(world) / "equipment_sets.json", {})
    return data if data else build_equipment_sets(world)


def equipped_names(player: dict[str, Any]) -> dict[str, str]:
    equipment = player.get("equipment", {})
    if not isinstance(equipment, dict):
        return {}
    return {slot: str(item.get("name", "")) for slot, item in equipment.items() if isinstance(item, dict)}


def active_set_bonuses(world: str, player: dict[str, Any]) -> list[dict[str, Any]]:
    data = load_equipment_sets(world)
    names = equipped_names(player)
    bonuses: list[dict[str, Any]] = []
    for row in data.get("sets", []):
        required = row.get("required_slots", {})
        if not row.get("enabled", False):
            continue
        if required and all(names.get(slot) == required_name for slot, required_name in required.items()):
            bonuses.append({"set_id": row.get("set_id"), "name": row.get("name"), "modifiers": row.get("bonuses", {}), "notes": row.get("notes", "")})
    return bonuses


def refresh_player_set_bonuses(world: str, state: dict[str, Any]) -> list[str]:
    player = state.setdefault("player", {})
    bonuses = active_set_bonuses(world, player)
    player["equipment_set_bonuses"] = bonuses
    return [f"套装生效：{row.get('name')}" for row in bonuses]


def main() -> None:
    parser = argparse.ArgumentParser(description="Build or inspect canon-derived equipment sets.")
    parser.add_argument("--world", required=True)
    parser.add_argument("--rebuild", action="store_true")
    args = parser.parse_args()
    data = build_equipment_sets(args.world) if args.rebuild else load_equipment_sets(args.world)
    print(json.dumps(data, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
