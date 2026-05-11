#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from bootstrap_profile import build_profile
from distill_playable import distill
from extract import extract
from index import build_index
from ingest import ingest
from merge import merge


def build(world: str, input_path: Path, profile: str, target_chars: int, max_chars: int, sample_chunks: int) -> None:
    ingest_profile = "generic" if profile == "auto" else profile
    ingest(world, input_path, target_chars, max_chars, ingest_profile)
    if profile == "auto":
        build_profile(world, sample_chunks)
        extract(world, "auto")
    else:
        extract(world, profile)
    merge(world)
    distill(world)
    build_index(world)
    print(f"Build complete for world={world} profile={profile}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the full novel adventure distillation pipeline.")
    parser.add_argument("--world", required=True)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--profile", default="auto", choices=["auto", "generic", "doupo"])
    parser.add_argument("--target-chars", type=int, default=4000)
    parser.add_argument("--max-chars", type=int, default=6000)
    parser.add_argument("--sample-chunks", type=int, default=80)
    args = parser.parse_args()
    build(args.world, args.input, args.profile, args.target_chars, args.max_chars, args.sample_chunks)


if __name__ == "__main__":
    main()
