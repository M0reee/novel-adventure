#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from typing import Any

from common import load_manifest, read_json, save_manifest, world_dir, write_json


def quest_id(name: str) -> str:
    digest = hashlib.sha1(name.encode("utf-8")).hexdigest()[:10]
    return f"quest_{digest}"


def objective_for_hook(name: str, summary: str) -> list[dict[str, Any]]:
    text = f"{name} {summary}"
    if "势力" in text:
        return [
            {"id": "identify_contact", "text": "确认可接触的势力人物", "done": False},
            {"id": "offer_value", "text": "拿出情报、资源或行动价值", "done": False},
            {"id": "manage_reputation", "text": "避免触发敌对或人情债失控", "done": False},
        ]
    if "炼药" in text:
        return [
            {"id": "find_materials", "text": "确认所需药材、魔核或药方来源", "done": False},
            {"id": "find_alchemist", "text": "找到可信炼药师或学习基础炼药", "done": False},
            {"id": "make_or_trade", "text": "炼制、购买或交换一份可用资源", "done": False},
        ]
    if "异火" in text:
        return [
            {"id": "collect_clue", "text": "获得异火位置或传闻的可靠线索", "done": False},
            {"id": "prepare_protection", "text": "准备护体丹药、撤退路线和护法", "done": False},
            {"id": "approach_site", "text": "接近目标区域但不贸然收服", "done": False},
        ]
    return [
        {"id": "gather_info", "text": "收集地点、人物和风险情报", "done": False},
        {"id": "choose_path", "text": "选择低风险入口或准备路线", "done": False},
        {"id": "resolve_first_step", "text": "完成第一个可验证的小目标", "done": False},
    ]


def quest_template(hook: dict[str, Any]) -> dict[str, Any]:
    name = str(hook.get("name", "未命名任务"))
    summary = str(hook.get("summary") or hook.get("claim") or "")
    return {
        "quest_id": quest_id(name),
        "name": name,
        "summary": summary,
        "status": "available",
        "objectives": objective_for_hook(name, summary),
        "rewards": {
            "exp": 20,
            "coins": [5, 20],
            "items": [],
            "relationship": "相关 NPC 或势力态度可能变化",
        },
        "failure_consequences": ["时间窗口错过", "竞争者介入", "关系或声望下降"],
        "source": "adventure_hooks.json",
    }


def build_quests(world: str) -> dict[str, Any]:
    wdir = world_dir(world)
    hooks = read_json(wdir / "adventure_hooks.json", {}).get("hooks", [])
    quests = [quest_template(hook) for hook in hooks if hook.get("name")]
    output = {
        "world": world,
        "policy": "任务模板来自冒险钩子；运行时只把玩家明确接受或推进的任务写入 active_quests。",
        "quests": quests,
    }
    write_json(wdir / "quest_templates.json", output)
    manifest = load_manifest(wdir, world)
    manifest["quest_templates"] = "quest_templates.json"
    save_manifest(wdir, manifest)
    print(f"Built quest_templates.json quests={len(quests)}")
    return output


def load_quests(world: str) -> dict[str, Any]:
    wdir = world_dir(world)
    quests = read_json(wdir / "quest_templates.json", {})
    return quests if quests else build_quests(world)


def relevant_quest(player_input: str, canon_rows: list[dict[str, Any]], templates: dict[str, Any]) -> dict[str, Any] | None:
    quests = templates.get("quests", [])
    names = [row.get("name", "") for row in canon_rows if "hook" in str(row.get("type", ""))]
    for quest in quests:
        if quest.get("name") in player_input or quest.get("name") in names:
            return quest
    for quest in quests:
        if any(word in player_input for word in str(quest.get("summary", "")).split("，")[:2]):
            return quest
    return None


def activate_quest(state: dict[str, Any], quest: dict[str, Any]) -> tuple[bool, str]:
    active = state.setdefault("active_quests", [])
    if any(row.get("quest_id") == quest.get("quest_id") for row in active):
        return False, f"任务「{quest.get('name')}」已经在进行中。"
    copied = json.loads(json.dumps(quest, ensure_ascii=False))
    copied["status"] = "active"
    active.append(copied)
    return True, f"任务「{quest.get('name')}」已加入 active_quests。"


def main() -> None:
    parser = argparse.ArgumentParser(description="Build or inspect quest templates for a world.")
    parser.add_argument("--world", required=True)
    parser.add_argument("--rebuild", action="store_true")
    args = parser.parse_args()
    quests = build_quests(args.world) if args.rebuild else load_quests(args.world)
    print(json.dumps(quests, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
