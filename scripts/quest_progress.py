#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import random
from typing import Any

from common import read_json, write_json, world_dir


PROGRESS_WORDS = ("确认", "找到", "收集", "完成", "交付", "学习", "炼制", "购买", "交换", "接近", "准备", "获得")
GENERIC_PROGRESS_WORDS = {"确认", "找到", "收集", "完成", "准备", "获得"}


def active_quests(state: dict[str, Any]) -> list[dict[str, Any]]:
    return [quest for quest in state.setdefault("active_quests", []) if isinstance(quest, dict)]


def is_background_quest(quest: dict[str, Any]) -> bool:
    return quest.get("source") == "story_arcs.json" or bool(quest.get("story_arc_id"))


def first_incomplete_objective(quest: dict[str, Any]) -> dict[str, Any] | None:
    for objective in quest.get("objectives", []):
        if not objective.get("done"):
            return objective
    return None


def quest_matches_input(quest: dict[str, Any], player_input: str) -> bool:
    objective = first_incomplete_objective(quest)
    if not objective:
        return False
    objective_text = str(objective.get("text", ""))
    tokens = [
        token.strip(" ，。；、")
        for token in objective_text.replace("、", " ").replace("，", " ").replace("。", " ").replace("；", " ").split()
    ]
    meaningful_tokens = [token for token in tokens if len(token) >= 2 and token not in GENERIC_PROGRESS_WORDS]
    if any(token in player_input for token in meaningful_tokens):
        return True
    quest_name = str(quest.get("name", ""))
    if not quest_name or quest_name not in player_input:
        return False
    target_words = [word for word in ("目标", "委托", "来源", "实力", "报酬", "期限", "违约", "撤退", "报复", "路线") if word in objective_text]
    return bool(target_words and any(word in player_input for word in target_words))


def apply_quest_rewards(state: dict[str, Any], quest: dict[str, Any]) -> list[str]:
    rewards = quest.get("rewards", {})
    player = state.setdefault("player", {})
    stats = player.setdefault("stats", {})
    currencies = player.setdefault("currencies", {"coins": 0})
    messages: list[str] = []
    exp = int(rewards.get("exp", 0))
    if exp:
        before = int(stats.get("exp", 0))
        stats["exp"] = before + exp
        messages.append(f"历练：{before} -> {stats['exp']}")
    coins_range = rewards.get("coins", [0, 0])
    coins = random.Random(quest.get("quest_id", "")).randint(int(coins_range[0]), int(coins_range[1])) if isinstance(coins_range, list) and len(coins_range) == 2 else int(coins_range or 0)
    if coins:
        before = int(currencies.get("coins", 0))
        currencies["coins"] = before + coins
        messages.append(f"金币：{before} -> {currencies['coins']}")
    for item in rewards.get("items", []):
        player.setdefault("inventory", []).append(item)
        messages.append(f"行囊新增：{item.get('name', item.get('item_id', '未知物品'))}")
    return messages


def progress_quests(state: dict[str, Any], player_input: str) -> tuple[list[str], list[str]]:
    messages: list[str] = []
    options: list[str] = []
    for quest in active_quests(state):
        if quest.get("status") != "active" or not quest_matches_input(quest, player_input):
            objective = first_incomplete_objective(quest)
            if objective and not is_background_quest(quest):
                options.append(objective.get("text", "推进任务目标"))
            continue
        objective = first_incomplete_objective(quest)
        if not objective:
            continue
        objective["done"] = True
        messages.append(f"任务「{quest.get('name')}」目标完成：{objective.get('text')}")
        next_objective = first_incomplete_objective(quest)
        if next_objective and not is_background_quest(quest):
            options.append(next_objective.get("text", "推进下一目标"))
        else:
            quest["status"] = "completed"
            messages.append(f"任务「{quest.get('name')}」完成。")
            messages.extend(apply_quest_rewards(state, quest))
    return messages, options[:4]


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect or progress quests in player_state.json.")
    parser.add_argument("--world", required=True)
    parser.add_argument("--input", default="")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    path = world_dir(args.world) / "player_state.json"
    state = read_json(path, {})
    messages, options = progress_quests(state, args.input)
    if not args.dry_run:
        write_json(path, state)
    print(json.dumps({"messages": messages, "options": options, "active_quests": state.get("active_quests", [])}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
