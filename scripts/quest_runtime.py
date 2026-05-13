#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
from typing import Any

from common import load_manifest, read_json, save_manifest, world_dir, write_json
from story_arcs import load_story_arcs


def quest_id(name: str) -> str:
    digest = hashlib.sha1(name.encode("utf-8")).hexdigest()[:10]
    return f"quest_{digest}"


QUEST_TYPE_KEYWORDS = {
    "threat": ("追杀", "悬赏", "通缉", "刺杀", "围捕", "封锁", "毒体危机", "救援", "血阵", "冲突"),
    "auction": ("拍卖", "交易", "买卖", "市场", "商会", "核价"),
    "alchemy": ("炼药", "炼丹", "寻药", "药材", "丹药", "药方", "炼药师", "丹会"),
    "special_fire": ("异火", "心炎", "妖火", "火焰", "抵御陨落心炎"),
    "faction": ("势力", "宗门", "家族", "联盟", "古族", "云岚宗", "萧门", "黑角域"),
    "exploration": ("探索", "残图", "地图", "遗迹", "山脉", "沙漠", "潜入", "查戒指", "戒中老者"),
    "training": ("修炼", "突破", "试炼", "测试", "名声", "目标"),
}


def classify_quest(name: str, summary: str) -> str:
    title = name.strip(" 「」")
    # The hook name is more reliable than a noisy long excerpt. Use it first.
    for kind in ("threat", "auction", "special_fire", "alchemy", "faction", "exploration", "training"):
        if any(word in title for word in QUEST_TYPE_KEYWORDS[kind]):
            return kind
    text = f"{title} {summary[:220]}"
    for kind in ("special_fire", "threat", "auction", "alchemy", "faction", "exploration", "training"):
        if any(word in text for word in QUEST_TYPE_KEYWORDS[kind]):
            return kind
    return "generic"


