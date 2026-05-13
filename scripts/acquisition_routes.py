#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from typing import Any

from common import load_manifest, read_json, save_manifest, world_dir, write_json


def route_id(kind: str, name: str) -> str:
    return f"route_{kind}_{hashlib.sha1(name.encode('utf-8')).hexdigest()[:10]}"


def step(step_id: str, title: str, check: str, result: str) -> dict[str, str]:
    return {"step_id": step_id, "title": title, "check": check, "result": result}


def skill_route(node: dict[str, Any]) -> dict[str, Any]:
    name = str(node.get("name") or "")
    gate = node.get("canon_gate", {})
    source_type = str(gate.get("source_type") or "unknown")
    return {
        "route_id": route_id("skill", name),
        "target_type": "skill",
        "target": name,
        "state": "locked_until_source",
        "canon_gate": gate,
        "steps": [
            step("discover", "确认技能存在", "必须来自检索 canon、NPC 口述、卷轴、传承或事件线索。", "只获得 rumor/source_known，不写入技能栏。"),
            step("source", "获得来源或许可", f"需要 source_type={source_type} 对应的导师、卷轴、势力资格、血脉或自创条件。", "进入 source_acquired。"),
            step("train", "训练到可用", "需要安全地点、时间、资源和失败代价裁定。", "runtime.skill_progress 达到 100%。"),
            step("verify", "实战或低风险验证", "第一次使用必须按能力边界结算消耗和失败风险。", "写入 player.skills。"),
        ],
        "ooc_policy": gate.get("ooc_policy", "出现于原著不等于玩家已掌握。"),
    }


def item_route(item: dict[str, Any]) -> dict[str, Any]:
    name = str(item.get("name") or "")
    return {
        "route_id": route_id("item", name),
        "target_type": "item",
        "target": name,
        "state": "not_owned",
        "canon_gate": {
            "canon_status": "confirmed" if item.get("canon_summary") else "inferred",
            "acquisition_required": True,
            "numeric_source": "item_market_playable",
        },
        "steps": [
            step("locate", "确认来源", "读取 item_market、NPC 线索、地点资源或任务奖励。", "获得来源情报。"),
            step("verify", "验真与适配", "检查可靠性、使用条件、境界/身份/风险。", "确认是否适合当前玩家。"),
            step("acquire", "购买、交换、任务或探索获得", "必须支付货币、人情、风险或完成条件。", "写入 inventory。"),
            step("use", "使用或装备", "通过 inventory_runtime 结算效果。", "写入 active_effects/equipment 或消耗。"),
        ],
        "ooc_policy": "物品存在不等于市场有货；剧情限定物品不能被普通购买绕过。",
    }


def location_route(location: dict[str, Any]) -> dict[str, Any]:
    name = str(location.get("name") or "")
    return {
        "route_id": route_id("location", name),
        "target_type": "location",
        "target": name,
        "state": "unknown_or_unreached",
        "canon_gate": {
            "canon_status": "confirmed",
            "acquisition_required": True,
            "numeric_source": "location_runtime_playable",
        },
        "steps": [
            step("clue", "获得地点线索", "通过 NPC、地图、任务、事件或传闻发现入口。", "地点进入 known。"),
            step("access", "满足进入条件", "检查身份、路线、风险、时间窗口和敌对势力。", "地点进入 accessible。"),
            step("prepare", "准备撤退和资源", "高风险地点必须准备补给、队友、护法或退路。", "降低失败后果。"),
            step("enter", "进入并触发现场状态", "写入 current_location 和 location flags。", "进入可探索状态。"),
        ],
        "ooc_policy": "知道地点名字不等于能瞬移进入；必须有路线、权限或风险承受能力。",
    }


def build_acquisition_routes(world: str) -> dict[str, Any]:
    wdir = world_dir(world)
    skill_tree = read_json(wdir / "skill_tree.json", {})
    market = read_json(wdir / "item_market.json", {})
    scene_graph = read_json(wdir / "scene_graph.json", {})
    routes = []
    routes.extend(skill_route(node) for node in skill_tree.get("nodes", []) if node.get("name"))
    routes.extend(item_route(item) for item in market.get("items", []) if item.get("name"))
    routes.extend(location_route(location) for location in scene_graph.get("locations", []) if location.get("name"))
    output = {
        "world": world,
        "policy": "Acquisition routes explain how a player may canon-safely gain skills, items, and location access. They are gates, not grants.",
        "routes": routes,
    }
    write_json(wdir / "acquisition_routes.json", output)
    manifest = load_manifest(wdir, world)
    manifest["acquisition_routes"] = "acquisition_routes.json"
    save_manifest(wdir, manifest)
    print(f"Built acquisition_routes.json routes={len(routes)}")
    return output


def load_acquisition_routes(world: str) -> dict[str, Any]:
    data = read_json(world_dir(world) / "acquisition_routes.json", {})
    return data if data else build_acquisition_routes(world)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build canon-safe acquisition routes.")
    parser.add_argument("--world", required=True)
    parser.add_argument("--rebuild", action="store_true")
    args = parser.parse_args()
    data = build_acquisition_routes(args.world) if args.rebuild else load_acquisition_routes(args.world)
    print(json.dumps(data, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
