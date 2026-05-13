#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from typing import Any

from common import load_manifest, read_json, save_manifest, world_dir, write_json


PHASES = [
    {"phase": "lead", "label": "线索", "rule": "只确认来源、对象和风险，不默认接取。"},
    {"phase": "contact", "label": "接触", "rule": "问清报酬、期限、筹码和失败后果。"},
    {"phase": "prepare", "label": "准备", "rule": "准备资源、路线、关系或能力边界。"},
    {"phase": "execute", "label": "执行", "rule": "按当前 objective 行动，失败也要写入后果。"},
    {"phase": "settle", "label": "结算", "rule": "交付证据、领取奖励或承担代价。"},
    {"phase": "aftermath", "label": "余波", "rule": "关系、市场、地点或事件链变化进入世界状态。"},
]


def infer_phase_index(quest: dict[str, Any]) -> int:
    objectives = [obj for obj in quest.get("objectives", []) if isinstance(obj, dict)]
    if not objectives:
        return 0
    done = sum(1 for obj in objectives if obj.get("done"))
    if quest.get("status") == "completed":
        return 5
    ratio = done / max(1, len(objectives))
    if done == 0:
        return 1 if quest.get("status") == "active" else 0
    if ratio < 0.5:
        return 2
    if ratio < 1.0:
        return 3
    return 4


def build_quest_lifecycle(world: str) -> dict[str, Any]:
    wdir = world_dir(world)
    quests = read_json(wdir / "quest_templates.json", {}).get("quests", [])
    rows = []
    for quest in quests:
        if not isinstance(quest, dict) or not quest.get("quest_id"):
            continue
        rows.append(
            {
                "quest_id": quest.get("quest_id"),
                "name": quest.get("name"),
                "source": quest.get("source"),
                "phases": PHASES,
                "policy": "Quest lifecycle tracks stage and next pressure only; it must not force a route or grant rewards before objectives are resolved.",
            }
        )
    output = {"world": world, "phases": PHASES, "quests": rows}
    write_json(wdir / "quest_lifecycle.json", output)
    manifest = load_manifest(wdir, world)
    manifest["quest_lifecycle"] = "quest_lifecycle.json"
    save_manifest(wdir, manifest)
    print(f"Built quest_lifecycle.json quests={len(rows)}")
    return output


def advance_quest_lifecycle(state: dict[str, Any]) -> list[str]:
    messages: list[str] = []
    runtime = state.setdefault("runtime", {}).setdefault("quest_lifecycle", {})
    for quest in state.get("active_quests", []):
        if not isinstance(quest, dict):
            continue
        idx = infer_phase_index(quest)
        phase = PHASES[idx]
        previous = quest.get("phase")
        quest["phase"] = phase["phase"]
        quest["phase_label"] = phase["label"]
        quest["phase_rule"] = phase["rule"]
        runtime[str(quest.get("quest_id"))] = {
            "name": quest.get("name"),
            "phase": phase["phase"],
            "label": phase["label"],
            "status": quest.get("status"),
        }
        if previous != phase["phase"]:
            messages.append(f"任务阶段：{quest.get('name')} -> {phase['label']}（{phase['rule']}）")
    return messages[:4]


def quest_lifecycle_lines(state: dict[str, Any]) -> list[str]:
    rows = []
    for quest in state.get("active_quests", []):
        if isinstance(quest, dict) and quest.get("status") == "active":
            rows.append(f"- {quest.get('name')}：{quest.get('phase_label', '未分阶段')}；{quest.get('phase_rule', '按当前目标推进。')}")
        if len(rows) >= 4:
            break
    return rows or ["- 暂无需要分阶段追踪的任务。"]


def main() -> None:
    parser = argparse.ArgumentParser(description="Build quest lifecycle projection.")
    parser.add_argument("--world", required=True)
    parser.add_argument("--rebuild", action="store_true")
    args = parser.parse_args()
    data = build_quest_lifecycle(args.world) if args.rebuild else read_json(world_dir(args.world) / "quest_lifecycle.json", {})
    print(json.dumps(data, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
