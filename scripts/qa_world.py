#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path
from typing import Any

from common import read_json, read_jsonl, world_dir


REQUIRED_FILES = [
    "manifest.json",
    "chunks.jsonl",
    "facts.jsonl",
    "world_bible.json",
    "power_system.json",
    "factions.json",
    "locations.json",
    "npcs.json",
    "game_rules.json",
    "playable_canon.json",
    "retrieval.sqlite",
]


def count_index_rows(path: Path) -> int:
    if not path.exists():
        return 0
    conn = sqlite3.connect(path)
    try:
        return int(conn.execute("SELECT count(*) FROM canon").fetchone()[0])
    finally:
        conn.close()


def long_summary_count(entries: list[dict[str, Any]], limit: int = 260) -> int:
    return sum(1 for row in entries if len(str(row.get("summary") or row.get("claim") or "")) > limit)


def status(ok: bool) -> str:
    return "OK" if ok else "WARN"


def qa(world: str) -> None:
    wdir = world_dir(world)
    manifest = read_json(wdir / "manifest.json", {})
    quality = read_json(wdir / "quality_report.json", {})
    playable = read_json(wdir / "playable_canon.json", {})
    curated = read_jsonl(wdir / "curated_facts.jsonl")
    index_rows = count_index_rows(wdir / "retrieval.sqlite")
    missing = [filename for filename in REQUIRED_FILES if not (wdir / filename).exists()]
    entity_counts = quality.get("entity_counts", {})
    playable_entries = playable.get("entries", [])

    checks = [
        ("required_files", not missing, f"missing={missing}" if missing else "all present"),
        ("chunks", int(manifest.get("chunk_count", 0)) > 0, str(manifest.get("chunk_count", 0))),
        ("facts", int(manifest.get("fact_count", 0)) > 0, str(manifest.get("fact_count", 0))),
        ("curated_facts", len(curated) >= 30, str(len(curated))),
        ("playable_canon", len(playable_entries) >= 30, str(len(playable_entries))),
        ("retrieval_index", index_rows >= len(curated), str(index_rows)),
        ("long_summaries", long_summary_count(playable_entries) <= max(5, len(playable_entries) // 10), str(long_summary_count(playable_entries))),
        ("locations", int(entity_counts.get("location", 0)) >= 5, str(entity_counts.get("location", 0))),
        ("npcs", int(entity_counts.get("npc", 0)) >= 5, str(entity_counts.get("npc", 0))),
    ]

    print(f"World QA: {world}")
    print(f"profile={manifest.get('profile')} genre={manifest.get('genre', 'unknown')}")
    for name, ok, detail in checks:
        print(f"[{status(ok)}] {name}: {detail}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run deterministic quality checks for a distilled world.")
    parser.add_argument("--world", required=True)
    args = parser.parse_args()
    qa(args.world)


if __name__ == "__main__":
    main()
