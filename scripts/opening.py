#!/usr/bin/env python3
from __future__ import annotations

import argparse
from typing import Any

from common import default_background, load_manifest, read_json, save_manifest, world_dir, write_json


def _first_names(rows: list[dict[str, Any]], limit: int = 4) -> list[str]:
    return [str(row.get("name")) for row in rows[:limit] if row.get("name")]


def _clean(value: Any, limit: int = 160) -> str:
    text = " ".join(str(value or "").replace("\n", " ").split()).strip(" ，。；")
    if not text:
        return ""
    return text[:limit].rstrip("，。； ")


def _unique(values: list[Any], limit: int = 4, width: int = 120) -> list[str]:
    rows: list[str] = []
    for value in values:
        text = _clean(value, width)
        if text and text not in rows:
            rows.append(text)
        if len(rows) >= limit:
            break
    return rows


def _top_story_arcs(world: str, limit: int = 4) -> list[dict[str, Any]]:
    arcs = read_json(world_dir(world) / "story_arcs.json", {}).get("arcs", [])
    arcs = [arc for arc in arcs if arc.get("name") and arc.get("summary")]
    return sorted(
        arcs,
        key=lambda arc: (
            int(arc.get("source_priority") or 0),
            float(arc.get("confidence") or 0),
            int(arc.get("mentions") or 0),
        ),
        reverse=True,
    )[:limit]


def _top_npc_cards(world: str, limit: int = 4) -> list[dict[str, Any]]:
    cards = read_json(world_dir(world) / "npc_motives.json", {}).get("npcs", [])
    cards = [card for card in cards if card.get("npc")]
    return sorted(cards, key=lambda card: (int(card.get("fact_count") or 0), float(card.get("confidence") or 0)), reverse=True)[:limit]


def _identity_background(world: str, background: dict[str, Any], location: str, faction: str, arcs: list[dict[str, Any]]) -> dict[str, Any]:
    if "doupo" in world:
        return {
            "identity": "乌坦城边缘少年",
            "origin": "你出身在乌坦城底层小户，能旁听萧家练武场的动静，却没有稳定师承、丹药和家族资源。",
            "past": "过去几年，你见过天才与废物只隔一场测试，也见过金币、丹药和人脉怎样决定一个少年能走多远。你不想替别人鼓掌，也不想被一句“资质普通”定死。",
            "role_boundary": "你不是原著主角，也不能预知主角机缘；你只能用当前身份、关系和资源，逐步接近这个世界的机会。",
        }
    arc_hint = arcs[0].get("summary") if arcs else ""
    return {
        "identity": background.get("origin", "无名旅人"),
        "origin": f"你从「{location}」附近开始行动，与「{faction}」只有松散联系，还没有足以改变命运的身份背书。",
        "past": arc_hint or background.get("opening_scene", "你刚踏入这个世界，对规则、势力和危险都只有模糊认识。"),
        "role_boundary": "你不能预知原著未来，也不能一句话跳过资源、关系、地点和能力前置。",
    }


def _opening_scene(world: str, location: str) -> str:
    if "doupo" in world:
        return (
            "清晨的乌坦城还带着薄雾。萧家练武场里，木桩被斗气震得发闷，少年们压低呼吸，"
            "有人在比较段位，有人在计算一瓶低阶药液的价钱。你站在场外，身上只有粗制护具和一门入门斗技，"
            "知道自己若想真正踏入斗气之路，第一步不是豪言壮语，而是找到资源、指导和一个不会立刻把你吞掉的机会。"
        )
    return f"你来到「{location}」的边缘。这里的机会和危险都还没有露出全貌，任何行动都需要先确认规则、关系和代价。"


def _opening_incident(world: str) -> dict[str, Any]:
    if "doupo" in world:
        return {
            "title": "练武场外的第一道门槛",
            "scene": (
                "练武场木门半开，里面刚结束一轮斗气测试。几个萧家少年正围着石碑说笑，"
                "一名管事把写着杂务名目的木牌挂到门侧：搬运沙袋、清扫器械、替外院送药材账单。"
                "做完的人可以在午后旁听半个时辰基础吐纳，但名额只有两个。"
            ),
            "visible_tension": (
                "你听见有人低声嘲笑外姓少年也想蹭练武场资源。管事没有赶你走，"
                "但他的眼神很清楚：没有贡献、没有担保、没有金币，就别妄想直接进场。"
            ),
            "first_goal": "在不惹怒萧家人的前提下，拿到一个可验证的小机会：旁听、杂务名额、药材账单线索，或低阶修炼资源消息。",
            "pressure_clock": "午后旁听名额会在一炷香内定下；如果你只是旁观，机会可能被其他低阶少年拿走。",
            "visible_npcs": [
                "练武场管事：负责分配杂务和旁听名额，只认规矩、耐性和可见贡献。",
                "萧家低阶少年：可能嘲笑你，也可能被你用训练心得或杂务合作打动。",
                "送账单的药材伙计：正等人把账单送去坊市，可能牵出药材价格和跑腿报酬。",
            ],
        }
    return {
        "title": "第一处立足点",
        "scene": "你刚抵达起点附近，一个低风险但有时间窗口的小机会正在出现。",
        "visible_tension": "机会不会等你太久；贸然深入会暴露无知，停在原地则会错过入口。",
        "first_goal": "确认当前地点的规则、人物和最低风险行动入口。",
        "pressure_clock": "如果你拖延，别人会先拿走线索、资源或任务资格。",
        "visible_npcs": [],
    }


