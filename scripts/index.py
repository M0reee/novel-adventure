#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path
from typing import Any

from common import read_json, read_jsonl, world_dir


CANON_FILES = [
    "world_bible.json",
    "power_system.json",
    "factions.json",
    "locations.json",
    "npcs.json",
    "items.json",
    "techniques.json",
    "timeline.json",
    "game_rules.json",
    "adventure_hooks.json",
    "playable_canon.json",
    "npc_motives.json",
    "ability_boundaries.json",
    "foreshadowing.json",
    "event_chains.json",
    "story_arcs.json",
]

BAD_ACTION_NAMES = {
    "炼药",
    "炼丹",
    "修炼",
    "突破",
    "拍卖",
    "交易",
    "试炼",
    "争夺",
    "追杀",
    "线索",
    "任务",
    "目标",
    "继续",
}


def compact_parts(parts: list[Any], limit: int = 900) -> str:
    cleaned: list[str] = []
    for part in parts:
        if isinstance(part, list):
            values = part
        else:
            values = [part]
        for value in values:
            text = " ".join(str(value or "").split())
            if not text or len(text) > 180:
                continue
            if any(noise in text for noise in ("['", "']", "{", "}", "目光", "脸色", "手掌", "微微", "笑道")):
                continue
            if text not in cleaned:
                cleaned.append(text)
    return " ".join(cleaned)[:limit]


def infer_type(source: str, path: str) -> str:
    if source == "playable_canon.json":
        return "playable_canon"
    if source == "npc_motives.json":
        return "npc_motive"
    if source == "ability_boundaries.json":
        return "ability_boundary"
    if source == "foreshadowing.json":
        return "foreshadowing"
    if source == "event_chains.json":
        return "event_chain"
    if source == "story_arcs.json":
        return "story_arc"
    checks = [
        ("world_laws", "world_law"),
        ("style_signals", "style_signal"),
        ("realms", "power_realm"),
        ("cultivation_rules", "cultivation_rule"),
        ("factions", "faction"),
        ("locations", "location"),
        ("npcs", "npc"),
        ("items", "item"),
        ("techniques", "technique"),
        ("events", "event"),
        ("hooks", "playable_hook"),
    ]
    for marker, ftype in checks:
        if marker in path:
            return ftype
    if source == "game_rules.json":
        return "game_rule"
    return Path(source).stem


