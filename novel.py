#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from scripts.build_world import build
from scripts.encounter_runtime import clear_encounter
from scripts.extract import extract
from scripts.index import build_index
from scripts.ingest import ingest
from scripts.install import install
from scripts.list_worlds import discover_worlds, format_worlds
from scripts.merge import merge
from scripts.opening import build_opening, ensure_opening, format_opening
from scripts.qa_world import qa
from scripts.retrieve import retrieve
from scripts.rpg_profile import build_rpg_profile
from scripts.run_turn import run_turn
from scripts.start_game import initialize_state


def cmd_install(args: argparse.Namespace) -> None:
    install(args.target, args.destination, args.force, args.no_commands, args.command_destination)


def cmd_worlds(args: argparse.Namespace) -> None:
    print(format_worlds(discover_worlds()))


def cmd_start(args: argparse.Namespace) -> None:
    state = initialize_state(args.world, args.reset)
    print(format_opening(ensure_opening(args.world)))
    player = state.get("player", {})
    print("")
    print("## 当前角色")
    print(f"- 身份：{player.get('identity')}")
    print(f"- 境界/等级：{player.get('realm_or_level')}")


def cmd_play(args: argparse.Namespace) -> None:
    print(run_turn(args.world, args.action, args.limit, args.dry_run))


def cmd_build(args: argparse.Namespace) -> None:
    build(
        args.world,
        args.input,
        args.profile,
        args.target_chars,
        args.max_chars,
        args.sample_chunks,
        args.llm_provider,
        args.llm_model,
        args.llm_max_chunks,
        args.llm_base_url,
    )


def cmd_llm_pack(args: argparse.Namespace) -> None:
    extract(
        args.world,
        args.profile,
        llm_provider="prompt-pack",
        llm_model=args.llm_model,
        llm_max_chunks=args.llm_max_chunks,
    )


def cmd_llm_import(args: argparse.Namespace) -> None:
    extract(args.world, args.profile, llm_responses=args.responses)


def cmd_qa(args: argparse.Namespace) -> None:
    qa(args.world)


def cmd_search(args: argparse.Namespace) -> None:
    for row in retrieve(args.world, args.query, args.limit):
        print(f"[{row.get('type')}] {row.get('name')}: {row.get('claim')}")


def cmd_clear_encounter(args: argparse.Namespace) -> None:
    clear_encounter(args.world)
    print(f"Cleared active encounter for {args.world}")


def cmd_rebuild_rpg(args: argparse.Namespace) -> None:
    build_rpg_profile(args.world)


def cmd_pipeline(args: argparse.Namespace) -> None:
    if args.step == "ingest":
        if args.input is None:
            raise SystemExit("pipeline ingest requires an input path")
        ingest(args.world, args.input, args.target_chars, args.max_chars, "generic")
    elif args.step == "extract":
        extract(
            args.world,
            args.profile,
            args.llm_provider,
            args.llm_model,
            args.llm_max_chunks,
            args.llm_base_url,
            args.llm_responses,
        )
    elif args.step == "merge":
        merge(args.world)
    elif args.step == "opening":
        build_opening(args.world)
    elif args.step == "index":
        build_index(args.world)


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="Friendly command router for Novel Adventure.")
    sub = root.add_subparsers(dest="command", required=True)

    p = sub.add_parser("install", help="Install this skill into a host skill directory.")
    p.add_argument(
        "--target",
        default="agents",
        choices=[
            "agents",
            "claude",
            "codex",
            "hermes",
            "openclaw",
            "project-agents",
            "project-claude",
            "project-codex",
            "project-hermes",
            "project-openclaw",
        ],
    )
    p.add_argument("--destination", type=Path)
    p.add_argument("--command-destination", type=Path)
    p.add_argument("--no-commands", action="store_true")
    p.add_argument("--force", action="store_true")
    p.set_defaults(func=cmd_install)

    p = sub.add_parser("worlds", help="List playable worlds.")
    p.set_defaults(func=cmd_worlds)

    p = sub.add_parser("start", help="Start or reset a world.")
    p.add_argument("world")
    p.add_argument("--reset", action="store_true")
    p.set_defaults(func=cmd_start)

    p = sub.add_parser("play", help="Run one adventure turn.")
    p.add_argument("world")
    p.add_argument("action")
    p.add_argument("--limit", type=int, default=30)
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(func=cmd_play)

    p = sub.add_parser("build", help="Build a world from TXT/MD.")
    p.add_argument("world")
    p.add_argument("input", type=Path)
    p.add_argument("--profile", default="auto", choices=["auto", "generic", "doupo"])
    p.add_argument("--target-chars", type=int, default=4000)
    p.add_argument("--max-chars", type=int, default=6000)
    p.add_argument("--sample-chunks", type=int, default=80)
    p.add_argument("--llm-provider", default="none", choices=["none", "openai-compatible", "prompt-pack"])
    p.add_argument("--llm-model", default="gpt-4.1-mini")
    p.add_argument("--llm-max-chunks", type=int)
    p.add_argument("--llm-base-url")
    p.set_defaults(func=cmd_build)

    p = sub.add_parser("llm-pack", help="Export prompt-pack requests for host-model distillation.")
    p.add_argument("world")
    p.add_argument("--profile", default="auto")
    p.add_argument("--llm-model", default="gpt-4.1-mini")
    p.add_argument("--llm-max-chunks", type=int, default=80)
    p.set_defaults(func=cmd_llm_pack)

    p = sub.add_parser("llm-import", help="Import prompt-pack responses.")
    p.add_argument("world")
    p.add_argument("responses", type=Path)
    p.add_argument("--profile", default="auto")
    p.set_defaults(func=cmd_llm_import)

    p = sub.add_parser("qa", help="Check world quality.")
    p.add_argument("world")
    p.set_defaults(func=cmd_qa)

    p = sub.add_parser("search", help="Search canon.")
    p.add_argument("world")
    p.add_argument("query")
    p.add_argument("--limit", type=int, default=10)
    p.set_defaults(func=cmd_search)

    p = sub.add_parser("clear-encounter", help="Clear active combat encounter.")
    p.add_argument("world")
    p.set_defaults(func=cmd_clear_encounter)

    p = sub.add_parser("rebuild-rpg", help="Rebuild world RPG terminology profile.")
    p.add_argument("world")
    p.set_defaults(func=cmd_rebuild_rpg)

    p = sub.add_parser("pipeline", help="Advanced single pipeline step.")
    p.add_argument("step", choices=["ingest", "extract", "merge", "opening", "index"])
    p.add_argument("world")
    p.add_argument("input", nargs="?", type=Path)
    p.add_argument("--profile", default="auto")
    p.add_argument("--target-chars", type=int, default=4000)
    p.add_argument("--max-chars", type=int, default=6000)
    p.add_argument("--llm-provider", default="none", choices=["none", "openai-compatible", "prompt-pack"])
    p.add_argument("--llm-model", default="gpt-4.1-mini")
    p.add_argument("--llm-max-chunks", type=int)
    p.add_argument("--llm-base-url")
    p.add_argument("--llm-responses", type=Path)
    p.set_defaults(func=cmd_pipeline)

    return root


def main() -> None:
    args = parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
