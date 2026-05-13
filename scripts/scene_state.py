#!/usr/bin/env python3
from __future__ import annotations

from typing import Any


def scene_key(location: str) -> str:
    return str(location or "当前位置").strip() or "当前位置"


def ensure_scene_record(state: dict[str, Any], scene: dict[str, Any]) -> dict[str, Any]:
    runtime = state.setdefault("runtime", {})
    scenes = runtime.setdefault("scenes", {})
    key = scene_key(scene.get("location", "当前位置"))
    turn = int(state.get("meta", {}).get("turn", 0))
    record = scenes.setdefault(
        key,
        {
            "location": key,
            "first_seen_turn": turn,
            "visits": 0,
            "risk": scene.get("risk", "medium"),
            "known_npcs": {},
            "known_resources": {},
            "known_hooks": {},
            "flags": {},
            "log": [],
        },
    )
    record["risk"] = scene.get("risk", record.get("risk", "medium"))
    for npc in scene.get("npcs", []):
        name = str(npc.get("name", ""))
        if name:
            record.setdefault("known_npcs", {}).setdefault(
                name,
                {
                    "name": name,
                    "status": "present_or_reachable",
                    "last_interaction_turn": None,
                    "memory": [],
                },
            )
    for resource in scene.get("resources", []):
        name = str(resource.get("name", ""))
        if name:
            record.setdefault("known_resources", {}).setdefault(
                name,
                {"name": name, "status": "rumored", "checked": False, "notes": []},
            )
    for hook in scene.get("hooks", []):
        name = str(hook.get("name", ""))
        if name:
            record.setdefault("known_hooks", {}).setdefault(
                name,
                {"name": name, "status": "available", "progress": 0, "notes": []},
            )
    return record


def find_scene_target(scene: dict[str, Any], player_input: str, bucket: str, *, allow_fallback: bool = True) -> str:
    for item in scene.get(bucket, []):
        name = str(item.get("name", ""))
        if name and name in player_input:
            return name
    if allow_fallback and scene.get(bucket):
        return str(scene.get(bucket, [{}])[0].get("name", ""))
    return ""


def advance_scene_state(
    state: dict[str, Any],
    scene: dict[str, Any],
    player_input: str,
    resolution: dict[str, Any],
    intent: dict[str, Any],
) -> list[str]:
    record = ensure_scene_record(state, scene)
    turn = int(state.get("meta", {}).get("turn", 0))
    record["visits"] = int(record.get("visits", 0)) + 1
    messages = [f"场景访问：{record['location']} 第 {record['visits']} 次"]
    kind = str(resolution.get("kind") or intent.get("kind") or "")
    status = str(resolution.get("status") or "")
    player_input = str(player_input or "")

    if kind == "social":
        target = str(intent.get("target") or find_scene_target(scene, player_input, "npcs"))
        if target:
            npc = record.setdefault("known_npcs", {}).setdefault(target, {"name": target, "status": "present_or_reachable", "memory": []})
            npc["last_interaction_turn"] = turn
            npc.setdefault("memory", []).append(
                {
                    "turn": turn,
                    "action": player_input[:80],
                    "status": status,
                    "result": str(resolution.get("verdict", ""))[:80],
                }
            )
            npc["memory"] = npc["memory"][-8:]
            messages.append(f"NPC记忆：{target} 记住了这次互动。")

    if kind in {"info", "trade", "social"}:
        resource = find_scene_target(scene, player_input, "resources", allow_fallback=False)
        if resource:
            row = record.setdefault("known_resources", {}).setdefault(resource, {"name": resource, "status": "rumored", "checked": False, "notes": []})
            row["checked"] = True
            row["status"] = "source_investigated" if kind != "trade" else "price_checked"
            row.setdefault("notes", []).append(f"第 {turn} 回合打听过来源/风险")
            row["notes"] = row["notes"][-6:]
            messages.append(f"资源情报：{resource} 来源和风险已记录。")
        elif kind == "info":
            record.setdefault("flags", {})["surveyed"] = True
            messages.append("场景情报：已观察风险、出口和可互动对象。")

    if kind == "quest" or "机会" in player_input or "入口" in player_input:
        hook = str(intent.get("target") or find_scene_target(scene, player_input, "hooks", allow_fallback=False))
        if hook:
            row = record.setdefault("known_hooks", {}).setdefault(hook, {"name": hook, "status": "available", "progress": 0, "notes": []})
            row["progress"] = min(100, int(row.get("progress", 0)) + (25 if status in {"resolved", "allowed"} else 10))
            row.setdefault("notes", []).append(f"第 {turn} 回合推进：{player_input[:60]}")
            row["notes"] = row["notes"][-6:]
            messages.append(f"机会进度：{hook} -> {row['progress']}%")

    record.setdefault("log", []).append({"turn": turn, "kind": kind, "status": status, "action": player_input[:100]})
    record["log"] = record["log"][-12:]
    return messages


def scene_state_lines(state: dict[str, Any], scene: dict[str, Any]) -> list[str]:
    runtime = state.get("runtime", {})
    record = runtime.get("scenes", {}).get(scene_key(scene.get("location", "当前位置")), {})
    if not record:
        return ["- 当前场景尚未形成持久状态。"]
    lines = [f"- 访问次数：{record.get('visits', 0)}"]
    npcs = [
        f"{name}（记忆 {len(row.get('memory', []))}）"
        for name, row in record.get("known_npcs", {}).items()
        if row.get("memory")
    ]
    if npcs:
        lines.append(f"- 有互动记忆的 NPC：{'、'.join(npcs[:4])}")
    resources = [
        name
        for name, row in record.get("known_resources", {}).items()
        if row.get("checked")
    ]
    if resources:
        lines.append(f"- 已调查资源：{'、'.join(resources[:4])}")
    hooks = [
        f"{name} {row.get('progress', 0)}%"
        for name, row in record.get("known_hooks", {}).items()
        if int(row.get("progress", 0)) > 0
    ]
    if hooks:
        lines.append(f"- 机会进度：{'、'.join(hooks[:3])}")
    return lines
