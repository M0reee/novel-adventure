#!/usr/bin/env python3
from __future__ import annotations

from copy import deepcopy
from typing import Any

from ability_runtime import evaluate_ability_use
from combat import resolve_combat_round
from common import read_json, world_dir
from encounter_runtime import default_encounter_state, record_combat_result, start_or_get_encounter
from economy import can_afford, find_market_item, load_market, price_text
from economy_runtime import record_market_check, record_purchase
from gameplay_profile import load_gameplay_profile
from inventory_runtime import resolve_inventory_action
from location_runtime import find_location, load_locations, move_to_location
from quest_progress import progress_quests, quest_matches_input
from quest_runtime import activate_quest, load_quests, relevant_quest
from relationship_runtime import adjust_relationship, detect_target, load_relationship_rules
from skill_tree import learn_skill


HIGH_RISK_WORDS = ("硬闯", "强闯", "击杀", "挑战", "偷袭", "抢夺", "潜入", "威胁", "追杀")
INFO_WORDS = ("打听", "询问", "调查", "观察", "探查", "侦查", "判断", "确认")
CULTIVATION_WORDS = ("修炼", "闭关", "突破", "炼化", "冲关")
TRADE_WORDS = ("购买", "交易", "出售", "买", "卖", "价格")
COMBAT_WORDS = ("攻击", "战斗", "切磋", "打倒", "揍", "击败", "反击")
QUEST_WORDS = ("接受", "接取", "任务", "追踪", "委托")
EARN_WORDS = ("赚钱", "赚点", "挣点", "挣金币", "报酬", "佣金", "跑腿")
LOCATION_WORDS = ("前往", "去", "进入", "探索", "离开", "返回")
SOCIAL_WORDS = ("拜访", "结交", "求助", "拜师", "送礼", "道歉", "威胁", "拉拢", "护法", "指导", "指点", "打好关系", "搭话")
SOCIAL_EXCHANGE_WORDS = ("筹码", "承诺", "交换", "人情", "报酬", "开价", "条件", "底线", "护法", "指导", "指点", "支付", "金币")
SOCIAL_TARGET_WORDS = ("炼药师", "药老", "导师", "老师", "管事", "练武场管事", "伙计", "摊主", "低阶少年", "少年", "对方", "那位", "可信 NPC", "NPC")
SOCIAL_INQUIRY_WORDS = ("询问", "请教", "请问", "确认", "打听", "问清", "问")
SERVICE_QUEST_WORDS = ("跑腿", "核价", "小活", "换情报", "换取情报", "基础情报", "送信", "传话", "搬运", "沙袋", "清扫", "器械", "杂务", "旁听资格", "旁听名额", "旁听", "吐纳")
INVENTORY_WORDS = ("使用", "服用", "炼化", "吞服", "装备", "佩戴", "穿戴", "换上")
DECLARED_SUCCESS_WORDS = ("直接成功", "一定成功", "秒杀", "无敌", "立刻突破", "马上成仙", "随便拿走")
BLOCKING_MARKERS = ("不可", "不能", "禁止", "无法", "必须", "需要", "代价", "风险", "失败")
RESOURCE_RELEVANCE_WORDS = ("突破", "冲关", "修炼", "炼药", "药材", "丹", "灵液", "魔核", "药方", "辅助", "恢复", "护体")
RESOURCE_NAME_WORDS = ("聚气散", "灵液", "丹", "魔核", "药方", "药材", "药剂", "灵石", "晶核", "魂环", "魂骨", "材料", "草", "花")
BAD_RESOURCE_NAMES = {"卷轴", "丹药", "药材", "物品", "资源", "这种等级", "听得药", "不会", "没有理会", "炼药", "炼丹", "炼药师", "纳戒"}
BAD_RESOURCE_FRAGMENTS = ("。", "，", "、", "：", "；", "?", "？", "！", "!", "听得", "什么", "对方", "当前", "你的", "炼制")
BAD_INFO_NAMES = {"不会", "没有理会", "这种等级", "听得药", "当前", "对方", "什么", "卷轴"}
BAD_SOCIAL_TARGETS = {"不会", "没有理会", "这种等级", "听得药", "当前", "对方", "什么", "卷轴", "不知", "方才", "缓缓地", "所以", "那一", "轻声"}


def naturalize_task_text(text: str) -> str:
    replacements = {
        "收集地点、人物和风险情报": "问清线索最早从谁口中传出",
        "选择低风险入口或准备路线": "先问清入口、报酬和撤退路线",
        "完成第一个可验证的小目标": "带回一条能交差的消息、价格或人物行踪",
        "选择一个低风险行动入口": "从问价、送信或带路这种低风险小事开始",
    }
    output = str(text or "")
    for bad, good in replacements.items():
        output = output.replace(bad, good)
    return output


