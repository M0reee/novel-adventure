#!/usr/bin/env python3
from __future__ import annotations

from copy import deepcopy
from typing import Any

from ability_runtime import evaluate_ability_use
from combat import resolve_combat_round
from common import read_json, world_dir
from encounter_runtime import load_encounters, record_combat_result, start_or_get_encounter
from economy import can_afford, find_market_item, load_market, price_text
from gameplay_profile import load_gameplay_profile
from inventory_runtime import resolve_inventory_action
from location_runtime import find_location, load_locations, move_to_location
from quest_progress import progress_quests
from quest_runtime import activate_quest, load_quests, relevant_quest
from relationship_runtime import adjust_relationship, detect_target, load_relationship_rules


HIGH_RISK_WORDS = ("硬闯", "强闯", "击杀", "挑战", "偷袭", "抢夺", "潜入", "威胁", "追杀")
INFO_WORDS = ("打听", "询问", "调查", "观察", "探查", "侦查", "判断", "确认")
CULTIVATION_WORDS = ("修炼", "闭关", "突破", "炼化", "冲关")
TRADE_WORDS = ("购买", "交易", "出售", "买", "卖", "价格")
COMBAT_WORDS = ("攻击", "战斗", "切磋", "打倒", "揍", "击败", "反击")
QUEST_WORDS = ("接受", "接取", "任务", "追踪", "委托")
LOCATION_WORDS = ("前往", "去", "进入", "探索", "离开", "返回")
SOCIAL_WORDS = ("拜访", "结交", "求助", "拜师", "送礼", "道歉", "威胁", "拉拢")
INVENTORY_WORDS = ("使用", "服用", "炼化", "吞服", "装备", "佩戴", "穿戴", "换上")
DECLARED_SUCCESS_WORDS = ("直接成功", "一定成功", "秒杀", "无敌", "立刻突破", "马上成仙", "随便拿走")
BLOCKING_MARKERS = ("不可", "不能", "禁止", "无法", "必须", "需要", "代价", "风险", "失败")


def classify_action(player_input: str) -> str:
    if any(word in player_input for word in DECLARED_SUCCESS_WORDS):
        return "declared_success"
    if any(word in player_input for word in INVENTORY_WORDS):
        return "inventory"
    if any(word in player_input for word in TRADE_WORDS):
        return "trade"
    if any(word in player_input for word in SOCIAL_WORDS):
        return "social"
    if any(word in player_input for word in CULTIVATION_WORDS):
        return "cultivation"
    if any(word in player_input for word in QUEST_WORDS):
        return "quest"
    if any(word in player_input for word in LOCATION_WORDS):
        return "location"
    if any(word in player_input for word in INFO_WORDS):
        return "info"
    if any(word in player_input for word in COMBAT_WORDS):
        return "combat"
    if any(word in player_input for word in HIGH_RISK_WORDS):
        return "high_risk"
    return "general"


def canon_text(canon_rows: list[dict[str, Any]], limit: int = 10) -> str:
    return " ".join(str(row.get("claim", "")) for row in canon_rows[:limit])


def resolve_trade(world: str, player_input: str, state: dict[str, Any], canon_rows: list[dict[str, Any]]) -> dict[str, Any]:
    market = load_market(world)
    player = state.setdefault("player", {})
    item = find_market_item(player_input, canon_rows, market)
    currency = market.get("currency", "货币")
    if not item:
        return {
            "kind": "trade",
            "status": "conditional",
            "verdict": "缺少明确交易目标",
            "consequence": f"你可以先打听价格和卖家，但本回合没有锁定具体物品；当前持有 {player.get('currencies', {}).get('coins', 0)} {currency}。",
            "state_changes": [],
            "options": ["询问低阶修炼资源的价格。", "确认可靠卖家。", "查看自己能拿来交换的物品或人情。"],
        }
    affordable, coins, min_price = can_afford(player, item)
    wants_buy = any(word in player_input for word in ("买", "购买", "拿下", "买下"))
    if wants_buy and affordable:
        player.setdefault("currencies", {})["coins"] = coins - min_price
        player.setdefault("inventory", []).append({"item_id": item.get("item_id"), "name": item.get("name"), "source": "market_purchase"})
        return {
            "kind": "trade",
            "status": "resolved",
            "verdict": "交易成功",
            "consequence": f"你以最低可成交价支付 {min_price} {currency}，买下「{item['name']}」。价格区间：{price_text(item)}。",
            "state_changes": [f"{currency}：{coins} -> {coins - min_price}", f"行囊新增：{item['name']}"],
            "options": [f"确认「{item['name']}」的使用条件。", "离开交易地点避免被盯上。", "继续打听其他资源。"],
        }
    if wants_buy and not affordable:
        gap = max(0, min_price - coins)
        return {
            "kind": "trade",
            "status": "blocked",
            "verdict": "资金不足，不能购买",
            "consequence": f"「{item['name']}」参考价格为 {price_text(item)}；你当前只有 {coins} {currency}，至少还差 {gap} {currency}。本回合只能获得价格与获取路线，不能直接买下。",
            "state_changes": [],
            "options": item.get("alternate_acquisition", [])[:4] or ["接取委托赚钱。", "寻找替代资源。", "向 NPC 求助。"],
        }
    return {
        "kind": "trade",
        "status": "allowed",
        "verdict": "价格情报获得",
        "consequence": f"你打听到「{item['name']}」的参考价格：{price_text(item)}。购买条件：{'；'.join(item.get('purchase_conditions', [])[:3])}。你当前有 {coins} {currency}，{'具备最低购买能力' if affordable else '暂时买不起'}。",
        "state_changes": ["获得交易情报。"],
        "options": ([f"购买「{item['name']}」。"] if affordable else item.get("alternate_acquisition", [])[:2]) + ["继续打听卖家可信度。", "寻找更便宜的替代品。"],
    }