def flatten_json(data: Any, source: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    def visit(node: Any, path: str) -> None:
        if isinstance(node, dict):
            if source == "playable_canon.json" and "name" in node and "play_rule" in node:
                if (
                    node.get("source_type") in {"playable_hook", "item"}
                    and str(node.get("name") or "") in BAD_ACTION_NAMES
                ):
                    return
                if (
                    node.get("source_type") == "playable_hook"
                    and float(node.get("source_quality") or 0) < 0.7
                    and any(noise in str(node.get("summary") or "") for noise in ("目光", "脸色", "手掌", "微微", "笑道"))
                ):
                    return
                claim = " ".join(
                    str(part)
                    for part in [
                        node.get("summary", ""),
                        node.get("play_rule", ""),
                        " ".join(node.get("entry_conditions", [])),
                        " ".join(node.get("risks", [])),
                        " ".join(node.get("rewards", [])),
                    ]
                    if part
                )[:700]
                rows.append(
                    {
                        "id": f"{source}:{path}:{node.get('name')}",
                        "type": f"playable_{node.get('type', 'canon')}",
                        "name": node.get("name", ""),
                        "claim": claim,
                        "aliases": "",
                        "evidence": node.get("source_type", ""),
                        "source_json": source,
                        "quality": float(node.get("source_quality", 0.8)),
                        "score": float(node.get("source_score", 0.0)),
                    }
                )
            elif source == "npc_motives.json" and "npc" in node:
                claim = compact_parts(
                    [
                        f"公开目标：{node.get('public_goal', '')}",
                        f"隐藏目标：{node.get('private_goal', '')}",
                        [f"担忧：{item}" for item in node.get("fears", [])[:2]],
                        [f"筹码：{item}" for item in node.get("leverage", [])[:3]],
                        [f"底线：{item}" for item in node.get("boundaries", [])[:3]],
                        [f"互动入口：{item}" for item in node.get("player_hooks", [])[:3]],
                    ],
                    900,
                )[:800]
                rows.append(
                    {
                        "id": f"{source}:{path}:{node.get('npc')}",
                        "type": "npc_motive",
                        "name": node.get("npc", ""),
                        "claim": claim,
                        "aliases": "",
                        "evidence": node.get("evidence", ""),
                        "source_json": source,
                        "quality": float(node.get("confidence", 0.7)),
                        "score": 380.0 if node.get("source") == "llm_aggregated" else 300.0,
                    }
                )
            elif source == "ability_boundaries.json" and "ability_id" in node:
                if str(node.get("name") or "") in BAD_ACTION_NAMES:
                    return
                claim = " ".join(
                    str(part)
                    for part in [
                        " ".join(node.get("can_do", [])),
                        " ".join(node.get("cannot_do", [])),
                        " ".join(node.get("costs", [])),
                        " ".join(node.get("risks", [])),
                        " ".join(node.get("requirements", [])),
                        node.get("scaling", ""),
                    ]
                    if part
                )[:900]
                rows.append(
                    {
                        "id": node.get("ability_id"),
                        "type": "ability_boundary",
                        "name": node.get("name", ""),
                        "claim": claim,
                        "aliases": node.get("type", ""),
                        "evidence": node.get("evidence", ""),
                        "source_json": source,
                        "quality": float(node.get("confidence", 0.7)),
                        "score": 320.0,
                    }
                )
            elif source == "foreshadowing.json" and "foreshadow_id" in node:
                claim = " ".join(
                    str(part)
                    for part in [
                        node.get("surface_clue", ""),
                        " ".join(node.get("reveal_conditions", [])),
                        " ".join(node.get("payoff", [])),
                        node.get("spoiler_level", ""),
                    ]
                    if part
                )[:700]
                rows.append(
                    {
                        "id": node.get("foreshadow_id"),
                        "type": "foreshadowing",
                        "name": " ".join(node.get("related_entities", [])) or node.get("surface_clue", ""),
                        "claim": claim,
                        "aliases": "",
                        "evidence": node.get("evidence", ""),
                        "source_json": source,
                        "quality": float(node.get("confidence", 0.65)),
                        "score": 260.0,
                    }
                )
            elif source == "event_chains.json" and "chain_id" in node:
                node_text = []
                for chain_node in node.get("nodes", []):
                    if isinstance(chain_node, dict):
                        node_text.append(" ".join(str(value) for value in chain_node.values() if not isinstance(value, (list, dict))))
                        for key in ("if_player_intervenes", "if_ignored", "effects"):
                            value = chain_node.get(key)
                            if isinstance(value, list):
                                node_text.extend(str(item) for item in value)
                rows.append(
                    {
                        "id": node.get("chain_id"),
                        "type": "event_chain",
                        "name": node.get("name", ""),
                        "claim": " ".join(node_text)[:900],
                        "aliases": node.get("type", ""),
                        "evidence": node.get("evidence", ""),
                        "source_json": source,
                        "quality": float(node.get("confidence", 0.68)),
                        "score": 280.0,
                    }
                )
            elif source == "story_arcs.json" and "arc_id" in node:
                claim = compact_parts(
                    [
                        node.get("summary", ""),
                        node.get("why_it_matters", []),
                        node.get("entry_conditions", []),
                        node.get("progression_loops", []),
                        node.get("risks", []),
                        node.get("rewards", []),
                    ],
                    700,
                )
                rows.append(
                    {
                        "id": node.get("arc_id"),
                        "type": "story_arc",
                        "name": node.get("name", ""),
                        "claim": claim,
                        "aliases": node.get("type", ""),
                        "evidence": " ".join(node.get("evidence_chunk_ids", [])),
                        "source_json": source,
                        "quality": float(node.get("confidence", 0.68)),
                        "score": 520.0 if int(node.get("source_priority") or 0) >= 5 else 340.0 if node.get("canon_strength") == "high" else 300.0,
                    }
                )
            elif "name" in node and ("summary" in node or "claims" in node):
                inferred = infer_type(source, path)
                if inferred in {"item", "playable_hook"} and str(node.get("name") or "") in BAD_ACTION_NAMES:
                    return
                claim = str(node.get("summary", ""))[:520]
                rows.append(
                    {
                        "id": f"{source}:{path}:{node.get('name')}",
                        "type": inferred,
                        "name": node.get("name", ""),
                        "claim": claim,
                        "aliases": " ".join(node.get("aliases", [])),
                        "evidence": " ".join(node.get("evidence_chunk_ids", [])),
                        "source_json": source,
                        "quality": float(node.get("quality", 0.5)),
                        "score": float(node.get("score", 0.0)),
                    }
                )
            for key, value in node.items():
                visit(value, f"{path}.{key}" if path else key)
        elif isinstance(node, list):
            for idx, value in enumerate(node):
                visit(value, f"{path}.{idx}")

    visit(data, "")
    return rows


def add_patch_rows(wdir: Path) -> list[dict[str, Any]]:
    rows = []
    for patch in read_jsonl(wdir / "canon_patches.jsonl"):
        rows.append(
            {
                "id": patch.get("patch_id", f"patch:{len(rows)}"),
                "type": "canon_patch",
                "name": patch.get("target", "canon_patch"),
                "claim": patch.get("rule", ""),
                "aliases": patch.get("priority", ""),
                "evidence": patch.get("reason", ""),
                "source_json": "canon_patches.jsonl",
                "quality": 1.0,
                "score": 999.0,
            }
        )
    return rows


def build_index(world: str) -> None:
    wdir = world_dir(world)
    rows: list[dict[str, Any]] = []
    for filename in CANON_FILES:
        path = wdir / filename
        if path.exists():
            rows.extend(flatten_json(read_json(path, {}), filename))
    rows.extend(add_patch_rows(wdir))

    db_path = wdir / "retrieval.sqlite"
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("DROP TABLE IF EXISTS canon")
        conn.execute("DROP TABLE IF EXISTS canon_fts")
        conn.execute(
            """
            CREATE TABLE canon (
                id TEXT PRIMARY KEY,
                type TEXT,
                name TEXT,
                claim TEXT,
                aliases TEXT,
                evidence TEXT,
                source_json TEXT,
                quality REAL,
                score REAL,
                search_text TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE VIRTUAL TABLE canon_fts USING fts5(
                id, type, name, claim, aliases, search_text,
                tokenize='unicode61'
            )
            """
        )
        for row in rows:
            search_text = " ".join(str(row.get(key, "")) for key in ("type", "name", "claim", "aliases", "evidence", "source_json"))
            values = (
                row["id"],
                row["type"],
                row["name"],
                row["claim"],
                row["aliases"],
                row["evidence"],
                row["source_json"],
                row["quality"],
                row["score"],
                search_text,
            )
            conn.execute("INSERT OR REPLACE INTO canon VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", values)
            conn.execute("INSERT INTO canon_fts VALUES (?, ?, ?, ?, ?, ?)", values[:5] + (search_text,))
        conn.commit()
    finally:
        conn.close()
    print(f"Indexed {len(rows)} canon row(s) into {db_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build SQLite FTS retrieval index.")
    parser.add_argument("--world", required=True)
    args = parser.parse_args()
    build_index(args.world)


if __name__ == "__main__":
    main()
