#!/usr/bin/env python3
from __future__ import annotations

import argparse

from common import WORLDS_DIR, read_json


def discover_worlds() -> list[dict[str, str]]:
    rows = []
    if not WORLDS_DIR.exists():
        return rows
    for path in sorted(item for item in WORLDS_DIR.iterdir() if item.is_dir()):
        manifest = read_json(path / "manifest.json", {})
        if not manifest:
            continue
        rows.append(
            {
                "slug": path.name,
                "display_name": manifest.get("display_name", path.name),
                "profile": manifest.get("profile", "generic"),
                "genre": manifest.get("genre", "unknown"),
                "preset": "yes" if manifest.get("preset_world") else "no",
                "description": manifest.get("description", ""),
            }
        )
    return rows


def format_worlds(rows: list[dict[str, str]]) -> str:
    if not rows:
        return "No playable worlds found. Build one with scripts/build_world.py first."
    lines = ["可游玩世界："]
    for idx, row in enumerate(rows, 1):
        preset = "内置预设" if row["preset"] == "yes" else "本地世界"
        lines.append(f"{idx}. {row['slug']} - {row['display_name']}")
        lines.append(f"   类型：profile={row['profile']} / genre={row['genre']} / {preset}")
        if row["description"]:
            lines.append(f"   说明：{row['description']}")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="List playable worlds.")
    parser.parse_args()
    print(format_worlds(discover_worlds()))


if __name__ == "__main__":
    main()