def classify_action(player_input: str) -> str:
    if any(word in player_input for word in DECLARED_SUCCESS_WORDS):
        return "declared_success"
    if any(word in player_input for word in ("辅助资源", "资源来源", "提高效率", "低阶药材", "药液价格")):
        return "info"
    if any(word in player_input for word in ("观察", "判断", "确认风险", "看清")):
        return "info"
    if any(word in player_input for word in ("复盘", "练习", "吐纳", "运转斗气", "低风险练习")):
        return "cultivation"
    if any(word in player_input for word in ("如何进入", "怎么进入", "进入练武场", "进练武场")) and any(word in player_input for word in SOCIAL_TARGET_WORDS):
        return "social"
    if any(word in player_input for word in SOCIAL_EXCHANGE_WORDS) and any(word in player_input for word in SOCIAL_TARGET_WORDS):
        return "social"
    if any(word in player_input for word in SOCIAL_INQUIRY_WORDS) and any(word in player_input for word in SOCIAL_TARGET_WORDS):
        return "social"
    if any(word in player_input for word in SERVICE_QUEST_WORDS):
        return "quest"
    if any(word in player_input for word in INVENTORY_WORDS):
        return "inventory"
    if any(word in player_input for word in TRADE_WORDS):
        return "trade"
    if any(word in player_input for word in SOCIAL_WORDS):
        return "social"
    if any(word in player_input for word in CULTIVATION_WORDS):
        return "cultivation"
    if any(word in player_input for word in EARN_WORDS):
        return "quest"
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


def mentioned_trade_resource(player_input: str) -> str:
    for name in sorted(RESOURCE_NAME_WORDS, key=len, reverse=True):
        if name in BAD_RESOURCE_NAMES:
            continue
        if name in player_input:
            return name
    return ""


def resolve_trade(world: str, player_input: str, state: dict[str, Any], canon_rows: list[dict[str, Any]]) -> dict[str, Any]:
    market = load_market(world)
    player = state.setdefault("player", {})
    item = find_market_item(player_input, canon_rows, market)
    currency = market.get("currency", "货币")
    if not item:
        resource = mentioned_trade_resource(player_input)
        if resource:
            record_market_check(world, resource, int(state.get("meta", {}).get("turn", 0)))
            return {
                "kind": "trade",
                "status": "allowed",
                "verdict": "资源询价与验真",
                "consequence": f"你锁定要打听的是「{resource}」。它暂未进入稳定可购买清单，本回合只能核实来源、真假风险和大致行情，不能直接视为已买到；当前持有 {player.get('currencies', {}).get('coins', 0)} {currency}。",
                "state_changes": [f"获得资源情报：{resource}的来源、价格和真假风险需要继续核实。"],
                "options": [f"询问「{resource}」的可靠卖家。", f"比较「{resource}」与同类低阶资源的价格。", "找可信 NPC 验证真假风险。"],
            }
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
        record_purchase(world, str(item.get("name", "")), int(state.get("meta", {}).get("turn", 0)))
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


def resolve_skill_learning(world: str, player_input: str, state: dict[str, Any]) -> dict[str, Any] | None:
    result = learn_skill(world, state, player_input)
    if result is None:
        return None
    if not result.get("ok"):
        return {
            "kind": "cultivation",
            "status": "blocked",
            "verdict": "技能学习条件不足",
            "consequence": str(result.get("reason", "当前条件不足，不能直接学会。")),
            "state_changes": [],
            "options": ["先训练基础属性。", "寻找导师确认前置条件。", "换一个低阶技能。"],
        }
    skill = result.get("skill", {})
    return {
        "kind": "cultivation",
        "status": "resolved",
        "verdict": "技能已习得",
        "consequence": f"你把「{skill.get('name')}」整理成可实战使用的技能。以后战斗结算会按它的消耗、威力、命中和效果计算。",
        "state_changes": [f"习得技能：{skill.get('name')}"],
        "options": [f"用「{skill.get('name')}」进行一次低风险试招。", "查看当前技能。", "继续修炼基础属性。"],
    }


