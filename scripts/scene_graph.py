#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from typing import Any

from common import DOUPO_FACTIONS, DOUPO_LOCATIONS, DOUPO_NPCS, DOUPO_REALMS, load_manifest, read_json, save_manifest, world_dir, write_json
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
    "沉吟",
    "喃喃",
    "喃喃道",
    "冷笑",
    "苦笑",
    "微笑",
    "摇头",
    "点头",
    "急忙",
    "旋即一",
    "嘿嘿",
    "刚欲",
    "开口",
    "挥手",
    "不得不",
    "他知",
    "不管如何",
    "也不知",
    "萧炎苦",
    "低声喃喃",
    "戏谑",
    "我知",
    "笑吟吟地",
    "萧炎低",
    "那无数",
    "大声",
    "安慰",
    "柔声",
    "些无奈地",
    "对于他来",
    "萧炎冷",
    "你知",
    "心中喃喃",
    "你难",
    "谁都知",
    "未听",
    "谁知",
    "没听",
    "虽然不知",
    "旋即几",
    "才知",
    "还不知",
    "你应该知",
    "萧炎皱眉",
    "间传出一",
    "你也知",
    "任由那",
    "萧炎干",
    "薰儿轻声",
    "低声骂",
    "虽然知",
    "雅妃微",
    "苏长老",
    "萧炎追",
    "雅妃嫣然",
    "心头嘀咕",
    "药老叹",
    "心中自语",
    "自然不知",
    "入空间通",
    "我怎么知",
    "萧战苦",
    "萧玉叹",
    "严狮沉声",
    "古河怒吼",
    "如果",
    "外界",
    "空间",
    "家族",
    "也不会",
}

LOCATION_HINTS = ("城", "镇", "村", "山", "谷", "域", "界", "院", "宗", "场", "坊", "市", "楼", "阁", "塔", "殿", "府", "宫", "沙漠", "山脉")
NPC_HINTS = ("管事", "伙计", "摊主", "守卫", "少年", "少女", "导师", "炼药师", "商人", "佣兵", "长老", "弟子", "族长")
RESOURCE_HINTS = ("丹", "药", "草", "花", "魔核", "功法", "斗技", "金币", "纳戒", "异火", "灵液", "材料", "情报")
FACTION_HINTS = ("家", "族", "宗", "门", "阁", "殿", "盟", "会", "学院", "帝国", "公会", "佣兵团")


def clean_text(value: Any, limit: int = 180) -> str:
    text = " ".join(str(value or "").replace("\n", " ").split()).strip(" ，。；")
    if not text:
        return ""
    return text[:limit].rstrip("，。； ")


def is_sentence_fragment(name: str) -> bool:
    return any(mark in name for mark in ("。", "，", "；", "：", "！", "？", "\n", "\"", "'"))


def good_name(name: Any, max_len: int = 16) -> bool:
    text = str(name or "").strip()
    if not text or text in BAD_NAMES:
        return False
    if text.startswith(("这", "那", "此", "该", "某")):
        return False
    if len(text) > max_len or is_sentence_fragment(text):
        return False
    return any("\u4e00" <= ch <= "\u9fff" for ch in text)


def entity_score(row: dict[str, Any], expected: str) -> float:
    name = str(row.get("name", "")).strip()
    summary = clean_text(row.get("summary") or row.get("claim"), 240)
    if not good_name(name):
        return -100.0
    score = float(row.get("score") or 0) / 100.0
    score += float(row.get("quality") or 0)
    score += min(float(row.get("mentions") or 0), 100) / 80.0
    if expected == "location" and any(hint in name for hint in LOCATION_HINTS):
        score += 2.0
    if expected == "npc" and (any(hint in name for hint in NPC_HINTS) or len(name) <= 4):
        score += 1.5
    if expected == "faction" and any(hint in name for hint in FACTION_HINTS):
        score += 2.0
    if expected == "resource" and any(hint in name for hint in RESOURCE_HINTS):
        score += 2.0
    if summary and len(summary) < 35:
        score -= 0.5
    if summary and summary[:1] in "，。；：":
        score -= 1.0
    return score


