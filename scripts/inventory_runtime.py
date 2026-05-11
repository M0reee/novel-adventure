#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from typing import Any

from common import read_json, write_json, world_dir
from economy import load_market


USE_WORDS = ("使用", "服用", "炼化", "吞服")
EQUIP_WORDS = ("装备", "佩戴", "穿戴", "换上")


def find_inventory_item(player: dict[str, Any], player_input: str) -> tuple[int, dict[str, Any]] | None:
    for idx, item in enumerate(player.get("inventory", [])):
        if isinstance(item, dict) and item.get("name") and item["name"] in player_input:
            return idx, item
    return None


def market_details(world: str, item_name: str) -> dict[str, Any]:
    market = load_market(world)
    return next((item for item in market.get("items", []) if item.get("name") == item_name), {})


def use_item(world: str, state: dict[str, Any], player_input: str) -> dict[str, Any] | None:
    if not any(word in player_input for word in USE_WORDS):
        return None
    player = state.setdefault("player", {})
    found = find_inventory_item(player, player_input)
    if not found:
        return {
            "kind": "inventory",
            "status": "blocked",
            "verdict": "物品不在行囊",
            "consequence": "你不能使用尚未拥有的物品；先确认来源、购买、炼制或任务奖励。",
            "state_changes": [],
            "options": ["查看行囊。", "寻找该物品的获取路径。", "改用已有资源。"],
        }
    idx, item = found
    details = market_details(world, item.get("name", ""))
    effect = details.get("use_effect") or item.get("use_effect")
    if not effect:
        return {
            "kind": "inventory",
            "status": "conditional",
            "verdict": "缺少可执行使用效果",
            "consequence": f"「{item.get('name')}」没有结构化使用效果；只能确认用途，不能凭空产生数值变化。",
            "state_changes": [],
            "options": ["询问正确用途。", "寻找炼药师或导师确认。", "暂时保留该物品。"],
        }
    player.setdefault("active_effects", []).append(effect)
    del player.setdefault("inventory", [])[idx]
    return {
        "kind": "inventory",
        "status": "resolved",
        "verdict": "物品已使用",
        "consequence": f"你使用「{item.get('name')}」，获得状态「{effect.get('name', effect.get('effect_id', '效果'))}」。",
        "state_changes": [f"行囊移除：{item.get('name')}", f"状态新增：{effect.get('name', effect.get('effect_id', '效果'))}"],
        "options": ["查看当前状态效果。", "继续修炼。", "寻找更多同类资源。"],
    }


def equip_item(state: dict[str, Any], player_input: str) -> dict[str, Any] | None:
    if not any(word in player_input for word in EQUIP_WORDS):
        return None
    player = state.setdefault("player", {})
    found = find_inventory_item(player, player_input)
    if not found:
        return {
            "kind": "inventory",
            "status": "blocked",
            "verdict": "装备不在行囊",
            "consequence": "你不能装备尚未拥有的物品。",
            "state_changes": [],
            "options": ["查看行囊。", "寻找该装备。", "使用当前装备。"],
        }
    idx, item = found
    slot = item.get("slot", "special")
    before = player.setdefault("equipment", {}).get(slot)
    player["equipment"][slot] = item
    del player.setdefault("inventory", [])[idx]
    if before:
        player["inventory"].append(before)
    return {
        "kind": "inventory",
        "status": "resolved",
        "verdict": "装备已更换",
        "consequence": f"你将「{item.get('name')}」装备到「{slot}」。",
        "state_changes": [f"装备槽 {slot} 更新为：{item.get('name')}"],
        "options": ["查看最终属性。", "测试新装备。", "继续探索。"],
    }


def resolve_inventory_action(world: str, state: dict[str, Any], player_input: str) -> dict[str, Any] | None:
    return use_item(world, state, player_input) or equip_item(state, player_input)


def main() -> None:
    parser = argparse.ArgumentParser(description="Use or equip an inventory item from player_state.json.")
    parser.add_argument("--world", required=True)
    parser.add_argument("--input", required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    path = world_dir(args.world) / "player_state.json"
    state = read_json(path, {})
    result = resolve_inventory_action(args.world, state, args.input)
    if result and not args.dry_run:
        write_json(path, state)
    print(json.dumps(result or {"status": "noop"}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
