#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from typing import Any

from common import read_json, world_dir
from location_runtime import risk_level


BAD_NAMES = {
    "不会",
    "没有理会",
    "这种等级",
    "听得药",
    "当前",
    "对方",
    "什么",
    "卷轴",
    "不知",
    "方才",
    "缓缓地",
    "所以",
    "那一",
    "轻声",
    "低声",
    "淡淡地",
    "沉声",
    "家族",
    "空间",
    "外界",
    "如果",
}
NPC_HINTS = ("管事", "伙计", "摊主", "守卫", "少年", "导师", "炼药师", "商人", "佣兵", "长老", "弟子")
RESOURCE_HINTS = ("药", "丹", "魔核", "金币", "斗技", "功法", "材料", "草", "花", "灵液", "情报")
LOCATION_HINTS = ("城", "镇", "村", "山", "谷", "域", "界", "院", "场", "坊", "市", "楼", "阁", "塔", "殿", "府", "宫", "学院", "公会", "拍卖", "山脉", "沙漠")


def clean_text(value: Any, limit: int = 120) -> str:
    text = " ".join(str(value or "").replace("\n", " ").split()).strip(" ，。；")
    if not text:
        return ""
    return text[:limit].rstrip("，。； ")


def good_name(name: Any, max_len: int = 14) -> bool:
    text = str(name or "").strip()
    if not text or text in BAD_NAMES:
        return False
    if text.startswith(("这", "那", "此", "该", "某")):
        return False
    if len(text) > max_len:
        return False
    if any(mark in text for mark in ("。", "，", "；", "：", "！", "？", "\n", "\"", "'")):
        return False
    return any("\u4e00" <= ch <= "\u9fff" for ch in text)


def add_unique(rows: list[dict[str, Any]], item: dict[str, Any], key: str = "name", limit: int = 5) -> None:
    name = str(item.get(key, ""))
    if not name:
        return
    for row in rows:
        existing = str(row.get(key, ""))
        if existing == name or existing in name or name in existing:
            return
    if not name:
        return
    rows.append(item)
    del rows[limit:]


def parse_seed(seed: str, kind: str) -> dict[str, Any] | None:
    if "：" in seed:
        name, note = seed.split("：", 1)
    elif ":" in seed:
        name, note = seed.split(":", 1)
    else:
        name, note = seed, ""
    name = name.strip()
    if not good_name(name, 18):
        return None
    return {"name": name, "kind": kind, "note": clean_text(note, 120), "source": "opening"}


def load_opening(world: str) -> dict[str, Any]:
    return read_json(world_dir(world) / "opening.json", {})


def load_scene_graph(world: str) -> dict[str, Any]:
    return read_json(world_dir(world) / "scene_graph.json", {})


def load_relationship_names(world: str) -> list[dict[str, Any]]:
    rules = read_json(world_dir(world) / "relationship_rules.json", {})
    rows: list[dict[str, Any]] = []
    for item in rules.get("npcs", []):
        name = item.get("name")
        if good_name(name) and (any(hint in str(name) for hint in NPC_HINTS) or len(str(name)) <= 4):
            rows.append({"name": str(name), "kind": "npc", "note": clean_text(item.get("notes", ""), 100), "source": "relationship_rules"})
    return rows


