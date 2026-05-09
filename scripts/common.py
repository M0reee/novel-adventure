#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable


FACT_TYPES = {
    "world_law",
    "power_realm",
    "cultivation_rule",
    "faction",
    "location",
    "npc",
    "item",
    "technique",
    "event",
    "relationship",
    "style_signal",
    "playable_hook",
}

SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
WORLDS_DIR = SKILL_DIR / "worlds"


def world_dir(slug: str) -> Path:
    if not re.fullmatch(r"[A-Za-z0-9_-]+", slug):
        raise SystemExit("World slug must contain only letters, numbers, underscores, and hyphens.")
    path = WORLDS_DIR / slug
    path.mkdir(parents=True, exist_ok=True)
    return path


def read_text(path: Path) -> str:
    for encoding in ("utf-8", "utf-8-sig", "gb18030"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    raise UnicodeDecodeError("unknown", b"", 0, 1, f"Could not decode {path}")


def write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def sha1_text(text: str, length: int = 12) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:length]


def now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def normalize_space(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{4,}", "\n\n\n", text)
    return text.strip()


def sentence_split(text: str) -> list[str]:
    parts = re.split(r"(?<=[。！？!?；;])\s*", text)
    return [part.strip() for part in parts if part.strip()]


def default_player_state(world_name: str) -> dict[str, Any]:
    return {
        "meta": {
            "world": world_name,
            "current_time": "第1日 清晨",
            "current_location": "未确定起点",
            "current_stage": "开局",
            "turn": 0,
        },
        "player": {
            "name": "旅人",
            "identity": "未定",
            "realm_or_level": "凡人",
            "attributes": {},
            "resources": {},
            "equipment": [],
            "status_effects": [],
        },
        "relationships": [],
        "active_quests": [],
        "world_events": [],
        "action_log": [],
    }


def load_manifest(path: Path, world: str) -> dict[str, Any]:
    manifest_path = path / "manifest.json"
    manifest = read_json(manifest_path, {})
    if not manifest:
        manifest = {
            "world": world,
            "created_at": now_iso(),
            "updated_at": now_iso(),
            "source_files": [],
            "chunk_count": 0,
            "fact_count": 0,
        }
    return manifest


def save_manifest(path: Path, manifest: dict[str, Any]) -> None:
    manifest["updated_at"] = now_iso()
    write_json(path / "manifest.json", manifest)