def breakthrough_resource_names(world: str, canon_rows: list[dict[str, Any]]) -> list[str]:
    def normalize(name: str) -> str:
        stripped = name.strip(" 「」《》[]()（）")
        while stripped[:1] in {"这", "那", "此", "该"}:
            stripped = stripped[1:]
        if stripped.endswith("魔核") and stripped != "魔核":
            return "合适阶别的魔核"
        return stripped

    def clean(name: str, context: str = "") -> str:
        normalized = normalize(name)
        if not normalized or normalized in BAD_RESOURCE_NAMES:
            return ""
        if len(normalized) > 12:
            return ""
        if any(fragment in normalized for fragment in BAD_RESOURCE_FRAGMENTS):
            return ""
        if not any(word in normalized for word in RESOURCE_NAME_WORDS):
            return ""
        combined = f"{normalized} {context}"
        if not any(word in combined for word in RESOURCE_RELEVANCE_WORDS):
            return ""
        return normalized

    names: list[str] = []
    market = load_market(world)
    for item in market.get("items", []):
        requirements = item.get("use_requirements", [])
        requirement_text = " ".join(str(row) for row in requirements) if isinstance(requirements, list) else str(requirements or "")
        name = clean(str(item.get("name", "")), str(item.get("summary", "")) + " " + requirement_text)
        if name and name not in names:
            names.append(name)

    gameplay = load_gameplay_profile(world)
    entities = gameplay.get("canon_entities", {})
    if not names:
        for raw_name in [*entities.get("market_items", []), *entities.get("items", [])]:
            name = clean(str(raw_name))
            if name and name not in names:
                names.append(name)
    for row in canon_rows[:12]:
        if row.get("type") in {"item", "playable_item"} and row.get("name"):
            name = clean(str(row["name"]), str(row.get("claim", "")))
            if name not in names:
                names.append(name)
    return names[:4]


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
        resource_hint = f"{resource_names[0]}或同类低阶辅助资源" if resource_names else "低阶药材、修炼耗材，或由可信 NPC 确认适用的辅助资源"
        resource_options = [f"向可信 NPC 确认当前最现实的辅助资源（可先问「{resource_names[0]}」）。"] if resource_names else []
        if not resource_options:
            resource_options = ["向可信 NPC 确认可用的辅助资源。", "去交易点询问低阶药材或修炼耗材。"]
        return {
            "kind": "cultivation",
            "status": "partial_or_blocked",
            "verdict": "突破缺少辅助资源",
            "consequence": f"你可以开始调整状态，但不能直接突破。当前缺少明确的辅助资源；可优先寻找：{resource_hint}。护法、指导或安全闭关环境能提高成功率，但不是替代资源的硬条件。强行冲关会带来 canon 已支持的反噬或失败代价。",
            "state_changes": [],
            "options": resource_options + ["寻找安全修炼地点。", "请可信 NPC 护法或指导。"],
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
    encounters = state.setdefault("runtime", {}).setdefault("encounter_state", default_encounter_state(world))
    enemy, started = start_or_get_encounter(encounters, player_input)
    active_round = int((encounters.get("active") or {}).get("round", 0)) + 1
    enemy["round"] = active_round
    skill_id = None
    for skill in state.get("player", {}).get("skills", []):
        if isinstance(skill, dict) and skill.get("name") and str(skill["name"]) in player_input:
            skill_id = str(skill.get("skill_id"))
            break
    result = resolve_combat_round(state, deepcopy(enemy), skill_id)
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
        "runtime_files": {},
    }


