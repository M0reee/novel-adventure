#!/usr/bin/env python3
from __future__ import annotations

from typing import Any

from canon_evidence import evidence_rows


def ensure_runtime_layers(state: dict[str, Any]) -> dict[str, Any]:
    runtime = state.setdefault("runtime", {})
    layers = runtime.setdefault(
        "layers",
        {
            "policy": "Separate canon evidence, derived playable rules, player-confirmed facts, rumors, and rulings to avoid treating rumors or templates as canon.",
            "canon_evidence": [],
            "derived_rules": [],
            "confirmed_facts": [],
            "rumors": [],
            "rulings": [],
        },
    )
    for key in ("canon_evidence", "derived_rules", "confirmed_facts", "rumors", "rulings"):
        layers.setdefault(key, [])
    return layers


def append_unique(rows: list[dict[str, Any]], row: dict[str, Any], key: str, limit: int) -> None:
    value = row.get(key)
    if value and any(existing.get(key) == value for existing in rows):
        return
    rows.append(row)
    del rows[:-limit]


def record_runtime_layers(
    state: dict[str, Any],
    canon_rows: list[dict[str, Any]],
    resolution: dict[str, Any],
    turn: int,
    player_input: str,
) -> list[str]:
    layers = ensure_runtime_layers(state)
    for row in evidence_rows(canon_rows, 8):
        row["turn"] = turn
        append_unique(layers["canon_evidence"], row, "id", 40)

    for row in canon_rows[:12]:
        row_type = str(row.get("type") or "")
        if row_type.startswith("playable_") or row_type in {"ability_boundary", "event_chain", "story_arc"}:
            append_unique(
                layers["derived_rules"],
                {
                    "id": row.get("id"),
                    "turn": turn,
                    "type": row_type,
                    "name": row.get("name"),
                    "source": row.get("source_json"),
                },
                "id",
                40,
            )

    status = str(resolution.get("status") or "")
    layers["rulings"].append(
        {
            "turn": turn,
            "action": player_input[:100],
            "kind": resolution.get("kind"),
            "status": status,
            "verdict": resolution.get("verdict"),
        }
    )
    layers["rulings"] = layers["rulings"][-40:]

    if status in {"resolved", "allowed"}:
        layers["confirmed_facts"].append({"turn": turn, "action": player_input[:100], "result": str(resolution.get("verdict", ""))[:100]})
        layers["confirmed_facts"] = layers["confirmed_facts"][-40:]
    elif status in {"conditional", "partial_or_blocked"}:
        layers["rumors"].append({"turn": turn, "action": player_input[:100], "note": str(resolution.get("verdict", ""))[:100]})
        layers["rumors"] = layers["rumors"][-40:]

    return [
        f"运行层更新：canon={len(layers['canon_evidence'])} derived={len(layers['derived_rules'])} confirmed={len(layers['confirmed_facts'])} rumors={len(layers['rumors'])}"
    ]


def runtime_layer_lines(state: dict[str, Any]) -> list[str]:
    layers = ensure_runtime_layers(state)
    return [
        f"- canon证据：{len(layers.get('canon_evidence', []))} 条",
        f"- 可玩推导：{len(layers.get('derived_rules', []))} 条",
        f"- 已确认事实：{len(layers.get('confirmed_facts', []))} 条",
        f"- 未证实传闻/条件：{len(layers.get('rumors', []))} 条",
    ]
