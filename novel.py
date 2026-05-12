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
from scripts.save_manager import copy_save, delete_save, format_saves
from scripts.start_game import initialize_state


def _save_summary(world: str) -> str:
    from scripts.common import read_json, world_dir

    state_path = world_dir(world) / "player_state.json"
    if not state_path.exists():
        return "无存档"
    state = read_json(state_path, {})
    meta = state.get("meta", {})
    player = state.get("player", {})
    turn = meta.get("turn", meta.get("turn_count", state.get("turn_count", 0)))
    location = meta.get("current_location", "未知地点")
    realm = player.get("realm_or_level", "未知境界")
    return f"已有存档：回合 {turn} / {location} / {realm}"


def cmd_install(args: argparse.Namespace) -> None:
    install(args.target, args.destination, args.force, args.no_commands, args.command_destination)


def cmd_launch(args: argparse.Namespace) -> None:
    rows = discover_worlds()
    print("## Novel Adventure 启动向导")
    print("")
    print("请选择你要做什么：")
    print("1. 游玩已有世界 / 读取存档")
    print("2. 蒸馏新的小说世界")
    print("")
    if rows:
        print("## 当前已有世界")
        for idx, row in enumerate(rows, 1):
            preset = "内置预设" if row["preset"] == "yes" else "本地世界"
            print(f"{idx}. {row['slug']} - {row['display_name']}（{preset}，{_save_summary(row['slug'])}）")
    else:
        print("当前没有可游玩世界。请选择 2 来蒸馏新的小说世界。")
    print("")
    print("也可以直接使用：")
    print("- /novel-start <world> --reset")
    print("- /novel-saves <world>")
    print("- /novel-play <world> <行动>")
    print("- /novel-build <world> <txt_or_dir>")
    print("- /novel-llm-pack <world> --llm-max-chunks 80")

    if not sys.stdin.isatty():
        return

    choice = input("请输入 1 或 2: ").strip()
    if choice == "1":
        if not rows:
            raise SystemExit("No playable worlds found. Build one first.")
        selected = input("请选择世界编号或 slug: ").strip()
        world = rows[int(selected) - 1]["slug"] if selected.isdigit() else selected
        reset = input("是否重置存档？输入 y 重置，直接回车读取/创建存档: ").strip().lower() == "y"
        slot = input("请输入存档 slot（直接回车使用 default）: ").strip() or None
        state = initialize_state(world, reset, slot)
        print(format_opening(ensure_opening(world)))
        print("")
        print("## 当前角色")
        player = state.get("player", {})
        print(f"- 身份：{player.get('identity')}")
        print(f"- 境界/等级：{player.get('realm_or_level')}")
        print("")
        slot_arg = f" --slot {slot}" if slot else ""
        print(f"下一步：python novel.py play {world} \"观察周围环境\"{slot_arg}")
        return
    if choice == "2":
        world = input("请输入世界 slug（例如 fanren）: ").strip()
        input_path = Path(input("请输入小说 TXT/MD 文件或目录路径: ").strip()).expanduser()
        print("请选择蒸馏方式：")
        print("1. 本地启发式蒸馏（无需 API，最快，质量基础）")
        print("2. API LLM-assisted 蒸馏（质量更好，需要 NOVEL_ADVENTURE_LLM_API_KEY）")
        print("3. 宿主模型 prompt-pack（不需要 API，先导出请求再让宿主模型处理）")
        mode = input("请输入 1/2/3: ").strip()
        if mode == "2":
            max_chunks = int(input("LLM 最多处理多少 chunk？默认 120: ").strip() or "120")
            build(world, input_path, "auto", 4000, 6000, 80, "openai-compatible", "gpt-4.1-mini", max_chunks, None)
        elif mode == "3":
            max_chunks = int(input("导出多少个 LLM 请求？默认 80: ").strip() or "80")
            build(world, input_path, "auto", 4000, 6000, 80, "prompt-pack", "gpt-4.1-mini", max_chunks, None)
            print(f"已生成 worlds/{world}/llm_requests.jsonl。让宿主模型处理后，用 python novel.py llm-import {world} worlds/{world}/llm_responses.jsonl 导入。")
        else:
            build(world, input_path, "auto", 4000, 6000, 80, "none", "gpt-4.1-mini", None, None)
        return
    raise SystemExit("Unknown choice. Enter 1 or 2.")


def cmd_worlds(args: argparse.Namespace) -> None:
    print(format_worlds(discover_worlds()))


def cmd_start(args: argparse.Namespace) -> None:
    state = initialize_state(args.world, args.reset, args.slot)
    print(format_opening(ensure_opening(args.world)))
    player = state.get("player", {})
    print("")
    print("## 当前角色")
    print(f"- 身份：{player.get('identity')}")
    print(f"- 境界/等级：{player.get('realm_or_level')}")
    print(f"- 存档：{state.get('meta', {}).get('save_slot', 'default')}")


def cmd_play(args: argparse.Namespace) -> None:
    print(run_turn(args.world, args.action, args.limit, args.dry_run, args.slot))


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


def cmd_saves(args: argparse.Namespace) -> None:
    print(format_saves(args.world))


def cmd_copy_save(args: argparse.Namespace) -> None:
    print(f"Copied save to {copy_save(args.world, args.from_slot, args.to_slot)}")


def cmd_delete_save(args: argparse.Namespace) -> None:
    delete_save(args.world, args.slot)
    print(f"Deleted save slot {args.slot} for {args.world}")


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

    p = sub.add_parser("launch", help="Interactive startup wizard.")
    p.set_defaults(func=cmd_launch)

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
    p.add_argument("--slot")
    p.add_argument("--reset", action="store_true")
    p.set_defaults(func=cmd_start)

    p = sub.add_parser("play", help="Run one adventure turn.")
    p.add_argument("world")
    p.add_argument("action")
    p.add_argument("--slot")
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

    p = sub.add_parser("saves", help="List save slots for a world.")
    p.add_argument("world")
    p.set_defaults(func=cmd_saves)

    p = sub.add_parser("copy-save", help="Copy a save slot.")
    p.add_argument("world")
    p.add_argument("from_slot")
    p.add_argument("to_slot")
    p.set_defaults(func=cmd_copy_save)

    p = sub.add_parser("delete-save", help="Delete a named save slot.")
    p.add_argument("world")
    p.add_argument("slot")
    p.set_defaults(func=cmd_delete_save)

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