def resolve_quest(world: str, player_input: str, state: dict[str, Any], canon_rows: list[dict[str, Any]]) -> dict[str, Any]:
    templates = load_quests(world)
    if "推进当前任务" in player_input:
        return {
            "kind": "quest",
            "status": "allowed",
            "verdict": "当前任务推进",
            "consequence": "你按当前任务的下一目标推进；本回合不会因为目标文本里的关键词而误接新的任务。",
            "state_changes": [],
            "options": [],
        }
    if any(
        isinstance(quest, dict)
        and quest.get("status") == "active"
        and quest.get("source") != "story_arcs.json"
        and quest_matches_input(quest, player_input)
        for quest in state.get("active_quests", [])
    ):
        return {
            "kind": "quest",
            "status": "allowed",
            "verdict": "已有任务推进",
            "consequence": "你继续处理已经接下的任务；本回合不会因为目标文本里的关键词误接另一条任务线。",
            "state_changes": [],
            "options": [],
        }
    if "午后旁听基础吐纳" in player_input or "旁听基础吐纳" in player_input:
        quest = next((row for row in state.get("active_quests", []) if isinstance(row, dict) and row.get("quest_id") == "quest_training_ground_sandbag"), None)
        objectives = quest.get("objectives", []) if quest else []
        reported = any(obj.get("id") == "report_steward" and obj.get("done") for obj in objectives)
        if not reported:
            if "回报" in player_input or "确认午后旁听名额" in player_input or "确认名额" in player_input:
                return {
                    "kind": "quest",
                    "status": "partial_or_blocked",
                    "verdict": "回报可完成，旁听需等确认后执行",
                    "consequence": "你可以先把搬运沙袋的结果交给练武场管事确认；但旁听资格必须等管事验收后才生效，本回合不能把回报和正式旁听压缩成一次自动完成。",
                    "state_changes": [],
                    "options": [
                        "午后旁听基础吐纳，不插话、不逾矩",
                        "说明已经完成搬运沙袋，请管事验收",
                        "如果名额已满，询问是否还能补做一件杂务",
                    ],
                }
            return {
                "kind": "quest",
                "status": "blocked",
                "verdict": "旁听前置未完成",
                "consequence": "你已经完成杂务，但还没有向练武场管事回报并确认名额。直接去旁听会被拦下，必须先把沙袋搬运结果交给管事确认。",
                "state_changes": [],
                "options": [
                    "向练武场管事回报，确认午后旁听名额",
                    "说明已经完成搬运沙袋，请管事验收",
                    "如果名额已满，询问是否还能补做一件杂务",
                ],
            }
        return {
            "kind": "quest",
            "status": "resolved",
            "verdict": "旁听资格已使用",
            "consequence": (
                "午后，管事让你站在练武场边缘，不许插话。你照做，盯着前排少年吐纳时的肩背起伏和收息节奏，"
                "第一次把“斗气运转”从传闻变成能模仿的细节。你没有立刻变强，但知道了基础吐纳不能急冲，"
                "要先稳住呼吸、经脉承受和姿势。"
            ),
            "state_changes": ["午后旁听基础吐纳。"],
            "options": [
                "回到场外复盘吐纳节奏，尝试一次低风险练习。",
                "向练武场管事道谢，询问下次还能做什么杂务。",
                "去坊市打听低阶药材或药液价格。",
            ],
        }
    if any(word in player_input for word in ("搬运", "沙袋", "清扫", "器械", "杂务", "旁听资格", "旁听名额")):
        flags = state.setdefault("scene_flags", {})
        if "沙袋" in player_input or "搬运" in player_input:
            flags["training_ground_chore"] = "搬运沙袋"
            task = "搬运沙袋"
            detail = "沙袋堆在练武场侧门旁，重量不算离谱，但要来回搬完三趟，动作慢了会被后面的少年抢名额。"
            reward = "午后旁听半个时辰基础吐纳"
        else:
            flags["training_ground_chore"] = "清扫器械"
            task = "清扫器械"
            detail = "器械架上沾着木屑和汗渍，清扫时能近距离观察萧家少年如何站桩、发力和收息。"
            reward = "午后旁听半个时辰基础吐纳，并额外观察基础训练动作"
        quest = {
            "quest_id": f"quest_training_ground_{'sandbag' if '沙袋' in player_input or '搬运' in player_input else 'cleaning'}",
            "name": f"练武场杂务：{task}",
            "summary": f"完成{task}，换取{reward}。",
            "status": "available",
            "objectives": [
                {"id": "finish_chore", "text": f"按管事要求完成{task}", "done": False},
                {"id": "report_steward", "text": "向练武场管事回报，确认午后旁听名额", "done": False},
                {"id": "attend_basic_breathing", "text": "午后旁听基础吐纳，不插话、不逾矩", "done": False},
            ],
            "rewards": {"exp": 8, "coins": [0, 0], "items": [], "relationship": "练武场管事关系小幅提升，获得旁听资格"},
            "failure_consequences": ["旁听名额被别人拿走", "练武场管事关系下降"],
            "source": "opening_scene",
        }
        changed, message = activate_quest(state, quest)
        return {
            "kind": "quest",
            "status": "resolved" if changed else "allowed",
            "verdict": "练武场杂务已接下",
            "consequence": f"{detail} 你接下「{task}」，这不是直接进入练武场修炼，而是先用可验证的贡献换一次旁听资格。{message}",
            "state_changes": [message, f"当前杂务：{task}", f"潜在奖励：{reward}"] if changed else [f"继续推进杂务：{task}"],
            "options": [obj["text"] for obj in quest["objectives"]],
        }
    if any(word in player_input for word in SERVICE_QUEST_WORDS) and any(word in player_input for word in ("跑腿", "核价", "药材", "摊", "商队", "账单", "报酬", "送信", "传话", "小活")):
        quest = {
            "quest_id": "quest_service_alchemist_price_check",
            "name": "炼药师跑腿核价",
            "summary": "为炼药师跑腿或核价，换取突破辅助资源的基础情报。",
            "status": "available",
            "objectives": [
                {"id": "confirm_stalls", "text": "确认需要核价的药材摊或商队", "done": False},
                {"id": "compare_prices", "text": "跑三处摊位核对低阶药材或辅助资源价格", "done": False},
                {"id": "report_back", "text": "回报炼药师，换取突破辅助资源来源", "done": False},
            ],
            "rewards": {"exp": 10, "coins": [3, 8], "items": [], "relationship": "炼药师关系提升，并获得资源来源情报"},
            "failure_consequences": ["价格情报过期", "炼药师信任下降"],
            "source": "runtime_service_quest",
        }
        changed, message = activate_quest(state, quest)
        return {
            "kind": "quest",
            "status": "resolved" if changed else "allowed",
            "verdict": "低风险小活已确认" if changed else "低风险小活继续推进",
            "consequence": f"{message} 这不是直接获得丹药，而是先用跑腿或核价换取可信来源。",
            "state_changes": [message] if changed else [],
            "options": [obj["text"] for obj in quest["objectives"]],
        }
    quest = relevant_quest(player_input, canon_rows, templates)
    if not quest and any(word in player_input for word in EARN_WORDS):
        location = state.get("meta", {}).get("current_location", "当前位置")
        return {
            "kind": "quest",
            "status": "conditional",
            "verdict": "需要先锁定带报酬的小活",
            "consequence": f"你不能凭空获得金币。在{location}，最稳妥的是先找可验证的小委托：跑腿、盯梢、核价、送口信或带回一条消息。报酬要在接活前问清，完成后再结算。",
            "state_changes": [],
            "options": [
                "去药材摊或商队问有没有跑腿核价的小活。",
                "找守卫或杂役打听是否需要盯梢、送信。",
                "先确认报酬、期限和失败后果，再接活。",
                "如果报酬太低，改为交换情报或人情。",
            ],
        }
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
    objectives = [naturalize_task_text(obj.get("text", "")) for obj in quest.get("objectives", [])[:4]]
    first_objective = objectives[0] if objectives else "确认下一步目标"
    return {
        "kind": "quest",
        "status": "resolved" if changed else "allowed",
        "verdict": "任务已确认" if changed else "任务继续推进",
        "consequence": f"{message} 第一目标：{first_objective}",
        "state_changes": [message] if changed else [],
        "options": objectives,
    }


