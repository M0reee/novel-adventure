#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parent.parent
SKILL_NAME = "novel-adventure"
TARGETS = {
    "codex": Path.home() / ".codex" / "skills",
    "claude": Path.home() / ".claude" / "skills",
    "agents": Path.home() / ".agents" / "skills",
    "hermes": Path.home() / ".hermes" / "skills",
    "openclaw": Path.home() / ".openclaw" / "skills",
    "project-codex": Path.cwd() / ".codex" / "skills",
    "project-claude": Path.cwd() / ".claude" / "skills",
    "project-agents": Path.cwd() / ".agents" / "skills",
    "project-hermes": Path.cwd() / ".hermes" / "skills",
    "project-openclaw": Path.cwd() / ".openclaw" / "skills",
}
COMMAND_TARGETS = {
    "codex": Path.home() / ".codex" / "prompts",
    "claude": Path.home() / ".claude" / "commands",
    "agents": Path.home() / ".agents" / "commands",
    "hermes": Path.home() / ".hermes" / "commands",
    "openclaw": Path.home() / ".openclaw" / "commands",
    "project-codex": Path.cwd() / ".codex" / "prompts",
    "project-claude": Path.cwd() / ".claude" / "commands",
    "project-agents": Path.cwd() / ".agents" / "commands",
    "project-hermes": Path.cwd() / ".hermes" / "commands",
    "project-openclaw": Path.cwd() / ".openclaw" / "commands",
}
COMMAND_SOURCE_DIR = SKILL_DIR / "commands"
EXCLUDE_DIRS = {"__pycache__", ".git"}
EXCLUDE_SUFFIXES = {".pyc", ".sqlite", ".db", ".db-wal", ".db-shm"}
PUBLIC_PRESET_WORLDS = {"doupo_cangqiong"}
RAW_WORLD_FILES = {
    "chunks.jsonl",
    "facts.jsonl",
    "source_index.jsonl",
    "llm_requests.jsonl",
    "llm_responses.jsonl",
    "llm_facts_cache.jsonl",
}


def ignore(directory: str, names: list[str]) -> set[str]:
    ignored = set()
    current = Path(directory)
    if current.name == "worlds":
        return {name for name in names if name not in PUBLIC_PRESET_WORLDS}
    for name in names:
        path = Path(name)
        if name in EXCLUDE_DIRS or name in RAW_WORLD_FILES:
            ignored.add(name)
        elif path.suffix in EXCLUDE_SUFFIXES and not (current.name in PUBLIC_PRESET_WORLDS and name == "retrieval.sqlite"):
            ignored.add(name)
    return ignored


def install_commands(target: str, command_destination: Path | None, force: bool) -> None:
    if not COMMAND_SOURCE_DIR.exists():
        return
    base = command_destination or COMMAND_TARGETS[target]
    base.mkdir(parents=True, exist_ok=True)
    installed = []
    for source in sorted(COMMAND_SOURCE_DIR.glob("*.md")):
        target_file = base / source.name
        if target_file.exists() and not force:
            raise SystemExit(f"{target_file} already exists. Re-run with --force to replace it.")
        shutil.copy2(source, target_file)
        installed.append(target_file.name)
    print(f"Installed slash command prompts to {base}: {', '.join(installed)}")


def install(
    target: str,
    destination: Path | None,
    force: bool,
    no_commands: bool = False,
    command_destination: Path | None = None,
) -> None:
    base = destination or TARGETS[target]
    target_dir = base / SKILL_NAME
    if target_dir.exists():
        if not force:
            raise SystemExit(f"{target_dir} already exists. Re-run with --force to replace it.")
        shutil.rmtree(target_dir)
    base.mkdir(parents=True, exist_ok=True)
    shutil.copytree(SKILL_DIR, target_dir, ignore=ignore)
    (target_dir / "worlds").mkdir(exist_ok=True)
    print(f"Installed {SKILL_NAME} to {target_dir}")
    if not no_commands:
        install_commands(target, command_destination, force)


def main() -> None:
    parser = argparse.ArgumentParser(description="Install novel-adventure into a common Agent Skills directory.")
    parser.add_argument("--target", choices=sorted(TARGETS), default="agents")
    parser.add_argument("--destination", type=Path, help="Override destination skills directory.")
    parser.add_argument("--command-destination", type=Path, help="Override slash-command prompt directory.")
    parser.add_argument("--no-commands", action="store_true", help="Install the skill only; do not install slash command prompts.")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    install(args.target, args.destination, args.force, args.no_commands, args.command_destination)


if __name__ == "__main__":
    main()
