#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from typing import Any

from common import load_manifest, read_json, save_manifest, sha1_text, world_dir, write_json


def compact(value: Any, limit: int = 96) -> str:
    text = " ".join(str(value or "").replace("\n", " ").split()).strip(" ，。；：")
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip("，。；： ") + "…"


def build_director_plan(world: str) -> dict[str, Any]:
    wdir = world_dir(world)
    arcs = read_json(wdir / "story_arcs.json", {}).get("arcs", [])
    events = read_json(wdir / "world_events.json", {}).get("events", [])
    scene_graph = read_json(wdir / "scene_graph.json", {})
    beats: list[dict[str, Any]] = []
    for arc in arcs[:12]:
        name = str(arc.get("name") or arc.get("arc_id") or "").strip()
        if not name:
            continue
        beats.append(
            {
                "beat_id": "beat_" + sha1_text(f"arc:{name}", 10),
                "source": "story_arcs.json",
                "name": name,
                "tempo": "slow_burn",
                "purpose": compact(arc.get("summary") or "长期目标只作为压力和方向，不强制玩家每回合推进。"),
                "entry_signals": [compact(term, 40) for term in arc.get("key_terms", [])[:4] if term],
                "allowed_pressure": "提示机会窗口、代价或旁人行动；不得替玩家做决定，不得跳过前置条件。",
            }
        )
    for event in events[:12]:
        title = str(event.get("title") or event.get("name") or "").strip()
        if not title:
            continue
        beats.append(
            {
                "beat_id": "beat_" + sha1_text(f"event:{title}", 10),
                "source": "world_events.json",
                "name": title,
                "tempo": "time_pressure",
                "purpose": compact(event.get("summary") or event.get("description") or "世界事件提供时间压力和后果。"),
                "entry_signals": [compact(title, 40)],
                "allowed_pressure": "只提醒已出现或将过期的 canon 事件，不凭空制造主线。",
            }
        )
    output = {
        "world": world,
        "policy": "The director layer controls pacing only. It may surface canon-derived pressure, downtime, and opportunity windows, but cannot invent hard facts or force a quest path.",
        "default_free_roam_ratio": 0.6,
        "locations": [row.get("name") for row in scene_graph.get("locations", [])[:16] if row.get("name")],
        "beats": beats,
    }
    write_json(wdir / "director_plan.json", output)
    manifest = load_manifest(wdir, world)
    manifest["director_plan"] = "director_plan.json"
    save_manifest(wdir, manifest)
    print(f"Built director_plan.json beats={len(beats)}")
    return output


EARLY_BLOCKED_BEAT_WORDS = ("天府联盟", "魂族", "魂殿", "净莲妖火", "陨落心炎", "迦南学院", "丹会", "云岚宗复仇")
EARLY_ALLOWED_BEAT_WORDS = ("乌坦城", "药材", "魔核", "筑基灵液", "筹钱", "废柴", "家族", "药老", "信任", "三年之约")


def beat_text(beat: dict[str, Any]) -> str:
    return " ".join(
        [
            str(beat.get("name") or ""),
            str(beat.get("purpose") or ""),
            " ".join(str(item) for item in beat.get("entry_signals", []) if item),
        ]
    )


def eligible_pressure_beats(plan: dict[str, Any], state: dict[str, Any], location: str, turn: int) -> list[dict[str, Any]]:
    player = state.get("player", {})
    realm = str(player.get("realm_or_level") or player.get("realm") or "")
    early_local = turn < 40 and ("乌坦" in location or "斗之气" in realm or "低段" in realm)
    rows: list[dict[str, Any]] = []
    for beat in plan.get("beats", []):
        text = beat_text(beat)
        if early_local and any(word in text for word in EARLY_BLOCKED_BEAT_WORDS):
            continue
        if early_local and not any(word in text for word in EARLY_ALLOWED_BEAT_WORDS):
            continue
        rows.append(beat)
    return rows


def advance_director(world: str, state: dict[str, Any], scene: dict[str, Any], resolution: dict[str, Any], turn: int) -> tuple[list[str], list[str]]:
    plan = read_json(world_dir(world) / "director_plan.json", {})
    runtime = state.setdefault("runtime", {}).setdefault("director", {"history": []})
    history = runtime.setdefault("history", [])
    kind = str(resolution.get("kind") or "general")
    status = str(resolution.get("status") or "allowed")
    location = str(scene.get("location") or state.get("meta", {}).get("current_location") or "当前地点")
    mode = "free_roam"
    label = "自由探索"
    reason = "保持自由探索；不强制任务线。"
    eligible_beats = eligible_pressure_beats(plan, state, location, turn)
    if status in {"blocked", "partial_or_blocked"}:
        mode = "cooldown"
        label = "缓冲准备"
        reason = "刚遇到阻断，下一步应提供低风险准备、情报或撤退选择。"
    elif kind in {"quest", "combat"}:
        mode = "consequence"
        label = "后果展开"
        reason = "行动已触发明确后果，下一步应展示局势变化而非立刻塞新任务。"
    elif turn % 5 == 0 and eligible_beats:
        mode = "pressure_ping"
        label = "机会窗口"
        reason = "可轻量提醒一个已蒸馏的机会窗口，但不能绑架玩家当前行动。"

    entry = {"turn": turn, "mode": mode, "label": label, "location": location, "reason": reason}
    history.append(entry)
    del history[:-30]
    lines = [f"- {label}：{reason}"]
    options: list[str] = []
    if mode == "cooldown":
        options = ["先撤到安全位置复盘风险。", "找可信 NPC 问清前置条件。"]
    elif mode == "pressure_ping":
        used = {row.get("beat_id") for row in history[-8:] if row.get("beat_id")}
        beat = next((row for row in eligible_beats if row.get("beat_id") not in used), eligible_beats[turn % len(eligible_beats)])
        entry["beat_id"] = beat.get("beat_id")
        lines.append(f"- 机会窗口：{beat.get('name')}（来源：{beat.get('source')}）")
        options = [f"只打听「{beat.get('name')}」的现状，不承诺接下。"]
    return lines, options


def main() -> None:
    parser = argparse.ArgumentParser(description="Build or inspect canon-derived director plan.")
    parser.add_argument("--world", required=True)
    parser.add_argument("--rebuild", action="store_true")
    args = parser.parse_args()
    data = build_director_plan(args.world) if args.rebuild else read_json(world_dir(args.world) / "director_plan.json", {})
    print(json.dumps(data, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
