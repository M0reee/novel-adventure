#!/usr/bin/env python3
from __future__ import annotations

from typing import Any


def matching_arc(state: dict[str, Any], player_input: str) -> dict[str, Any] | None:
    text = str(player_input or "")
    for quest in state.get("active_quests", []):
        if not isinstance(quest, dict) or quest.get("status") != "active":
            continue
        if quest.get("source") != "story_arcs.json" and not quest.get("story_arc_id"):
            continue
        name = str(quest.get("name", ""))
        terms = [name, *[str(term) for term in quest.get("key_terms", []) if term]]
        objectives = [str(obj.get("text", "")) for obj in quest.get("objectives", []) if isinstance(obj, dict)]
        if any(term and term in text for term in [*terms, *objectives]):
            return quest
    return None


def advance_arc_attention(state: dict[str, Any], player_input: str, resolution: dict[str, Any]) -> list[str]:
    arc = matching_arc(state, player_input)
    if not arc:
        return []
    runtime = state.setdefault("runtime", {})
    arcs = runtime.setdefault("story_arcs", {})
    name = str(arc.get("name") or arc.get("story_arc_id"))
    row = arcs.setdefault(
        name,
        {
            "name": name,
            "attention": 0,
            "stage_notes": [],
            "last_turn": None,
            "status": "tracked",
        },
    )
    turn = int(state.get("meta", {}).get("turn", 0))
    delta = 10 if resolution.get("status") in {"allowed", "resolved"} else 3
    row["attention"] = min(100, int(row.get("attention", 0)) + delta)
    row["last_turn"] = turn
    row.setdefault("stage_notes", []).append(
        {
            "turn": turn,
            "action": str(player_input)[:100],
            "result": str(resolution.get("verdict", ""))[:80],
        }
    )
    row["stage_notes"] = row["stage_notes"][-8:]
    return [f"长期线索关注度：{name} -> {row['attention']}%"]


def arc_state_lines(state: dict[str, Any]) -> list[str]:
    rows = state.get("runtime", {}).get("story_arcs", {})
    if not rows:
        return []
    lines = []
    for name, row in list(rows.items())[:4]:
        lines.append(f"- {name}：关注度 {row.get('attention', 0)}%，最近回合 {row.get('last_turn')}")
    return lines
