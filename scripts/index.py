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
    "timeline.json",
    "game_rules.json",
    "adventure_hooks.json",
]


def infer_type(source: str, path: str) -> str:
    if "world_laws" in path:
        return "world_law"
    if "style_signals" in path:
        return "style_signal"
    if "realms" in path:
        return "power_realm"
    if "cultivation_rules" in path:
        return "cultivation_rule"
    if "factions" in path:
        return "faction"
    if "locations" in path:
        return "location"
    if "npcs" in path:
        return "npc"
    if "events" in path:
        return "event"
    if "hooks" in path:
        return "playable_hook"
    if source == "game_rules.json":
        return "game_rule"
    return Path(source).stem


def flatten_json(data: Any, source: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    def visit(node: Any, path: str) -> None:
        if isinstance(node, dict):
            if "name" in node and ("summary" in node or "claims" in node):
                claim = node.get("summary", "")
                if node.get("claims"):
                    claim = " ".join(claim_item.get("claim", "") for claim_item in node["claims"][:4]) or claim
                rows.append(
                    {
                        "id": f"{source}:{path}:{node.get('name')}",
                        "type": infer_type(source, path),
                        "name": node.get("name", ""),
                        "claim": claim,
                        "aliases": " ".join(node.get("aliases", [])),
                        "evidence": " ".join(node.get("evidence_chunk_ids", [])),
                        "source_json": source,
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
            search_text = " ".join(
                str(row.get(key, "")) for key in ("type", "name", "claim", "aliases", "evidence", "source_json")
            )
            values = (
                row["id"],
                row["type"],
                row["name"],
                row["claim"],
                row["aliases"],
                row["evidence"],
                row["source_json"],
                search_text,
            )
            conn.execute("INSERT OR REPLACE INTO canon VALUES (?, ?, ?, ?, ?, ?, ?, ?)", values)
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