def resolve_info(player_input: str, state: dict[str, Any], canon_rows: list[dict[str, Any]]) -> dict[str, Any]:
    if any(word in player_input for word in ("辅助资源", "资源来源", "提高效率", "低阶药材", "药液价格")):
        flags = state.setdefault("scene_flags", {})
        flags["seeking_cultivation_aids"] = True
        return {
            "kind": "info",
            "status": "allowed",
            "verdict": "辅助资源线索已明确",
            "consequence": (
                "你没有凭空拿到丹药，而是把刚学到的吐纳问题拆成资源需求：低阶药液、温和药材、"
                "稳定练习地点，以及懂价格的人。练武场外能问到的最稳路线，是去坊市比较低阶药材价格，"
                "或找药材伙计接核价跑腿，用报酬和消息换第一批辅助资源。"
            ),
            "state_changes": ["获得线索：坊市低阶药材、药液价格、药材伙计跑腿。"],
            "options": [
                "去坊市打听低阶药材和药液价格。",
                "找药材伙计询问是否需要核价跑腿，并问清报酬。",
                "向练武场管事确认哪些药液适合斗之气低段。",
                "先继续稳步练习，等有金币再考虑药液。",
            ],
        }
    names: list[str] = []
    for row in canon_rows[:8]:
        name = str(row.get("name", "")).strip()
        if not name or name in BAD_INFO_NAMES or len(name) > 18 or any(mark in name for mark in ("。", "，", "；", "：", "\n")):
            continue
        if name not in names:
            names.append(name)
        if len(names) >= 3:
            break
    target = "、".join(names) if names else str(state.get("meta", {}).get("current_location") or "当前局势")
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


def relationship_score(state: dict[str, Any], target: str) -> int:
    for row in state.get("relationships", []):
        if row.get("target") == target:
            return int(row.get("score", 0) or 0)
    return 0


