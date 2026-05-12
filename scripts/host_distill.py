#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from bootstrap_profile import build_profile
from distill_playable import distill
from distillation_qa import distillation_qa
from extract import extract
from gameplay_profile import build_gameplay_profile
from index import build_index
from ingest import ingest
from merge import merge
from narrative_intelligence import build_narrative_intelligence
from qa_world import qa
from common import read_jsonl, world_dir
from world_events import build_world_events


def request_count(world: str) -> int:
    return len(read_jsonl(world_dir(world) / "llm_requests.jsonl"))


def response_count(world: str, responses: Path | None = None) -> int:
    path = responses or (world_dir(world) / "llm_responses.jsonl")
    return len(read_jsonl(path))


def export_prompt_pack(
    world: str,
    input_path: Path | None,
    profile: str,
    target_chars: int,
    max_chars: int,
    sample_chunks: int,
    llm_max_chunks: int,
    llm_model: str,
) -> None:
    wdir = world_dir(world)
    if input_path:
        ingest_profile = "generic" if profile == "auto" else profile
        ingest(world, input_path, target_chars, max_chars, ingest_profile)
        if profile == "auto":
            build_profile(world, sample_chunks)
    elif not (wdir / "chunks.jsonl").exists():
        raise SystemExit("No chunks found. Provide --input <txt_or_dir> for the first host distill export.")

    extract(world, profile, llm_provider="prompt-pack", llm_model=llm_model, llm_max_chunks=llm_max_chunks)
    print("")
    print("Host-model distillation request pack is ready.")
    print(f"- Requests: worlds/{world}/llm_requests.jsonl ({request_count(world)} rows)")
    print("- Ask the host model to process each JSONL row and write responses to:")
    print(f"  worlds/{world}/llm_responses.jsonl")
    print("- Then run:")
    print(f"  python novel.py host-import {world} worlds/{world}/llm_responses.jsonl")


def import_prompt_pack(world: str, responses: Path, profile: str) -> None:
    if not responses.exists():
        raise SystemExit(f"Response file not found: {responses}")
    extract(world, profile, llm_responses=responses)
    merge(world)
    distill(world)
    build_narrative_intelligence(world)
    build_gameplay_profile(world)
    build_world_events(world)
    build_index(world)
    distillation_qa(world)
    qa(world)
    print("")
    print("Host-model distillation import complete.")
    print(f"- Imported responses: {response_count(world, responses)}")
    print(f"- Quality report: worlds/{world}/quality_report.md")


def status(world: str) -> None:
    wdir = world_dir(world)
    requests = request_count(world)
    responses = response_count(world)
    has_chunks = (wdir / "chunks.jsonl").exists()
    has_facts = (wdir / "facts.jsonl").exists()
    has_index = (wdir / "retrieval.sqlite").exists()
    has_quality = (wdir / "quality_report.md").exists()
    print(f"Host distill status: {world}")
    print(f"- chunks.jsonl: {'yes' if has_chunks else 'no'}")
    print(f"- llm_requests.jsonl: {requests} row(s)")
    print(f"- llm_responses.jsonl: {responses} row(s)")
    print(f"- facts.jsonl: {'yes' if has_facts else 'no'}")
    print(f"- retrieval.sqlite: {'yes' if has_index else 'no'}")
    print(f"- quality_report.md: {'yes' if has_quality else 'no'}")
    if requests and not responses:
        print("Next: process llm_requests.jsonl with the host model, then run host-import.")
    elif responses:
        print("Next: run host-import if you have not imported the responses yet.")
    else:
        print("Next: run host-export with --input <txt_or_dir>.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Guide host-model prompt-pack distillation.")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("export")
    p.add_argument("--world", required=True)
    p.add_argument("--input", type=Path)
    p.add_argument("--profile", default="auto")
    p.add_argument("--target-chars", type=int, default=4000)
    p.add_argument("--max-chars", type=int, default=6000)
    p.add_argument("--sample-chunks", type=int, default=80)
    p.add_argument("--llm-max-chunks", type=int, default=80)
    p.add_argument("--llm-model", default="gpt-4.1-mini")

    p = sub.add_parser("import")
    p.add_argument("--world", required=True)
    p.add_argument("--responses", required=True, type=Path)
    p.add_argument("--profile", default="auto")

    p = sub.add_parser("status")
    p.add_argument("--world", required=True)

    args = parser.parse_args()
    if args.command == "export":
        export_prompt_pack(
            args.world,
            args.input,
            args.profile,
            args.target_chars,
            args.max_chars,
            args.sample_chunks,
            args.llm_max_chunks,
            args.llm_model,
        )
    elif args.command == "import":
        import_prompt_pack(args.world, args.responses, args.profile)
    elif args.command == "status":
        status(args.world)


if __name__ == "__main__":
    main()