def profile_known_names(world: str) -> dict[str, set[str]]:
    manifest = load_manifest(world_dir(world), world)
    profile = str(manifest.get("profile") or "")
    if profile == "doupo" or "doupo" in world:
        return {
            "location": set(DOUPO_LOCATIONS),
            "npc": set(DOUPO_NPCS),
            "faction": set(DOUPO_FACTIONS),
        }
    return {"location": set(), "npc": set(), "faction": set()}


def add_node(nodes: list[dict[str, Any]], node: dict[str, Any], limit: int) -> None:
    name = str(node.get("name", ""))
    for existing in nodes:
        other = str(existing.get("name", ""))
        if other == name or other in name or name in other:
            if float(node.get("score", 0)) > float(existing.get("score", 0)):
                existing.update(node)
            return
    nodes.append(node)
    nodes.sort(key=lambda item: float(item.get("score", 0)), reverse=True)
    del nodes[limit:]


def node_from_entity(row: dict[str, Any], kind: str, known: dict[str, set[str]]) -> dict[str, Any] | None:
    score = entity_score(row, kind)
    name = str(row.get("name", "")).strip()
    if kind == "location" and name not in known.get("location", set()) and not any(hint in name for hint in LOCATION_HINTS):
        return None
    if kind == "faction" and name not in known.get("faction", set()) and not any(hint in name for hint in FACTION_HINTS):
        return None
    if kind == "faction" and name in set(DOUPO_REALMS):
        return None
    if kind == "npc" and known.get("npc") and name not in known["npc"] and not any(hint in name for hint in NPC_HINTS):
        return None
    if name in known.get(kind, set()):
        score += 3.0
    if score < 1.0:
        return None
    summary = clean_text(row.get("summary") or row.get("claim"), 180)
    node = {
        "id": f"{kind}:{name}",
        "name": name,
        "kind": kind,
        "summary": summary,
        "score": round(score, 3),
        "source": "distilled_entity",
    }
    if kind == "location":
        node["risk"] = risk_level(name, summary)
        node["actions"] = ["观察局势", "寻找 NPC", "打听资源", "确认出口"]
    if kind == "npc":
        node["relationship_target"] = name
        node["actions"] = ["搭话", "询问规矩", "提出交换", "打听传闻"]
    if kind == "resource":
        node["actions"] = ["询价", "确认真假", "寻找来源", "评估用途"]
    return node


def opening_nodes(world: str) -> dict[str, list[dict[str, Any]]]:
    opening = read_json(world_dir(world) / "opening.json", {})
    bg = opening.get("player_background", {})
    incident = bg.get("opening_incident", {})
    locations: list[dict[str, Any]] = []
    npcs: list[dict[str, Any]] = []
    hooks: list[dict[str, Any]] = []
    starting = str(opening.get("starting_location") or "")
    if starting:
        add_node(
            locations,
            {
                "id": f"location:{starting}",
                "name": starting,
                "kind": "location",
                "summary": clean_text(bg.get("opening_scene"), 180),
                "risk": risk_level(starting, str(bg.get("opening_scene", ""))),
                "actions": ["观察局势", "寻找 NPC", "打听资源", "确认出口"],
                "score": 10.0,
                "source": "opening",
            },
            8,
        )
    for seed in [*incident.get("visible_npcs", []), *bg.get("relationship_seeds", [])]:
        text = str(seed)
        name, _, note = text.partition("：")
        if good_name(name, 18):
            add_node(
                npcs,
                {
                    "id": f"npc:{name}",
                    "name": name,
                    "kind": "npc",
                    "summary": clean_text(note, 160),
                    "relationship_target": name,
                    "actions": ["搭话", "询问规矩", "提出交换", "打听传闻"],
                    "score": 9.0,
                    "source": "opening",
                },
                12,
            )
    first_goal = clean_text(incident.get("first_goal"), 180)
    if first_goal:
        hooks.append(
            {
                "id": "hook:opening_opportunity",
                "name": "眼前机会",
                "kind": "hook",
                "summary": first_goal,
                "actions": ["确认入口", "评估代价", "选择低风险切入点"],
                "score": 10.0,
                "source": "opening",
            }
        )
    return {"locations": locations, "npcs": npcs, "hooks": hooks, "resources": [], "factions": []}