def fallback_social_target(player_input: str, state: dict[str, Any]) -> str:
    relationships = [row for row in state.get("relationships", []) if isinstance(row, dict) and row.get("target")]
    for row in relationships:
        target = str(row.get("target"))
        if target in player_input:
            return target
    if "炼药师" in player_input:
        return "炼药师"
    if "药老" in player_input:
        return "药老"
    if "练武场管事" in player_input or "管事" in player_input:
        return "练武场管事"
    if "药材伙计" in player_input or "伙计" in player_input:
        return "药材伙计"
    if "药材摊主" in player_input or "摊主" in player_input:
        return "药材摊主"
    if "低阶少年" in player_input:
        return "低阶少年"
    if any(word in player_input for word in ("对方", "那位", "可信 NPC", "NPC")):
        candidates = [row for row in relationships if str(row.get("target")) not in {"不会", "没有理会"}]
        candidates.sort(key=lambda row: int(row.get("score", 0) or 0), reverse=True)
        if candidates:
            return str(candidates[0].get("target"))
    if any(word in player_input for word in ("指点", "护法", "指导", "支付", "金币", "筹码", "承诺")):
        candidates = [row for row in relationships if str(row.get("target")) not in {"不会", "没有理会"}]
        candidates.sort(key=lambda row: int(row.get("score", 0) or 0), reverse=True)
        if candidates:
            return str(candidates[0].get("target"))
    return ""


def player_leverage(player_input: str, state: dict[str, Any], target: str) -> tuple[list[str], list[str]]:
    player = state.setdefault("player", {})
    coins = int(player.setdefault("currencies", {}).get("coins", 0) or 0)
    score = relationship_score(state, target)
    leverage: list[str] = []
    changes: list[str] = []
    if coins > 0 and any(word in player_input for word in ("金币", "钱", "付款", "报酬", "开价")):
        leverage.append(f"可支付最多 {coins} 金币")
    if score > 0:
        leverage.append(f"已有关系基础 {score}")
    if any(word in player_input for word in ("人情", "跑腿", "核价", "传话", "帮忙", "承诺")):
        leverage.append("可提供跑腿、核价、传话或后续承诺")
    if any(word in player_input for word in ("线索", "情报", "来源")):
        leverage.append("可交换情报或来源线索")
    if not leverage:
        leverage.append("只能提供低风险协助")
    if any(word in player_input for word in ("护法", "指导")):
        aids = player.setdefault("cultivation_aids", [])
        aid = {
            "source": target,
            "type": "guidance",
            "uses": 1,
            "effect": "降低一次突破准备的失败风险；不替代丹药、魔核、功法或安全地点等硬资源。",
        }
        if aid not in aids:
            aids.append(aid)
            changes.append(f"修炼帮助新增：{target} 指导/护法（1 次，非硬前置）")
    return leverage, changes


def paid_guidance_offer(player_input: str) -> bool:
    return any(word in player_input for word in ("支付", "金币", "少量金币", "花钱")) and any(word in player_input for word in ("指点", "指导", "护法"))


def social_target_options(rules: dict[str, Any]) -> list[str]:
    options: list[str] = []
    for row in rules.get("npcs", []) + rules.get("factions", []):
        name = str(row.get("name", "")).strip()
        if not name or name in BAD_SOCIAL_TARGETS or len(name) > 12 or any(mark in name for mark in ("。", "，", "；", "：", "\n")):
            continue
        if name not in options:
            options.append(name)
        if len(options) >= 4:
            break
    return options or ["先找本地摊主或杂役打听。", "寻找可信炼药师。", "询问守卫或商队联系人。"]


def resolve_opening_social_target(target: str, player_input: str, state: dict[str, Any], relationship_change: str | None) -> dict[str, Any] | None:
    if target == "练武场管事":
        flags = state.setdefault("scene_flags", {})
        flags["asked_training_ground_entry"] = True
        return {
            "kind": "social",
            "status": "resolved",
            "verdict": "入场条件已问清",
            "consequence": (
                "你没有急着往门里挤，而是等管事挂完木牌，先拱手说明自己想找个能出力的机会。"
                "管事扫了你一眼，没有立刻赶人，只把木牌往你面前推了推："
                "“练武场不是谁想进就进。外姓、无担保、无贡献，最多从杂务做起。"
                "搬完沙袋、清完器械，或者把外院药材账单送去坊市，午后可以旁听半个时辰。"
                "名额两个，做事拖沓就换别人。”"
            ),
            "state_changes": [item for item in [relationship_change, "已问清练武场入场条件：完成杂务可换午后旁听机会。"] if item],
            "options": [
                "接下搬运沙袋，换取午后旁听资格。",
                "接下清扫器械，顺便观察萧家少年如何训练。",
                "接下送药材账单，去坊市打听药材价格和跑腿报酬。",
                "继续追问旁听规矩、失败后果和是否需要担保。",
            ],
        }
    if target == "药材伙计":
        return {
            "kind": "social",
            "status": "resolved",
            "verdict": "跑腿机会已出现",
            "consequence": (
                "你拦下送账单的药材伙计，先问报酬和路线。对方急着去坊市，愿意把账单交给你跑一趟，"
                "但要求你带回摊主签押和三家低阶药材价目。做成了能给少量金币，做砸了要赔误事的人情。"
            ),
            "state_changes": [item for item in [relationship_change, "发现低风险跑腿机会：送药材账单并核价。"] if item],
            "options": [
                "接下送账单和核价的小活。",
                "先问清报酬、期限和失败后果。",
                "拒绝跑腿，回头找练武场管事。",
            ],
        }
    return None