def _known_context(world: str, arcs: list[dict[str, Any]], npc_cards: list[dict[str, Any]], hooks: list[str]) -> list[str]:
    rows: list[str] = []
    if "doupo" in world:
        return [
            "斗气是这个世界的根基；低阶修炼者离不开功法、训练、资源和安全环境。",
            "丹药、药材、魔核和拍卖渠道能改变修炼速度，但都需要金币、人情或可靠联系人。",
            "乌坦城有萧家、拍卖场和坊市，适合从低风险打听、跑腿、议价和基础训练开始。",
            "萧家练武场不是公开善堂；没有身份或贡献时，最好先观察规矩，再找低风险入口。",
            "拍卖场和坊市讲究信誉、眼力和本金；空口许诺通常换不到真正资源。",
        ]
    rows.extend(f"{arc.get('name')}：{arc.get('summary')}" for arc in arcs[:2])
    rows.extend(f"{card.get('npc')}：{card.get('public_goal')}" for card in npc_cards[:2] if card.get("public_goal"))
    rows.extend(hooks[:2])
    return _unique(rows, 6, 140)


def _personal_stakes(world: str, arcs: list[dict[str, Any]]) -> list[str]:
    if "doupo" in world:
        return [
            "你需要先证明自己能稳定修炼，而不是空喊要变强。",
            "你没有金币，购买药材、斗技消息或训练资格都要找来源。",
            "你可以接触原著人物和事件，但必须用合理身份切入，不能默认别人信任你。",
        ]
    return _unique(
        [
            "你缺少可靠资源、关系和情报。",
            "越过当前能力边界会触发失败、代价或敌意。",
            *[arc.get("summary") for arc in arcs[:2]],
        ],
        4,
        130,
    )


def _relationship_seeds(npc_cards: list[dict[str, Any]]) -> list[str]:
    rows = []
    for card in npc_cards:
        npc = card.get("npc")
        if not npc:
            continue
        hook = next(iter(card.get("player_hooks", []) or []), "")
        boundary = next(iter(card.get("boundaries", []) or []), "")
        text = f"{npc}：{hook or card.get('public_goal', '')}"
        if boundary:
            text += f"；底线：{boundary}"
        rows.append(text)
    return _unique(rows, 4, 150)


def _opening_relationship_seeds(world: str, npc_cards: list[dict[str, Any]]) -> list[str]:
    if "doupo" in world:
        return [
            "萧家练武场管事：可能允许你旁观或做杂务换训练机会，但会先看规矩和耐性。",
            "坊市药材摊主：可能提供低阶药材价格线索，但需要金币、跑腿或识货能力。",
            "拍卖场外围联系人：可能知道低阶修炼资源流向，但只认信誉、货源和可验证的价值。",
            "低阶修炼者：可能交换训练心得，也可能把你当成竞争者或笑柄。",
        ]
    return _relationship_seeds(npc_cards)