def breakthrough_resource_names(world: str, canon_rows: list[dict[str, Any]]) -> list[str]:
    gameplay = load_gameplay_profile(world)
    entities = gameplay.get("canon_entities", {})
    names = [str(name) for name in entities.get("market_items", []) if str(name)]
    if not names:
        names = [str(name) for name in entities.get("items", []) if str(name)]
    for row in canon_rows[:12]:
        if row.get("type") in {"item", "playable_item"} and row.get("name"):
            name = str(row["name"])
            if name not in names:
                names.append(name)
    return names[:6]


def resolve_cultivation(world: str, player_input: str, state: dict[str, Any], canon_rows: list[dict[str, Any]]) -> dict[str, Any]:
    player = state.setdefault("player", {})
    stats = player.setdefault("stats", {})
    inventory_names = {item.get("name") for item in player.get("inventory", []) if isinstance(item, dict)}
    is_breakthrough = any(word in player_input for word in ("突破", "冲关", "晋升"))
    gameplay = load_gameplay_profile(world)
    mechanisms = gameplay.get("mechanisms", {})
    needs_consumable = bool(mechanisms.get("consumable_crafting", {}).get("enabled"))
    resource_names = breakthrough_resource_names(world, canon_rows)
    has_support = bool(inventory_names.intersection(resource_names)) if resource_names else False
    if is_breakthrough and needs_consumable and not has_support:
        resource_hint = "、".join(resource_names[:3]) if resource_names else "该世界 canon 支持的辅助资源"
        return {
            "kind": "cultivation",
            "status": "partial_or_blocked",
            "verdict": "突破缺少资源和护持",
            "consequence": f"你可以开始调整状态，但不能直接突破。当前缺少明确的辅助资源、护法或安全闭关环境；可优先寻找：{resource_hint}。强行冲关会带来 canon 已支持的反噬或失败代价。",
            "state_changes": [],
            "options": [f"先获取「{name}」。" for name in resource_names[:3]] + ["寻找安全修炼地点。", "请可信 NPC 护法或指导。"],
        }
    gain = 5 if not is_breakthrough else 15
    before = int(stats.get("exp", 0))
    stats["exp"] = before + gain
    return {
        "kind": "cultivation",
        "status": "resolved",
        "verdict": "修炼获得稳定进展",
        "consequence": f"你按当前境界的可承受范围修炼，没有跳过硬设定边界；本回合获得 {gain} 点历练。",
        "state_changes": [f"历练：{before} -> {stats['exp']}"],
        "options": ["继续稳步修炼。", "寻找辅助资源提高效率。", "打听突破条件。"],
    }