def apply_paid_guidance(state: dict[str, Any], target: str) -> tuple[bool, list[str], str]:
    player = state.setdefault("player", {})
    currencies = player.setdefault("currencies", {})
    coins = int(currencies.get("coins", 0) or 0)
    cost = 5
    if coins < cost:
        return False, [], f"你当前只有 {coins} 金币，不足以支付这次指点的最低谢礼（{cost} 金币）。"
    currencies["coins"] = coins - cost
    aids = player.setdefault("cultivation_aids", [])
    aid = {
        "source": target,
        "type": "paid_guidance",
        "uses": 1,
        "effect": "降低一次突破准备的失败风险；不替代丹药、魔核、功法或安全地点等硬资源。",
    }
    if aid not in aids:
        aids.append(aid)
    return True, [f"金币：{coins} -> {coins - cost}", f"修炼帮助新增：{target} 付费指点（1 次，非硬前置）"], "你支付少量金币，换到一次具体指点：先稳住斗气运转，再确认辅助资源和安全地点；这能降低突破准备风险，但不保证突破成功。"


def resolve_social(world: str, player_input: str, state: dict[str, Any], canon_rows: list[dict[str, Any]]) -> dict[str, Any]:
    rules = load_relationship_rules(world)
    target = detect_target(player_input, canon_rows, rules) or fallback_social_target(player_input, state)
    if not target:
        options = ["寻找可信炼药师。", "询问守卫或商队联系人。", "先找本地摊主或杂役打听。"] if paid_guidance_offer(player_input) else social_target_options(rules)
        return {
            "kind": "social",
            "status": "conditional",
            "verdict": "缺少明确互动对象",
            "consequence": "你需要先确认要接触的 NPC 或势力；不同对象会影响好感、敌意、人情债和资源渠道。",
            "state_changes": [],
            "options": options,
        }
    delta = 3
    if any(word in player_input for word in ("威胁", "挑衅", "勒索")):
        delta = -8
    elif any(word in player_input for word in ("送礼", "求助", "拜师", "结交", "交换", "人情", "承诺", "护法", "指导")):
        delta = 5
    leverage, leverage_changes = player_leverage(player_input, state, target)
    change = adjust_relationship(state, target, delta, f"行动：{player_input[:60]}")
    opening_result = resolve_opening_social_target(target, player_input, state, change)
    if opening_result:
        return attach_quest_progress(state, player_input, opening_result)
    paid_ok = False
    paid_changes: list[str] = []
    paid_note = ""
    if paid_guidance_offer(player_input):
        paid_ok, paid_changes, paid_note = apply_paid_guidance(state, target)
    motives = read_json(world_dir(world) / "npc_motives.json", {}).get("npcs", [])
    motive = next((row for row in motives if row.get("npc") == target), {})
    motive_note = ""
    motive_options: list[str] = []
    if motive:
        motive_leverage = "；".join(motive.get("leverage", [])[:2])
        boundaries = "；".join(motive.get("boundaries", [])[:2])
        motive_note = f" 对方可被打动的筹码：{motive_leverage or '合理利益或可信关系'}；底线：{boundaries or '不会无条件满足要求'}。"
        motive_options = []
        for option in motive.get("player_hooks", [])[:3]:
            option = str(option).strip()
            if option and not any(verb in option for verb in ("请求", "提出", "交换", "询问", "完成", "帮助", "打听", "合作", "确认")):
                option = f"围绕「{option}」提出具体请求"
            if option:
                motive_options.append(option if option.endswith(("。", "！", "？")) else f"{option}。")
        motive_options.extend(["提出具体交换条件。", "询问对方不能接受的底线。"])
    asks_for_terms = any(word in player_input for word in ("筹码", "承诺", "开价", "条件", "底线", "需要什么"))
    offers_exchange = any(word in player_input for word in ("交换", "人情", "金币", "跑腿", "核价", "传话", "换", "护法", "指导"))
    if paid_guidance_offer(player_input) and not paid_ok:
        return {
            "kind": "social",
            "status": "blocked",
            "verdict": "金币不足，不能换取指点",
            "consequence": paid_note,
            "state_changes": [item for item in [change] if item],
            "options": ["接受低风险跑腿或核价，换基础情报。", "用后续承诺换联系人入口。", "先赚钱再回来请教。"],
        }
    if asks_for_terms or offers_exchange:
        terms = [
            "低风险跑腿或核价换基础情报。",
            "少量金币换一次指点，但不包含丹药和突破保证。",
            "后续承诺换联系人入口；失约会降低关系。",
        ]
        consequence = paid_note if paid_guidance_offer(player_input) and paid_ok else (
            f"你把筹码摊开给「{target}」：{'；'.join(leverage)}。"
            f"对方给出可执行条件：{' '.join(terms)}"
            f"{motive_note}"
        )
        return {
            "kind": "social",
            "status": "resolved",
            "verdict": "付费指点已获得" if paid_guidance_offer(player_input) and paid_ok else "交换条件已明确",
            "consequence": consequence,
            "state_changes": [item for item in [change, *leverage_changes, *paid_changes] if item],
            "options": [
                "确认当前最现实的辅助资源来源。",
                "寻找安全修炼地点。",
                "准备低风险跑腿或核价，换更多情报。",
                "暂时不继续付费，避免资源耗尽。",
            ],
        }
    return {
        "kind": "social",
        "status": "resolved",
        "verdict": "关系已更新",
        "consequence": f"你与「{target}」产生一次明确互动。关系变化会影响后续情报、交易、任务和敌意。{motive_note}",
        "state_changes": [change, *leverage_changes] if change else leverage_changes,
        "options": (motive_options or ["继续沟通。", "提出交易或任务请求。", "暂时退开避免关系恶化。"])[:4],
    }