def playable_nodes(world: str) -> dict[str, list[dict[str, Any]]]:
    data = read_json(world_dir(world) / "playable_canon.json", {})
    resources: list[dict[str, Any]] = []
    hooks: list[dict[str, Any]] = []
    for row in data.get("entries", []):
        name = str(row.get("name", ""))
        kind = str(row.get("type", ""))
        summary = clean_text(row.get("summary"), 160)
        if not good_name(name):
            continue
        if kind in {"item", "technique", "power_realm", "cultivation_rule", "playable_item", "playable_technique"}:
            add_node(
                resources,
                {
                    "id": f"resource:{name}",
                    "name": name,
                    "kind": "resource",
                    "summary": summary,
                    "actions": ["确认来源", "询价", "评估用途", "检查风险"],
                    "score": 4.0,
                    "source": "playable_canon",
                },
                20,
            )
        elif "hook" in kind or "arc" in kind:
            add_node(
                hooks,
                {
                    "id": f"hook:{name}",
                    "name": name,
                    "kind": "hook",
                    "summary": summary,
                    "actions": ["确认入口", "打听相关人物", "评估风险"],
                    "score": 3.0,
                    "source": "playable_canon",
                },
                12,
            )
    return {"resources": resources, "hooks": hooks, "locations": [], "npcs": [], "factions": []}


def link_scene_graph(graph: dict[str, Any]) -> list[dict[str, Any]]:
    links: list[dict[str, Any]] = []
    locations = graph.get("locations", [])
    npcs = graph.get("npcs", [])
    resources = graph.get("resources", [])
    hooks = graph.get("hooks", [])
    if locations:
        primary = locations[0]["id"]
        for npc in npcs[:6]:
            links.append({"from": primary, "to": npc["id"], "type": "present_or_reachable"})
        for resource in resources[:6]:
            links.append({"from": primary, "to": resource["id"], "type": "can_ask_about"})
        for hook in hooks[:4]:
            links.append({"from": primary, "to": hook["id"], "type": "opportunity"})
    return links


def build_scene_graph(world: str) -> dict[str, Any]:
    wdir = world_dir(world)
    known = profile_known_names(world)
    graph: dict[str, Any] = {
        "world": world,
        "policy": "Scene graph is a cleaned, playable projection of distilled canon. Runtime scene generation should prefer this over raw entity files.",
        "locations": [],
        "npcs": [],
        "factions": [],
        "resources": [],
        "hooks": [],
        "links": [],
    }

    for source in (opening_nodes(world), playable_nodes(world)):
        for key in ("locations", "npcs", "factions", "resources", "hooks"):
            for node in source.get(key, []):
                add_node(graph[key], node, {"locations": 24, "npcs": 32, "factions": 24, "resources": 32, "hooks": 24}[key])

    for filename, key, kind, limit in [
        ("locations.json", "locations", "location", 24),
        ("npcs.json", "npcs", "npc", 32),
        ("factions.json", "factions", "faction", 24),
    ]:
        for row in read_json(wdir / filename, {}).get(key, []):
            node = node_from_entity(row, kind, known)
            if node:
                add_node(graph[key], node, limit)

    for row in read_json(wdir / "adventure_hooks.json", {}).get("hooks", []):
        name = str(row.get("name", ""))
        if not good_name(name):
            continue
        add_node(
            graph["hooks"],
            {
                "id": f"hook:{name}",
                "name": name,
                "kind": "hook",
                "summary": clean_text(row.get("summary") or row.get("claim"), 180),
                "actions": ["确认入口", "打听相关人物", "评估风险"],
                "score": max(2.0, entity_score(row, "resource")),
                "source": "adventure_hooks",
            },
            24,
        )

    graph["links"] = link_scene_graph(graph)
    write_json(wdir / "scene_graph.json", graph)
    manifest = load_manifest(wdir, world)
    manifest["scene_graph"] = "scene_graph.json"
    save_manifest(wdir, manifest)
    print(
        "Built scene_graph.json "
        f"locations={len(graph['locations'])} npcs={len(graph['npcs'])} "
        f"resources={len(graph['resources'])} hooks={len(graph['hooks'])}"
    )
    return graph


def main() -> None:
    parser = argparse.ArgumentParser(description="Build cleaned scene graph for runtime scene generation.")
    parser.add_argument("--world", required=True)
    args = parser.parse_args()
    print(json.dumps(build_scene_graph(args.world), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