def build_opening(world: str) -> dict[str, Any]:
    wdir = world_dir(world)
    manifest = load_manifest(wdir, world)
    locations = read_json(wdir / "locations.json", {}).get("locations", [])
    factions = read_json(wdir / "factions.json", {}).get("factions", [])
    npcs = read_json(wdir / "npcs.json", {}).get("npcs", [])
    hooks = read_json(wdir / "adventure_hooks.json", {}).get("hooks", [])
    background = default_background(world)

    display_name = manifest.get("display_name") or world
    starting_location = _first_names(locations, 1)[0] if locations else "未确定起点"
    primary_faction = _first_names(factions, 1)[0] if factions else "本地势力"
    first_npc = _first_names(npcs, 1)[0] if npcs else "本地人"
    hook_names = _first_names(hooks, 4) or background["starting_hooks"]
    arcs = _top_story_arcs(world)
    npc_cards = _top_npc_cards(world)
    identity = _identity_background(world, background, starting_location, primary_faction, arcs)
    known_context = _known_context(world, arcs, npc_cards, hook_names)
    stakes = _personal_stakes(world, arcs)
    relationships = _opening_relationship_seeds(world, npc_cards)
    incident = _opening_incident(world)

    if manifest.get("profile") == "doupo" or "doupo" in world:
        opening = {
            "world": world,
            "display_name": display_name,
            "player_background": {
                **background,
                **identity,
                "opening_scene": _opening_scene(world, "乌坦城"),
                "motivation": "你想从斗之气低段开始，靠可验证的小目标逐步拿到资源、指导、关系和真正的成长机会。",
                "starting_conflict": "你没有丹药、没有正式师承、没有金币，也没有能让萧家或拍卖场立刻重视你的身份。",
                "known_context": known_context,
                "personal_stakes": stakes,
                "relationship_seeds": relationships,
                "opening_incident": incident,
            },
            "starting_location": "乌坦城萧家练武场外",
            "starting_time": "第一日 清晨",
            "initial_options": [
                "上前询问练武场管事：我能做哪件杂务换旁听机会？",
                "观察萧家低阶少年和木牌内容，判断哪个任务最稳妥。",
                "找送账单的药材伙计搭话，询问是否需要跑腿以及报酬。",
                "自定义行动。",
            ],
        }
    else:
        opening = {
            "world": world,
            "display_name": display_name,
            "player_background": {
                **identity,
                "origin": background["origin"],
                "opening_scene": _opening_scene(world, starting_location),
                "motivation": background["motivation"],
                "starting_conflict": "你缺少可靠资源、关系和情报，需要先确认世界规则，再寻找安全成长路径。",
                "known_context": known_context,
                "personal_stakes": stakes,
                "relationship_seeds": relationships or [f"{first_npc}等人物可能影响你的第一步选择。"],
                "opening_incident": incident,
                "starting_hooks": hook_names,
            },
            "starting_location": starting_location,
            "starting_time": "第一日 清晨",
            "initial_options": [
                f"观察「{starting_location}」周围环境，确认风险。",
                f"打听「{primary_faction}」的规矩和可接任务。",
                "寻找可靠 NPC，询问这个世界的基础生存方式。",
                "自定义行动。",
            ],
        }
    write_json(wdir / "opening.json", opening)
    manifest["opening"] = "opening.json"
    save_manifest(wdir, manifest)
    return opening


def ensure_opening(world: str) -> dict[str, Any]:
    wdir = world_dir(world)
    existing = read_json(wdir / "opening.json", {})
    return existing or build_opening(world)


def format_opening(opening: dict[str, Any]) -> str:
    bg = opening.get("player_background", {})
    options = opening.get("initial_options", [])
    known_context = bg.get("known_context", [])
    personal_stakes = bg.get("personal_stakes", [])
    relationship_seeds = bg.get("relationship_seeds", [])
    incident = bg.get("opening_incident", {})
    lines = [
        f"# {opening.get('display_name', opening.get('world', '未知世界'))}",
        "",
        "## 身份",
        str(bg.get("identity") or bg.get("origin", "无名旅人")),
        "",
        "## 背景",
        str(bg.get("origin", "")),
        "",
        "## 过去",
        str(bg.get("past", "")),
        "",
        "## 开场",
        str(bg.get("opening_scene", "")),
        "",
        "## 第一幕",
        str(incident.get("title", "起点")),
        "",
        str(incident.get("scene", "")),
        "",
        "## 眼前冲突",
        str(incident.get("visible_tension", "")),
        "",
        "## 当前目标",
        str(incident.get("first_goal", "")),
        "",
        "## 时间压力",
        str(incident.get("pressure_clock", "")),
        "",
        "## 你想要什么",
        str(bg.get("motivation", "")),
        "",
        "## 当前困难",
        str(bg.get("starting_conflict", "")),
        "",
        "## 你知道的事",
    ]
    lines.extend(f"- {item}" for item in known_context)
    lines.extend(
        [
            "",
            "## 你的压力",
        ]
    )
    lines.extend(f"- {item}" for item in personal_stakes)
    if relationship_seeds:
        lines.extend(["", "## 可接触关系"])
        lines.extend(f"- {item}" for item in relationship_seeds)
    if incident.get("visible_npcs"):
        lines.extend(["", "## 眼前人物"])
        lines.extend(f"- {item}" for item in incident.get("visible_npcs", []))
    lines.extend(
        [
            "",
            "## 主持规则",
            str(bg.get("role_boundary", "不能预知原著未来，也不能跳过资源、关系、地点和能力前置。")),
            "",
            "## 可选开局行动",
        ]
    )
    lines.extend(f"{idx}. {option}" for idx, option in enumerate(options, 1))
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate or print a world's opening scene.")
    parser.add_argument("--world", required=True)
    parser.add_argument("--rebuild", action="store_true")
    args = parser.parse_args()
    opening = build_opening(args.world) if args.rebuild else ensure_opening(args.world)
    print(format_opening(opening))


if __name__ == "__main__":
    main()
