#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from bootstrap_profile import build_profile
from acquisition_routes import build_acquisition_routes
from distill_playable import distill
from distillation_qa import distillation_qa
from extract import extract
from gameplay_profile import build_gameplay_profile
from index import build_index
from ingest import ingest
from merge import merge
from narrative_intelligence import build_narrative_intelligence
from opening import build_opening
from ooc_qa import check_world
from qa_world import qa
from scene_graph import build_scene_graph
from skill_tree import build_skill_tree
from equipment_sets import build_equipment_sets
from economy_runtime import build_economy_state
from story_arcs import build_story_arcs
from world_events import build_world_events


def build(
    world: str,
    input_path: Path,
    profile: str,
    target_chars: int,
    max_chars: int,
    sample_chunks: int,
    llm_provider: str,
    llm_model: str,
    llm_max_chunks: int | None,
    llm_base_url: str | None,
) -> None:
    ingest_profile = "generic" if profile == "auto" else profile
    ingest(world, input_path, target_chars, max_chars, ingest_profile)
    if profile == "auto":
        build_profile(world, sample_chunks)
        extract(world, "auto", llm_provider=llm_provider, llm_model=llm_model, llm_max_chunks=llm_max_chunks, llm_base_url=llm_base_url)
    else:
        extract(world, profile, llm_provider=llm_provider, llm_model=llm_model, llm_max_chunks=llm_max_chunks, llm_base_url=llm_base_url)
    merge(world)
    build_opening(world)
    distill(world)
    build_narrative_intelligence(world)
    build_story_arcs(world)
    build_gameplay_profile(world)
    build_skill_tree(world)
    build_equipment_sets(world)
    build_economy_state(world)
    build_scene_graph(world)
    build_acquisition_routes(world)
    build_world_events(world)
    build_index(world)
    distillation_qa(world)
    check_world(world)
    qa(world)
    print(f"Build complete for world={world} profile={profile}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the full novel adventure distillation pipeline.")
    parser.add_argument("--world", required=True)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--profile", default="auto", choices=["auto", "generic", "doupo"])
    parser.add_argument("--target-chars", type=int, default=4000)
    parser.add_argument("--max-chars", type=int, default=6000)
    parser.add_argument("--sample-chunks", type=int, default=80)
    parser.add_argument("--llm-provider", default="none", choices=["none", "openai-compatible", "prompt-pack"])
    parser.add_argument("--llm-model", default="gpt-4.1-mini")
    parser.add_argument("--llm-max-chunks", type=int, help="Limit LLM-assisted chunks for cost control.")
    parser.add_argument("--llm-base-url", help="OpenAI-compatible base URL.")
    args = parser.parse_args()
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


if __name__ == "__main__":
    main()