def resolve_combat(world: str, player_input: str, state: dict[str, Any]) -> dict[str, Any]:
    boundary_result = evaluate_ability_use(world, player_input, state)
    encounters = load_encounters(world)
    enemy, started = start_or_get_encounter(encounters, player_input)
    result = resolve_combat_round(state, deepcopy(enemy), None)
    encounter_changes = record_combat_result(encounters, result.get("enemy", enemy), result.get("messages", []))
    boundary_text = f"{boundary_result.get('consequence')} " if boundary_result else ""
    boundary_changes = boundary_result.get("state_changes", []) if boundary_result else []
    return {
        "kind": "combat",
        "status": result.get("status", "resolved"),
        "verdict": "战斗回合已结算" if not started else "遭遇开始并完成首轮结算",
        "consequence": boundary_text + " ".join(result.get("messages", [])),
        "state_changes": [*boundary_changes, "生命、资源、经验、货币或掉落已按 combat.py 结算。", *encounter_changes],
        "options": (boundary_result.get("options", []) if boundary_result else []) + ["继续战斗。", "撤退并休整。", "检查战利品和状态。"],
        "runtime_files": {"encounter_state.json": encounters},
    }


def resolve_quest(world: str, player_input: str, state: dict[str, Any], canon_rows: list[dict[str, Any]]) -> dict[str, Any]:
    templates = load_quests(world)
    quest = relevant_quest(player_input, canon_rows, templates)
    if not quest:
        return {
            "kind": "quest",
            "status": "conditional",
            "verdict": "缺少明确任务目标",
            "consequence": "你有接取任务的意图，但当前没有锁定具体钩子；先确认目标、期限、风险和奖励。",
            "state_changes": [],
            "options": [q.get("name", "未知任务") for q in templates.get("quests", [])[:4]],
        }
    changed, message = activate_quest(state, quest)
    return {
        "kind": "quest",
        "status": "resolved" if changed else "allowed",
        "verdict": "任务已确认" if changed else "任务继续推进",
        "consequence": f"{message} 第一目标：{quest.get('objectives', [{}])[0].get('text', '确认下一步目标')}",
        "state_changes": [message] if changed else [],
        "options": [obj.get("text", "") for obj in quest.get("objectives", [])[:4]],
    }


def resolve_info(player_input: str, state: dict[str, Any], canon_rows: list[dict[str, Any]]) -> dict[str, Any]:
    names = [row.get("name") for row in canon_rows[:4] if row.get("name")]
    target = "、".join(names) if names else "当前局势"
    return {
        "kind": "info",
        "status": "allowed",
        "verdict": "信息行动可执行但消耗时间",
        "consequence": f"你围绕 {target} 收集情报，获得更清晰的风险边界；本回合不直接取得物品或突破。",
        "state_changes": ["获得情报。"],
        "options": ["继续追问价格、位置或人物关系。", "把情报转化为任务。", "选择一个低风险行动入口。"],
    }


def resolve_location(world: str, player_input: str, state: dict[str, Any], canon_rows: list[dict[str, Any]]) -> dict[str, Any]:
    locations = load_locations(world)
    location = find_location(player_input, canon_rows, locations)
    if not location:
        return {
            "kind": "location",
            "status": "conditional",
            "verdict": "缺少明确地点",
            "consequence": "你有移动或探索意图，但没有锁定可验证地点；先确认路线、入口条件和风险。",
            "state_changes": [],
            "options": [row.get("name", "") for row in locations.get("locations", [])[:4]],
        }
    changes = move_to_location(state, location)
    return {
        "kind": "location",
        "status": "resolved",
        "verdict": "地点变更已结算",
        "consequence": f"你转向「{location.get('name')}」。当地风险为 {location.get('risk_level')}；可行动作包括：{'、'.join(location.get('available_actions', [])[:4])}。",
        "state_changes": changes,
        "options": location.get("available_actions", [])[:4],
    }


