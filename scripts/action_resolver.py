#!/usr/bin/env python3
from __future__ import annotations

from copy import deepcopy
from typing import Any

from combat import ENEMY_TEMPLATES, resolve_combat_round
from economy import can_afford, find_market_item, load_market, price_text
from quest_runtime import activate_quest, load_quests, relevant_quest


HIGH_RISK_WORDS = ("硬闯", "强闯", "击杀", "挑战", "偷袭", "抢夺", "潜入", "威胁", "追杀")
INFO_WORDS = ("打听", "询问", "调查", "观察", "探查", "侦查", "判断", "确认")
CULTIVATION_WORDS = ("修炼", "闭关", "突破", "炼化", "冲关")
TRADE_WORDS = ("购买", "交易", "出售", "买", "卖", "价格")
COMBAT_WORDS = ("攻击", "战斗", "切磋", "打倒", "揍", "击败", "反击")
QUEST_WORDS = ("接受", "接取", "任务", "追踪", "委托")
DECLARED_SUCCESS_WORDS = ("直接成功", "一定成功", "秒杀", "无敌", "立刻突破", "马上成仙", "随便拿走")
BLOCKING_MARKERS = ("不可", "不能", "禁止", "无法", "必须", "需要", "代价", "风险", "失败")


def classify_action(player_input: str) -> str:
    if any(word in player_input for word in DECLARED_SUCCESS_WORDS):
        return "declared_success"
    if any(word in player_input for word in TRADE_WORDS):
        return "trade"
    if any(word in player_input for word in CULTIVATION_WORDS):
        return "cultivation"
    if any(word in player_input for word in QUEST_WORDS):
        return "quest"
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


def resolve_cultivation(player_input: str, state: dict[str, Any], canon_rows: list[dict[str, Any]]) -> dict[str, Any]:
    player = state.setdefault("player", {})
    stats = player.setdefault("stats", {})
    inventory_names = {item.get("name") for item in player.get("inventory", []) if isinstance(item, dict)}
    is_breakthrough = any(word in player_input for word in ("突破", "冲关", "晋升"))
    if is_breakthrough and not inventory_names.intersection({"筑基灵液", "聚气散"}):
        return {
            "kind": "cultivation",
            "status": "partial_or_blocked",
            "verdict": "突破缺少资源和护持",
            "consequence": "你可以开始调整状态，但不能直接突破。当前缺少明确的辅助资源、护法或安全闭关环境；强行冲关会带来反噬风险。",
            "state_changes": [],
            "options": ["先购买或炼制辅助资源。", "寻找安全修炼地点。", "请可信 NPC 护法或指导。"],
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
    enemy_id = "training_dummy" if any(word in player_input for word in ("木桩", "练武", "训练", "切磋")) else "low_thug"
    result = resolve_combat_round(state, deepcopy(ENEMY_TEMPLATES[enemy_id]), None)
    return {
        "kind": "combat",
        "status": result.get("status", "resolved"),
        "verdict": "战斗回合已结算",
        "consequence": " ".join(result.get("messages", [])),
        "state_changes": ["生命、资源、经验、货币或掉落已按 combat.py 结算。"],
        "options": ["继续战斗。", "撤退并休整。", "检查战利品和状态。"],
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


def resolve_action(world: str, player_input: str, state: dict[str, Any], canon_rows: list[dict[str, Any]]) -> dict[str, Any]:
    kind = classify_action(player_input)
    all_claims = canon_text(canon_rows)
    if kind == "declared_success":
        return {
            "kind": kind,
            "status": "blocked",
            "verdict": "声明式成功无效",
            "consequence": "你不能直接声明结果；本回合只裁定你的尝试，并根据 canon、状态和风险决定后果。",
            "state_changes": [],
            "options": ["改为尝试行动。", "说明准备和资源。", "寻找可行前置条件。"],
        }
    if kind == "high_risk" and any(word in all_claims for word in BLOCKING_MARKERS):
        return {
            "kind": kind,
            "status": "partial_or_blocked",
            "verdict": "高风险行动需要前置条件",
            "consequence": "你的行动触碰了当前世界硬规则或高风险边界，不能直接成功；本回合转为试探、准备或寻找替代路径。",
            "state_changes": [],
            "options": ["收集更多情报。", "寻找协助者。", "准备撤退路线或消耗品。"],
        }
    if kind == "trade":
        return resolve_trade(world, player_input, state, canon_rows)
    if kind == "cultivation":
        return resolve_cultivation(player_input, state, canon_rows)
    if kind == "combat":
        return resolve_combat(world, player_input, state)
    if kind == "quest":
        return resolve_quest(world, player_input, state, canon_rows)
    if kind == "info":
        return resolve_info(player_input, state, canon_rows)
    return {
        "kind": kind,
        "status": "allowed",
        "verdict": "普通行动推进",
        "consequence": "行动被纳入当前场景推进，但不会跳过资源、地点、关系或实力限制。",
        "state_changes": [],
        "options": ["观察风险。", "寻找 NPC。", "转向交易、修炼或任务行动。"],
    }