def attach_quest_progress(state: dict[str, Any], player_input: str, result: dict[str, Any]) -> dict[str, Any]:
    messages, options = progress_quests(state, player_input)
    if messages:
        result.setdefault("state_changes", []).extend(messages)
        existing = result.setdefault("options", [])
        completed = [message.split("目标完成：", 1)[1] for message in messages if "目标完成：" in message]
        completed_quests = [message for message in messages if message.endswith("完成。")]
        if completed:
            progress_text = "；".join(completed[:2])
            reward_text = "；".join(message for message in messages if message.startswith(("历练：", "金币：", "行囊新增：")))
            summary = f"你完成了当前目标：{progress_text}。"
            if completed_quests:
                summary += f" {'；'.join(completed_quests[:2])}"
            if reward_text:
                summary += f" 奖励结算：{reward_text}。"
            generic_markers = ("当前任务推进", "已有任务推进", "任务继续推进", "已经在进行中", "本回合不会因为")
            if any(marker in str(result.get("verdict", "")) or marker in str(result.get("consequence", "")) for marker in generic_markers):
                result["consequence"] = summary
            else:
                result["consequence"] = f"{result.get('consequence', '')} {summary}".strip()
        reordered: list[str] = []
        for option in [*options, *existing]:
            if option in completed:
                continue
            if option and option not in reordered:
                reordered.append(option)
        result["options"] = reordered
    return result


def resolve_action(world: str, player_input: str, state: dict[str, Any], canon_rows: list[dict[str, Any]], forced_kind: str | None = None) -> dict[str, Any]:
    allowed_forced_kinds = {"social", "quest", "location", "info", "trade", "cultivation", "inventory", "combat", "high_risk", "general"}
    kind = forced_kind if forced_kind in allowed_forced_kinds else classify_action(player_input)
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
    if ability_result and kind in {"cultivation", "combat", "high_risk", "general"} and ability_result.get("status") in {"blocked", "partial_or_blocked"}:
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
    learning_result = resolve_skill_learning(world, player_input, state)
    if learning_result:
        return attach_quest_progress(state, player_input, learning_result)
    if kind == "trade":
        return attach_quest_progress(state, player_input, resolve_trade(world, player_input, state, canon_rows))
    if kind == "cultivation":
        return attach_quest_progress(state, player_input, resolve_cultivation(world, player_input, state, canon_rows))
    if kind == "combat":
        return attach_quest_progress(state, player_input, resolve_combat(world, player_input, state))
    if kind == "quest":
        return attach_quest_progress(state, player_input, resolve_quest(world, player_input, state, canon_rows))
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
