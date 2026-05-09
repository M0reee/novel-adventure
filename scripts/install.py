#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parent.parent
SKILL_NAME = SKILL_DIR.name
TARGETS = {
    "codex": Path.home() / ".codex" / "skills",
    "claude": Path.home() / ".claude" / "skills",
    "agents": Path.home() / ".agents" / "skills",
    "project-codex": Path.cwd() / ".codex" / "skills",
    "project-claude": Path.cwd() / ".claude" / "skills",
    "project-agents": Path.cwd() / ".agents" / "skills",
}
EXCLUDE_DIRS = {"worlds", "__pycache__", ".git"}
EXCLUDE_SUFFIXES = {".pyc", ".sqlite", ".db", ".db-wal", ".db-shm"}


def ignore(_dir: str, names: list[str]) -> set[str]:
    ignored = set()
    for name in names:
        path = Path(name)
        if name in EXCLUDE_DIRS or path.suffix in EXCLUDE_SUFFIXES:
            ignored.add(name)
    return ignored


def install(target: str, destination: Path | None, force: bool) -> None:
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


def main() -> None:
    parser = argparse.ArgumentParser(description="Install novel-adventure into a common Agent Skills directory.")
    parser.add_argument("--target", choices=sorted(TARGETS), default="agents")
    parser.add_argument("--destination", type=Path, help="Override destination skills directory.")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    install(args.target, args.destination, args.force)


if __name__ == "__main__":
    main()