def objective_for_hook(name: str, summary: str) -> list[dict[str, Any]]:
    quest_type = classify_quest(name, summary)
    if quest_type == "threat":
        return [
            {"id": "identify_target", "text": "确认追杀目标、委托来源和对方实力", "done": False},
            {"id": "confirm_reward", "text": "问清报酬、期限、交付方式和违约后果", "done": False},
            {"id": "prepare_exit", "text": "准备撤退路线，评估是否会引来势力报复", "done": False},
        ]
    if quest_type == "auction":
        return [
            {"id": "confirm_market_window", "text": "确认拍卖或交易窗口的时间、地点和入场条件", "done": False},
            {"id": "check_price", "text": "问清目标资源的价格、真假和竞争者", "done": False},
            {"id": "prepare_bid", "text": "准备金币、抵押物、人情或替代获取路线", "done": False},
        ]
    if quest_type == "faction":
        return [
            {"id": "identify_contact", "text": "确认可接触的势力人物", "done": False},
            {"id": "offer_value", "text": "拿出情报、资源或行动价值", "done": False},
            {"id": "manage_reputation", "text": "避免触发敌对或人情债失控", "done": False},
        ]
    if quest_type == "alchemy":
        return [
            {"id": "find_materials", "text": "确认所需药材、魔核或药方来源", "done": False},
            {"id": "find_alchemist", "text": "找到可信炼药师或学习基础炼药", "done": False},
            {"id": "make_or_trade", "text": "炼制、购买或交换一份可用资源", "done": False},
        ]
    if quest_type == "special_fire":
        return [
            {"id": "collect_clue", "text": "获得异火位置或传闻的可靠线索", "done": False},
            {"id": "prepare_protection", "text": "准备护体丹药、撤退路线和护法", "done": False},
            {"id": "approach_site", "text": "接近目标区域但不贸然收服", "done": False},
        ]
    if quest_type == "exploration":
        return [
            {"id": "confirm_route", "text": "确认入口、路线、向导或地图来源", "done": False},
            {"id": "prepare_supplies", "text": "准备补给、撤退路线和最低自保手段", "done": False},
            {"id": "scout_site", "text": "先侦察外围风险，不贸然深入核心区域", "done": False},
        ]
    if quest_type == "training":
        return [
            {"id": "confirm_requirement", "text": "确认当前阶段的修炼或测试前置条件", "done": False},
            {"id": "prepare_resource", "text": "准备资源、指导、安全地点或恢复手段", "done": False},
            {"id": "attempt_low_risk", "text": "先完成一次低风险训练或小规模验证", "done": False},
        ]
    hook_name = name.strip(" 「」")
    target = hook_name if hook_name and hook_name != "未命名任务" else "这条线索"
    return [
        {"id": "ask_source", "text": f"问清「{target}」最早从谁口中传出", "done": False},
        {"id": "confirm_place", "text": f"确认「{target}」牵涉的地点、人物或交易窗口", "done": False},
        {"id": "bring_back_proof", "text": f"带回一条能交差的「{target}」结果", "done": False},
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


def quest_template_from_arc(arc: dict[str, Any]) -> dict[str, Any]:
    name = str(arc.get("name") or "未命名长期任务线")
    summary = str(arc.get("summary") or "原著反复出现的长期目标或任务循环。")
    stages = [stage for stage in arc.get("stages", []) if isinstance(stage, dict)]
    objectives = []
    for idx, stage in enumerate(stages[:4]):
        text = str(stage.get("objective") or "").strip()
        if not text:
            continue
        objectives.append(
            {
                "id": str(stage.get("stage_id") or f"stage_{idx + 1}"),
                "text": text,
                "done": False,
            }
        )
    if not objectives:
        objectives = objective_for_hook(name, summary)
    rewards = arc.get("rewards") if isinstance(arc.get("rewards"), list) else []
    risks = arc.get("risks") if isinstance(arc.get("risks"), list) else []
    return {
        "quest_id": quest_id(f"story_arc:{arc.get('arc_id') or name}"),
        "name": name,
        "summary": summary,
        "status": "available",
        "objectives": objectives,
        "rewards": {
            "exp": 30 if arc.get("recurrence") == "major_arc" else 15,
            "coins": [0, 30] if arc.get("recurrence") == "major_arc" else [3, 12],
            "items": [],
            "relationship": "根据任务线相关 NPC 或势力结算关系、人情、敌意或声望。",
            "canon_rewards": rewards[:3],
        },
        "failure_consequences": risks[:3] or ["机会窗口变化", "竞争者介入", "关系或声望下降"],
        "source": "story_arcs.json",
        "story_arc_id": arc.get("arc_id"),
        "arc_type": arc.get("type"),
        "canon_strength": arc.get("canon_strength", "low"),
        "key_terms": arc.get("key_terms", []),
    }


def build_quests(world: str) -> dict[str, Any]:
    wdir = world_dir(world)
    hooks = read_json(wdir / "adventure_hooks.json", {}).get("hooks", [])
    arcs = load_story_arcs(world).get("arcs", [])
    arc_quests = [quest_template_from_arc(arc) for arc in arcs if arc.get("name")]
    hook_quests = [quest_template(hook) for hook in hooks if hook.get("name")]
    seen: set[str] = set()
    quests: list[dict[str, Any]] = []
    for quest in [*arc_quests, *hook_quests]:
        key = str(quest.get("name") or "").lower()
        if not key or key in seen:
            continue
        seen.add(key)
        quests.append(quest)
    output = {
        "world": world,
        "policy": "任务模板优先来自 story_arcs.json 的原著长期任务线，其次来自冒险钩子；运行时只把玩家明确接受或推进的任务写入 active_quests。",
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
    if not quests:
        return None
    canon_names = [
        str(row.get("name", ""))
        for row in canon_rows
        if any(kind in str(row.get("type", "")) for kind in ("hook", "story_arc", "event_chain"))
    ]
    query_terms = [
        term
        for term in re.split(r"[\s,，。；;、/]+", player_input)
        if len(term) >= 2 and term not in {"任务", "长期任务", "长期", "一个", "有关", "想找"}
    ]
    for words in QUEST_TYPE_KEYWORDS.values():
        for word in words:
            if word in player_input and word not in query_terms:
                query_terms.append(word)
    for word in ("赚钱", "筹钱", "金币", "资源", "药材", "魔核", "人情", "情报", "长期任务", "任务线"):
        if word in player_input and word not in query_terms:
            query_terms.append(word)

    def quest_text(quest: dict[str, Any]) -> str:
        parts = [
            str(quest.get("name") or ""),
            str(quest.get("summary") or ""),
            " ".join(str(item) for item in quest.get("key_terms", []) if item),
        ]
        for objective in quest.get("objectives", [])[:4]:
            if isinstance(objective, dict):
                parts.append(str(objective.get("text") or ""))
        return " ".join(parts)

    scored: list[tuple[int, int, dict[str, Any]]] = []
    for index, quest in enumerate(quests):
        name = str(quest.get("name") or "")
        text = quest_text(quest)
        score = 0
        if name and name in player_input:
            score += 100
        if name and name in canon_names:
            score += 50
        if quest.get("source") == "story_arcs.json":
            score += 35
            if any(word in player_input for word in ("长期", "主线", "支线", "长期任务", "任务线")):
                score += 50
            if any(term and term in name for term in query_terms):
                score += 80
        elif any(word in player_input for word in ("长期", "主线", "支线", "长期任务", "任务线")):
            score -= 25
        for term in query_terms:
            if term in text:
                score += 12
            elif any(char in text for char in term if "\u4e00" <= char <= "\u9fff"):
                score += 2
        if any(name and name in row_name for row_name in canon_names):
            score += 10
        if score > 0:
            scored.append((score, -index, quest))
    if scored:
        scored.sort(reverse=True)
        return scored[0][2]
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