def resolve_social(world: str, player_input: str, state: dict[str, Any], canon_rows: list[dict[str, Any]]) -> dict[str, Any]:
    rules = load_relationship_rules(world)
    target = detect_target(player_input, canon_rows, rules)
    if not target:
        return {
            "kind": "social",
            "status": "conditional",
            "verdict": "缺少明确互动对象",
            "consequence": "你需要先确认要接触的 NPC 或势力；不同对象会影响好感、敌意、人情债和资源渠道。",
            "state_changes": [],
            "options": [row.get("name", "") for row in (rules.get("npcs", []) + rules.get("factions", []))[:4]],
        }
    delta = 3
    if any(word in player_input for word in ("威胁", "挑衅", "勒索")):
        delta = -8
    elif any(word in player_input for word in ("送礼", "求助", "拜师", "结交")):
        delta = 5
    change = adjust_relationship(state, target, delta, f"行动：{player_input[:60]}")
    motives = read_json(world_dir(world) / "npc_motives.json", {}).get("npcs", [])
    motive = next((row for row in motives if row.get("npc") == target), {})
    motive_note = ""
    motive_options: list[str] = []
    if motive:
        leverage = "；".join(motive.get("leverage", [])[:2])
        boundaries = "；".join(motive.get("boundaries", [])[:2])
        motive_note = f" 对方可被打动的筹码：{leverage or '合理利益或可信关系'}；底线：{boundaries or '不会无条件满足要求'}。"
        motive_options = []
        for option in motive.get("player_hooks", [])[:3]:
            option = str(option).strip()
            if option and not any(verb in option for verb in ("请求", "提出", "交换", "询问", "完成", "帮助", "打听", "合作", "确认")):
                option = f"围绕「{option}」提出具体请求"
            if option:
                motive_options.append(option if option.endswith(("。", "！", "？")) else f"{option}。")
        motive_options.extend(["提出具体交换条件。", "询问对方不能接受的底线。"])
    return {
        "kind": "social",
        "status": "resolved",
        "verdict": "关系已更新",
        "consequence": f"你与「{target}」产生一次明确互动。关系变化会影响后续情报、交易、任务和敌意。{motive_note}",
        "state_changes": [change] if change else [],
        "options": (motive_options or ["继续沟通。", "提出交易或任务请求。", "暂时退开避免关系恶化。"])[:4],
    }


def attach_quest_progress(state: dict[str, Any], player_input: str, result: dict[str, Any]) -> dict[str, Any]:
    messages, options = progress_quests(state, player_input)
    if messages:
        result.setdefault("state_changes", []).extend(messages)
        result.setdefault("options", []).extend(options)
    return result


def resolve_action(world: str, player_input: str, state: dict[str, Any], canon_rows: list[dict[str, Any]]) -> dict[str, Any]:
    kind = classify_action(player_input)
    all_claims = canon_text(canon_rows)
    ability_result = evaluate_ability_use(world, player_input, state)
    if kind == "declared_success":
        return {
            "kind": kind,
            "status": "blocked",
            "verdict": "声明式成功无效",
            "consequence": "你不能直接声明结果；本回合只裁定你的尝试，并根据 canon、状态和风险决定后果。",
            "state_changes": [],
            "options": ["改为尝试行动。", "说明准备和资源。", "寻找可行前置条件。"],
        }
    if ability_result and ability_result.get("status") in {"blocked", "partial_or_blocked"}:
        return attach_quest_progress(state, player_input, ability_result)
    if kind == "high_risk" and any(word in all_claims for word in BLOCKING_MARKERS):
        return {
            "kind": kind,
            "status": "partial_or_blocked",
            "verdict": "高风险行动需要前置条件",
            "consequence": "你的行动触碰了当前世界硬规则或高风险边界，不能直接成功；本回合转为试探、准备或寻找替代路径。",
            "state_changes": [],
            "options": ["收集更多情报。", "寻找协助者。", "准备撤退路线或消耗品。"],
        }
    if ability_result and kind == "general":
        return attach_quest_progress(state, player_input, ability_result)
    if kind == "trade":
        return attach_quest_progress(state, player_input, resolve_trade(world, player_input, state, canon_rows))
    if kind == "cultivation":
        return attach_quest_progress(state, player_input, resolve_cultivation(world, player_input, state, canon_rows))
    if kind == "combat":
        return attach_quest_progress(state, player_input, resolve_combat(world, player_input, state))
    if kind == "quest":
        return resolve_quest(world, player_input, state, canon_rows)
    if kind == "inventory":
        return attach_quest_progress(state, player_input, resolve_inventory_action(world, state, player_input) or {
            "kind": "inventory",
            "status": "conditional",
            "verdict": "没有可执行的物品动作",
            "consequence": "请明确要使用、服用、炼化或装备的物品名称。",
            "state_changes": [],
            "options": ["查看行囊。", "明确物品名称。", "寻找物品用途。"],
        })
    if kind == "location":
        return attach_quest_progress(state, player_input, resolve_location(world, player_input, state, canon_rows))
    if kind == "social":
        return attach_quest_progress(state, player_input, resolve_social(world, player_input, state, canon_rows))
    if kind == "info":
        return attach_quest_progress(state, player_input, resolve_info(player_input, state, canon_rows))
    return {
        "kind": kind,
        "status": "allowed",
        "verdict": "普通行动推进",
        "consequence": "行动被纳入当前场景推进，但不会跳过资源、地点、关系或实力限制。",
        "state_changes": [],
        "options": ["观察风险。", "寻找 NPC。", "转向交易、修炼或任务行动。"],
    }
