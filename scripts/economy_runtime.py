#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from copy import deepcopy
from typing import Any

from common import load_manifest, read_json, save_manifest, world_dir, write_json


def default_stock(rarity: str) -> int:
    return {
        "common": 8,
        "uncommon": 5,
        "rare": 2,
        "epic": 1,
        "legendary": 0,
        "mythic": 0,
    }.get(rarity, 3)


def build_economy_state(world: str) -> dict[str, Any]:
    wdir = world_dir(world)
    market = read_json(wdir / "item_market.json", {})
    items = []
    for item in market.get("items", []):
        name = str(item.get("name", ""))
        rarity = str(item.get("rarity", "common"))
        items.append(
            {
                "item_id": item.get("item_id"),
                "name": name,
                "rarity": rarity,
                "stock": default_stock(rarity),
                "price_modifier": 1.0,
                "reliability": "unknown" if rarity in {"rare", "epic", "legendary", "mythic"} else "ordinary",
                "last_checked_turn": None,
                "flags": [],
            }
        )
    output = {
        "world": world,
        "policy": "Runtime economy tracks stock, price modifiers and reliability hints. It modifies playable prices but does not override canon.",
        "items": items,
        "market_events": [],
    }
    write_json(wdir / "economy_state.json", output)
    manifest = load_manifest(wdir, world)
    manifest["economy_state"] = "economy_state.json"
    save_manifest(wdir, manifest)
    print(f"Built economy_state.json items={len(items)}")
    return output


def load_economy_state(world: str) -> dict[str, Any]:
    data = read_json(world_dir(world) / "economy_state.json", {})
    return data if data else build_economy_state(world)


def apply_economy_state_to_market(world: str, market: dict[str, Any]) -> dict[str, Any]:
    state = load_economy_state(world)
    rows = {str(item.get("name")): item for item in state.get("items", [])}
    output = deepcopy(market)
    for item in output.get("items", []):
        runtime = rows.get(str(item.get("name", "")))
        if not runtime:
            continue
        modifier = float(runtime.get("price_modifier", 1.0))
        low, high = item.get("price_range", [0, 0])
        item["runtime"] = {
            "stock": runtime.get("stock", 0),
            "reliability": runtime.get("reliability", "unknown"),
            "price_modifier": modifier,
            "flags": runtime.get("flags", []),
        }
        if int(low) > 0 and int(high) > 0:
            item["effective_price_range"] = [max(1, int(round(int(low) * modifier))), max(1, int(round(int(high) * modifier)))]
    return output


def record_market_check(world: str, item_name: str, turn: int | None = None) -> dict[str, Any]:
    data = load_economy_state(world)
    for item in data.get("items", []):
        if item.get("name") == item_name:
            item["last_checked_turn"] = turn
            if "checked" not in item.setdefault("flags", []):
                item["flags"].append("checked")
            break
    write_json(world_dir(world) / "economy_state.json", data)
    return data


def record_purchase(world: str, item_name: str, turn: int | None = None) -> dict[str, Any]:
    data = load_economy_state(world)
    for item in data.get("items", []):
        if item.get("name") == item_name:
            item["stock"] = max(0, int(item.get("stock", 0)) - 1)
            if int(item.get("stock", 0)) <= 1:
                item["price_modifier"] = min(2.0, float(item.get("price_modifier", 1.0)) + 0.15)
            item["last_checked_turn"] = turn
            data.setdefault("market_events", []).append({"turn": turn, "type": "purchase", "item": item_name})
            data["market_events"] = data["market_events"][-30:]
            break
    write_json(world_dir(world) / "economy_state.json", data)
    return data


def main() -> None:
    parser = argparse.ArgumentParser(description="Build or inspect runtime economy state.")
    parser.add_argument("--world", required=True)
    parser.add_argument("--rebuild", action="store_true")
    args = parser.parse_args()
    data = build_economy_state(args.world) if args.rebuild else load_economy_state(args.world)
    print(json.dumps(data, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
