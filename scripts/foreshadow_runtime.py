#!/usr/bin/env python3
from __future__ import annotations

from typing import Any

from common import read_json, world_dir


INVESTIGATION_WORDS = ("追问", "调查", "打听", "观察", "询问", "为什么", "秘密", "真相", "过去", "线索")
REVEAL_WORDS = ("信任", "坦白", "承认", "揭开", "真相", "告诉")


def _relationship_score(state: dict[str, Any], targets: list[str]) -> int:
    relationships = state.get("relationships", [])
    for row in relationships:
        if row.get("target") in targets:
            return int(row.get("score", 0) or 0)
    return 0


def relevant_foreshadows(world: str, player_input: str, canon_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    seen = set()
    for row in canon_rows:
        if row.get("type") != "foreshadowing":
            continue
        row_id = row.get("id")
        if row_id and row_id not in seen:
            rows.append(row)
            seen.add(row_id)
    direct = read_json(world_dir(world) / "foreshadowing.json", {}).get("foreshadows", [])
    for item in direct:
        related = [str(name) for name in item.get("related_entities", []) if str(name)]
        haystack = " ".join([str(item.get("surface_clue", "")), str(item.get("evidence", "")), *related])
        if not any(term and term in player_input for term in related) and not any(term and term in haystack for term in player_input.split()):
            continue
        row_id = item.get("foreshadow_id")
        if row_id in seen:
            continue
        rows.append(
            {
                "id": row_id,
                "type": "foreshadowing",
                "name": "、".join(related) or item.get("surface_clue", "伏笔线索"),
                "claim": item.get("surface_clue", ""),
                "source_json": "foreshadowing.json",
            }
        )
        seen.add(row_id)
    return rows[:3]


def advance_foreshadows(
    world: str,
    state: dict[str, Any],
    player_input: str,
    canon_rows: list[dict[str, Any]],
) -> tuple[list[str], list[str]]:
    if not any(word in player_input for word in INVESTIGATION_WORDS):
        return [], []

    messages: list[str] = []
    options: list[str] = []
    discovered = state.setdefault("discovered_foreshadows", [])
    by_id = {row.get("foreshadow_id") or row.get("id"): row for row in discovered}

    for row in relevant_foreshadows(world, player_input, canon_rows):
        row_id = str(row.get("id") or row.get("name") or "foreshadow")
        name = str(row.get("name") or "伏笔线索")
        clue = str(row.get("claim") or "").split(" hidden_truth")[0][:120]
        record = by_id.get(row_id)
        if not record:
            record = {
                "foreshadow_id": row_id,
                "name": name,
                "stage": "clue_seen",
                "seen_clues": [],
                "revealed": False,
            }
            discovered.append(record)
            by_id[row_id] = record
        if clue and clue not in record.setdefault("seen_clues", []):
            record["seen_clues"].append(clue)
            record["seen_clues"] = record["seen_clues"][-5:]
            messages.append(f"伏笔线索：你注意到「{name}」相关异常，但当前只确认表层线索。")
            options.append(f"继续追查「{name}」的来龙去脉。")

        score = _relationship_score(state, [name])
        wants_reveal = any(word in player_input for word in REVEAL_WORDS)
        if wants_reveal and score >= 25 and not record.get("revealed"):
            record["stage"] = "revealed"
            record["revealed"] = True
            messages.append(f"伏笔推进：「{name}」的隐藏信息开始浮出水面，但仍以已检索 canon 为边界。")
        elif wants_reveal and not record.get("revealed"):
            messages.append(f"伏笔未揭示：「{name}」还缺少信任、证据、地点或事件推进，不能直接剧透。")
            options.append("先建立关系、寻找证据或推进相关事件。")

    return messages[:4], options[:3]
