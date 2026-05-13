#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from typing import Any

from common import load_manifest, read_json, save_manifest, sha1_text, world_dir, write_json


def compact(value: Any, limit: int = 90) -> str:
    text = " ".join(str(value or "").replace("\n", " ").split()).strip(" ，。；：")
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip("，。；： ") + "…"


def build_npc_agency(world: str) -> dict[str, Any]:
    wdir = world_dir(world)
    motives = read_json(wdir / "npc_motives.json", {}).get("npcs", [])
    rows = []
    for row in motives:
        npc = str(row.get("npc") or row.get("name") or "").strip()
        if not npc:
            continue
        rows.append(
            {
                "npc": npc,
                "agency_id": "agency_" + sha1_text(npc, 10),
                "goal": compact(row.get("public_goal") or row.get("private_goal") or row.get("summary") or "维持自身利益和边界。"),
                "leverage": [compact(item, 60) for item in row.get("leverage", [])[:3] if item],
                "boundaries": [compact(item, 60) for item in row.get("boundaries", [])[:3] if item],
                "possible_moves": [
                    "提出条件或交换",
                    "拒绝越界请求",
                    "提供低风险线索",
                    "在关系足够时给出有限帮助",
                ],
            }
        )
    output = {
        "world": world,
        "policy": "NPC agency may propose, refuse, delay, or react according to canon-derived motives. It cannot hand out unsupported rewards or override player freedom.",
        "npcs": rows,
    }
    write_json(wdir / "npc_agency.json", output)
    manifest = load_manifest(wdir, world)
    manifest["npc_agency"] = "npc_agency.json"
    save_manifest(wdir, manifest)
    print(f"Built npc_agency.json npcs={len(rows)}")
    return output


def advance_npc_agency(world: str, state: dict[str, Any], scene: dict[str, Any], turn: int, resolution: dict[str, Any]) -> tuple[list[str], list[str]]:
    data = read_json(world_dir(world) / "npc_agency.json", {})
    runtime = state.setdefault("runtime", {}).setdefault("npc_agency", {"last_turn": 0, "history": []})
    if turn - int(runtime.get("last_turn", 0) or 0) < 3:
        return [], []
    visible = {str(row.get("name")) for row in scene.get("npcs", []) if row.get("name")}
    if not visible:
        return [], []
    candidates = [row for row in data.get("npcs", []) if row.get("npc") in visible]
    if not candidates:
        return [], []
    candidate = candidates[turn % len(candidates)]
    npc = candidate.get("npc")
    status = str(resolution.get("status") or "")
    if status in {"blocked", "partial_or_blocked"}:
        move = "提醒你先补前置条件，而不是硬闯。"
    else:
        move = "给出一个有限交换或低风险线索。"
    runtime["last_turn"] = turn
    runtime.setdefault("history", []).append({"turn": turn, "npc": npc, "move": move})
    runtime["history"] = runtime["history"][-30:]
    lines = [f"- {npc}：{move} 目标：{candidate.get('goal')}"]
    options = [f"找「{npc}」问清条件、代价和底线。"]
    return lines, options


def main() -> None:
    parser = argparse.ArgumentParser(description="Build NPC agency projection.")
    parser.add_argument("--world", required=True)
    parser.add_argument("--rebuild", action="store_true")
    args = parser.parse_args()
    data = build_npc_agency(args.world) if args.rebuild else read_json(world_dir(args.world) / "npc_agency.json", {})
    print(json.dumps(data, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
