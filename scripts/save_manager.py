#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import shutil
from pathlib import Path
from typing import Any

from common import read_json, world_dir, write_json


DEFAULT_SLOT = "default"


def normalize_slot(slot: str | None) -> str:
    value = (slot or DEFAULT_SLOT).strip()
    if value in {"", "main", "current"}:
        value = DEFAULT_SLOT
    if not re.fullmatch(r"[A-Za-z0-9_-]+", value):
        raise SystemExit("Save slot must contain only letters, numbers, underscores, and hyphens.")
    return value


def saves_dir(world: str) -> Path:
    path = world_dir(world) / "saves"
    path.mkdir(parents=True, exist_ok=True)
    return path


def save_path(world: str, slot: str | None = None) -> Path:
    slot_name = normalize_slot(slot)
    if slot_name == DEFAULT_SLOT:
        return world_dir(world) / "player_state.json"
    return saves_dir(world) / f"{slot_name}.json"


def load_save(world: str, slot: str | None = None, default: Any | None = None) -> dict[str, Any]:
    return read_json(save_path(world, slot), default if default is not None else {})


def write_save(world: str, slot: str | None, state: dict[str, Any]) -> None:
    slot_name = normalize_slot(slot)
    state.setdefault("meta", {})["save_slot"] = slot_name
    write_json(save_path(world, slot_name), state)


def list_saves(world: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    default_path = save_path(world, DEFAULT_SLOT)
    if default_path.exists():
        rows.append(describe_save(world, DEFAULT_SLOT, default_path))
    directory = saves_dir(world)
    for path in sorted(directory.glob("*.json")):
        rows.append(describe_save(world, path.stem, path))
    return rows


def describe_save(world: str, slot: str, path: Path) -> dict[str, Any]:
    state = read_json(path, {})
    meta = state.get("meta", {})
    player = state.get("player", {})
    return {
        "world": world,
        "slot": slot,
        "path": str(path),
        "turn": int(meta.get("turn", meta.get("turn_count", 0)) or 0),
        "location": meta.get("current_location", "未知地点"),
        "stage": meta.get("current_stage", "未知阶段"),
        "identity": player.get("identity", "未知身份"),
        "realm_or_level": player.get("realm_or_level", "未知等级"),
        "updated_at": path.stat().st_mtime if path.exists() else 0,
    }


def format_saves(world: str) -> str:
    rows = list_saves(world)
    if not rows:
        return f"No saves found for {world}. Start one with: python novel.py start {world} --slot {DEFAULT_SLOT}"
    lines = [f"存档列表：{world}"]
    for idx, row in enumerate(rows, 1):
        lines.append(
            f"{idx}. {row['slot']} - 回合 {row['turn']} / {row['location']} / {row['realm_or_level']} / {row['stage']}"
        )
    return "\n".join(lines)


def copy_save(world: str, source_slot: str | None, target_slot: str) -> Path:
    source = save_path(world, source_slot)
    if not source.exists():
        raise SystemExit(f"Source save not found: {source}")
    target = save_path(world, target_slot)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    state = read_json(target, {})
    state.setdefault("meta", {})["save_slot"] = normalize_slot(target_slot)
    write_json(target, state)
    return target


def delete_save(world: str, slot: str) -> None:
    slot_name = normalize_slot(slot)
    if slot_name == DEFAULT_SLOT:
        raise SystemExit("Refusing to delete default player_state.json. Use a named slot.")
    path = save_path(world, slot_name)
    if path.exists():
        path.unlink()


def main() -> None:
    parser = argparse.ArgumentParser(description="Manage Novel Adventure save slots.")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("list")
    p.add_argument("--world", required=True)
    p = sub.add_parser("copy")
    p.add_argument("--world", required=True)
    p.add_argument("--from-slot", default=DEFAULT_SLOT)
    p.add_argument("--to-slot", required=True)
    p = sub.add_parser("delete")
    p.add_argument("--world", required=True)
    p.add_argument("--slot", required=True)
    args = parser.parse_args()
    if args.command == "list":
        print(format_saves(args.world))
    elif args.command == "copy":
        print(f"Copied save to {copy_save(args.world, args.from_slot, args.to_slot)}")
    elif args.command == "delete":
        delete_save(args.world, args.slot)
        print(f"Deleted save slot {args.slot} for {args.world}")


if __name__ == "__main__":
    main()