def canon_scene_candidates(canon_rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    npcs: list[dict[str, Any]] = []
    locations: list[dict[str, Any]] = []
    resources: list[dict[str, Any]] = []
    hooks: list[dict[str, Any]] = []
    for row in canon_rows:
        row_type = str(row.get("type", ""))
        name = str(row.get("name", "")).strip()
        if not good_name(name, 16):
            continue
        note = clean_text(row.get("claim") or row.get("summary"), 120)
        item = {"name": name, "kind": row_type, "note": note, "source": "retrieval"}
        if row_type in {"npc", "npc_motive"} or "npc" in row_type:
            add_unique(npcs, item, limit=4)
        elif row_type == "location" or "location" in row_type or any(hint in name for hint in LOCATION_HINTS):
            add_unique(locations, item, limit=4)
        elif row_type in {"item", "technique", "playable_item"} or any(hint in name for hint in RESOURCE_HINTS):
            add_unique(resources, item, limit=4)
        elif "hook" in row_type or "story_arc" in row_type or "event_chain" in row_type:
            add_unique(hooks, item, limit=3)
    return {"npcs": npcs, "locations": locations, "resources": resources, "hooks": hooks}


def opening_scene_candidates(world: str, state: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    opening = load_opening(world)
    bg = opening.get("player_background", {})
    incident = bg.get("opening_incident", {})
    current_location = str(state.get("meta", {}).get("current_location", ""))
    starting_location = str(opening.get("starting_location", ""))
    near_opening = bool(starting_location and (current_location in starting_location or starting_location in current_location))
    npcs: list[dict[str, Any]] = []
    hooks: list[dict[str, Any]] = []
    if near_opening:
        for seed in incident.get("visible_npcs", []):
            parsed = parse_seed(str(seed), "npc")
            if parsed:
                add_unique(npcs, parsed, limit=5)
        for seed in bg.get("relationship_seeds", []):
            parsed = parse_seed(str(seed), "npc")
            if parsed:
                add_unique(npcs, parsed, limit=5)
        first_goal = clean_text(incident.get("first_goal"), 140)
        pressure = clean_text(incident.get("pressure_clock"), 120)
        if first_goal:
            hooks.append({"name": "眼前机会", "kind": "opportunity", "note": first_goal, "source": "opening"})
        if pressure:
            hooks.append({"name": "时间压力", "kind": "pressure", "note": pressure, "source": "opening"})
    return {"npcs": npcs, "hooks": hooks, "locations": [], "resources": []}


def current_scene(world: str, state: dict[str, Any], canon_rows: list[dict[str, Any]]) -> dict[str, Any]:
    meta = state.get("meta", {})
    location = str(meta.get("current_location") or "当前位置")
    graph = load_scene_graph(world)
    opening_candidates = opening_scene_candidates(world, state)
    canon_candidates = canon_scene_candidates(canon_rows)
    npcs = []
    locations = []
    resources = []
    hooks = []
    graph_candidates = graph_scene_candidates(graph, location)
    for source in (opening_candidates, graph_candidates, canon_candidates):
        for item in source.get("npcs", []):
            add_unique(npcs, item, limit=5)
        for item in source.get("locations", []):
            add_unique(locations, item, limit=4)
        for item in source.get("resources", []):
            add_unique(resources, item, limit=4)
        for item in source.get("hooks", []):
            add_unique(hooks, item, limit=4)

    if not npcs:
        for item in load_relationship_names(world):
            add_unique(npcs, item, limit=3)

    scene_risk = risk_level(location, " ".join(item.get("note", "") for item in locations + hooks))
    return {
        "location": location,
        "risk": scene_risk,
        "npcs": npcs,
        "locations": locations,
        "resources": resources,
        "hooks": hooks,
    }


def graph_scene_candidates(graph: dict[str, Any], location: str) -> dict[str, list[dict[str, Any]]]:
    if not graph:
        return {"npcs": [], "locations": [], "resources": [], "hooks": []}

    locations = [
        normalize_graph_node(row)
        for row in graph.get("locations", [])
        if good_name(row.get("name"), 24)
    ]
    primary_location = next(
        (
            row
            for row in locations
            if str(row.get("name")) in location or location in str(row.get("name"))
        ),
        locations[0] if locations else None,
    )
    result = {
        "locations": [primary_location] if primary_location else [],
        "npcs": [normalize_graph_node(row) for row in graph.get("npcs", [])[:5] if good_name(row.get("name"), 18)],
        "resources": [normalize_graph_node(row) for row in graph.get("resources", [])[:4] if good_name(row.get("name"), 16)],
        "hooks": [normalize_graph_node(row) for row in graph.get("hooks", [])[:4] if good_name(row.get("name"), 16)],
    }
    return result


def normalize_graph_node(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": str(row.get("name", "")),
        "kind": str(row.get("kind", "")),
        "note": clean_text(row.get("summary"), 140),
        "source": str(row.get("source", "scene_graph")),
    }


def scene_lines(scene: dict[str, Any]) -> list[str]:
    lines = [f"- 地点：{scene.get('location', '当前位置')}（风险：{scene.get('risk', 'medium')}）"]
    if scene.get("npcs"):
        names = "、".join(item["name"] for item in scene["npcs"][:4])
        lines.append(f"- 可互动人物：{names}")
    if scene.get("resources"):
        names = "、".join(item["name"] for item in scene["resources"][:4])
        lines.append(f"- 可打听资源：{names}")
    if scene.get("hooks"):
        hook = scene["hooks"][0]
        lines.append(f"- 当前机会：{hook.get('name')}：{hook.get('note')}")
    if scene.get("locations"):
        names = "、".join(item["name"] for item in scene["locations"][:3])
        lines.append(f"- 地点线索：{names}")
    return lines


def scene_options(scene: dict[str, Any], state: dict[str, Any]) -> list[str]:
    location = scene.get("location", "当前位置")
    options: list[str] = []
    if scene.get("npcs"):
        npc = scene["npcs"][0]
        options.append(f"找「{npc['name']}」搭话，问清规矩、机会或代价。")
    if scene.get("hooks"):
        hook = scene["hooks"][0]
        note = clean_text(hook.get("note"), 42) or "确认入口和风险"
        if hook.get("name") == "眼前机会":
            note = "确认旁听、杂务名额或药材账单线索的入口和代价"
        options.append(f"围绕「{hook['name']}」行动：{note}。")
    if scene.get("resources"):
        resource = scene["resources"][0]
        options.append(f"打听「{resource['name']}」的来源、价格和真假风险。")
    options.extend(
        [
            f"观察{location}的动静，确认风险、出口和可用人物。",
            "进行一次低风险训练或休整，检查当前状态能否承受修炼。",
            "清点背包、金币和关系，决定买卖、修炼还是换情报。",
        ]
    )
    if scene.get("locations"):
        dest = scene["locations"][0]
        options.append(f"转向与「{dest['name']}」相关的地点线索。")
    deduped: list[str] = []
    for option in options:
        if option and option not in deduped:
            deduped.append(option)
        if len(deduped) >= 5:
            break
    return deduped


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect the scene generated for a world/save.")
    parser.add_argument("--world", required=True)
    parser.add_argument("--state", default="player_state.json")
    args = parser.parse_args()
    state = read_json(world_dir(args.world) / args.state, {})
    scene = current_scene(args.world, state, [])
    print(json.dumps(scene, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
