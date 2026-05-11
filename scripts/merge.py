#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from typing import Any

from common import (
    default_player_state,
    load_manifest,
    migrate_player_state,
    read_json,
    read_jsonl,
    save_manifest,
    write_json,
    write_jsonl,
    world_dir,
)
from economy import build_economy
from encounter_runtime import build_encounter_state
from location_runtime import build_locations
from quest_runtime import build_quests
from relationship_runtime import build_relationship_rules
from rpg_profile import apply_rpg_profile_to_state, build_rpg_profile, load_rpg_profile


ENTITY_LIMITS = {
    "power_realm": 80,
    "cultivation_rule": 300,
    "faction": 800,
    "location": 800,
    "npc": 500,
    "item": 500,
    "technique": 500,
    "event": 300,
    "playable_hook": 120,
    "world_law": 160,
    "style_signal": 40,
}

NEGATIVE_WORDS = ("不可", "不能", "无法", "禁止", "不许")
POSITIVE_WORDS = ("可以", "能够", "允许", "能")


def norm_name(name: str) -> str:
    return name.strip().replace("　", "").lower()


def fact_weight(fact: dict[str, Any]) -> float:
    confidence = float(fact.get("confidence", 0.5))
    quality = float(fact.get("quality", confidence))
    evidence_bonus = min(len(fact.get("evidence_chunk_ids", [])), 5) * 0.03
    known_bonus = 0.08 if quality >= 0.9 else 0.0
    return confidence * 0.45 + quality * 0.45 + evidence_bonus + known_bonus


def group_facts(facts: list[dict[str, Any]]) -> dict[str, dict[str, dict[str, Any]]]:
    grouped: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for fact in facts:
        ftype = fact["type"]
        key = norm_name(fact["name"])
        if not key:
            continue
        if key not in grouped[ftype]:
            grouped[ftype][key] = {
                "name": fact["name"],
                "type": ftype,
                "aliases": set(),
                "claims": [],
                "evidence_chunk_ids": set(),
                "confidence": 0.0,
                "quality": 0.0,
                "mentions": 0,
                "score": 0.0,
            }
        item = grouped[ftype][key]
        item["aliases"].update(fact.get("aliases", []))
        item["claims"].append(
            {
                "claim": fact["claim"],
                "confidence": fact.get("confidence", 0.5),
                "quality": fact.get("quality", fact.get("confidence", 0.5)),
                "evidence_chunk_ids": fact.get("evidence_chunk_ids", []),
            }
        )
        item["evidence_chunk_ids"].update(fact.get("evidence_chunk_ids", []))
        item["confidence"] = max(item["confidence"], fact.get("confidence", 0.5))
        item["quality"] = max(item["quality"], fact.get("quality", fact.get("confidence", 0.5)))
        item["mentions"] += 1
        item["score"] += fact_weight(fact)
    return grouped


def finalize_entity(item: dict[str, Any]) -> dict[str, Any]:
    claims = sorted(item["claims"], key=lambda row: (row.get("quality", 0), row.get("confidence", 0), len(row.get("claim", ""))), reverse=True)
    unique_claims = []
    seen = set()
    has_negative = False
    has_positive = False
    for claim in claims:
        text = claim["claim"]
        if text not in seen:
            unique_claims.append(claim)
            seen.add(text)
        has_negative = has_negative or any(word in text for word in NEGATIVE_WORDS)
        has_positive = has_positive or any(word in text for word in POSITIVE_WORDS)
    score = round(item["score"] + min(item["mentions"], 12) * 0.08, 3)
    return {
        "name": item["name"],
        "aliases": sorted(alias for alias in item["aliases"] if alias and alias != item["name"]),
        "summary": unique_claims[0]["claim"] if unique_claims else "",
        "claims": unique_claims[:6],
        "evidence_chunk_ids": sorted(item["evidence_chunk_ids"]),
        "confidence": round(item["confidence"], 2),
        "quality": round(item["quality"], 2),
        "mentions": item["mentions"],
        "score": score,
        "conflict_status": "unresolved" if has_negative and has_positive and len(unique_claims) > 1 else "clear",
    }


NOISE_PRONE_TYPES = {"cultivation_rule", "faction", "location", "npc", "item", "technique"}
GENERIC_RULE_NAMES = {"修炼", "斗气", "斗技", "功法", "炼药", "丹药", "境界", "能量"}


def entity_is_usable(row: dict[str, Any], ftype: str) -> bool:
    if ftype not in NOISE_PRONE_TYPES:
        return True
    quality = float(row.get("quality", 0.0))
    score = float(row.get("score", 0.0))
    mentions = int(row.get("mentions", 0))
    name = str(row.get("name", ""))
    if ftype == "cultivation_rule" and name in GENERIC_RULE_NAMES:
        return False
    if quality >= 0.88:
        return True
    if ftype in {"item", "technique"} and score >= 30.0 and mentions >= 20 and len(name) <= 8:
        return True
    return False


def entities(grouped: dict[str, dict[str, dict[str, Any]]], ftype: str) -> list[dict[str, Any]]:
    rows = [finalize_entity(item) for item in grouped.get(ftype, {}).values()]
    rows = [row for row in rows if entity_is_usable(row, ftype)]
    rows.sort(key=lambda row: (row["score"], row["mentions"], row["quality"]), reverse=True)
    return rows[: ENTITY_LIMITS.get(ftype, 500)]


def seed_entity(name: str, summary: str, ftype: str, score: float = 999.0) -> dict[str, Any]:
    return {
        "name": name,
        "aliases": [],
        "summary": summary,
        "claims": [{"claim": summary, "confidence": 1.0, "quality": 1.0, "evidence_chunk_ids": []}],
        "evidence_chunk_ids": [],
        "confidence": 1.0,
        "quality": 1.0,
        "mentions": 0,
        "score": score,
        "conflict_status": "clear",
        "source": "profile_seed",
    }


def merge_seeded(seed_rows: list[dict[str, Any]], extracted_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen = {row["name"] for row in seed_rows}
    return seed_rows + [row for row in extracted_rows if row.get("name") not in seen]


def doupo_seed_outputs(outputs: dict[str, list[dict[str, Any]]]) -> dict[str, list[dict[str, Any]]]:
    realms = [
        ("斗之气", "斗气修炼的基础阶段，通常以段位衡量；达到足够段位后可凝聚斗之气旋，迈入斗者。"),
        ("斗者", "正式踏入斗气修炼门槛，形成斗之气旋，可系统修习功法与斗技。"),
        ("斗师", "斗气掌控力明显增强，可外放斗气并支撑更稳定的战斗消耗。"),
        ("大斗师", "斗气强度和身体承载力进一步提升，低阶修炼者很难正面对抗。"),
        ("斗灵", "能够更成熟地调动斗气战斗，是地方势力中的重要战力。"),
        ("斗王", "可以斗气化翼、短距离飞行，开始具备跨区域行动和压制低阶修炼者的能力。"),
        ("斗皇", "加玛帝国层面的顶尖强者，能显著影响宗门、家族与帝国格局。"),
        ("斗宗", "可踏空而行，是大陆强者分水岭，对低阶修炼者具有压倒性威胁。"),
        ("斗尊", "中州高阶强者层次，拥有极强空间与斗气掌控力。"),
        ("半圣", "斗尊与斗圣之间的过渡层次，已接近圣者领域。"),
        ("斗圣", "远古种族与大陆顶级势力的核心战力，可开辟或影响空间。"),
        ("斗帝", "斗气大陆传说中的终极境界，长期绝迹；成帝需要极稀缺的源气。"),
    ]
    rules = [
        ("斗气体系", "斗气大陆没有花俏魔法，主流力量是斗气；修炼依赖功法、斗技、资源、体质和机缘。"),
        ("境界压制", "高境界通常对低境界形成压制；越级战斗需要异火、强斗技、特殊体质、经验或外力支撑。"),
        ("功法等级", "功法通常分为天、地、玄、黄四阶，每阶又有低中高等层次；高阶功法决定修炼速度和斗气质量。"),
        ("斗技等级", "斗技同样有品阶差异，高阶斗技威力强但消耗和修习门槛更高。"),
        ("炼药师", "炼药师能炼制提升实力、疗伤或辅助突破的丹药，因此地位高且容易被势力拉拢。"),
        ("异火", "异火是天地奇火，威力狂暴，可增强战斗和炼药，但收服失败会造成重伤甚至死亡。"),
        ("药老指导", "药老拥有高阶炼药与修炼经验，可提供指导，但不能让玩家无视资源、境界和风险直接成功。"),
    ]
    laws = [
        ("斗气大陆", "这是斗气繁衍到巅峰的世界，强者、家族、宗派、学院和炼药师共同构成核心秩序。"),
        ("资源稀缺", "高级功法、斗技、丹药、异火和魔核都具备稀缺性，获取通常伴随竞争、交易或危险。"),
        ("势力后果", "家族、宗门和帝国势力会对玩家行为作出反应；羞辱、抢夺、杀戮和背叛都会产生长期后果。"),
    ]
    hooks = [
        ("乌坦城开局", "玩家可从乌坦城出发，围绕萧家、退婚风波、拍卖场、筑基灵液和斗气修炼展开早期冒险。"),
        ("异火线", "玩家可通过地图、情报、药老指导和高风险探索追寻异火，但必须准备丹药、护体手段和退路。"),
        ("炼药线", "玩家可收集药材、魔核和药方，学习炼药，借丹药提升修炼或换取资源与人情。"),
        ("势力线", "玩家可与萧家、云岚宗、米特尔家族、炼药师公会等势力结交或冲突。"),
    ]
    locations = [
        ("乌坦城", "加玛帝国东北部城市，萧家早期根基所在；适合低阶玩家打听情报、购买基础资源、接触家族与拍卖场事件。"),
        ("萧家", "乌坦城三大家族之一，是萧炎出身势力；家族声望、人情与内部评价会影响玩家早期资源和任务。"),
        ("魔兽山脉", "乌坦城外的高风险野外区域，盛产魔核、药材和魔兽踪迹；低阶玩家必须结伴、准备疗伤物品和撤退路线。"),
        ("云岚宗", "加玛帝国强大宗门，和退婚、三年之约等主线冲突有关；贸然挑衅会引来宗门级后果。"),
        ("迦南学院", "大陆知名学院，适合中期修炼、试炼和结交天才；入院、内院竞争与天焚炼气塔是重要玩法入口。"),
        ("黑角域", "秩序混乱、强者和交易并存的区域；适合高风险交易、争夺功法斗技和卷入势力冲突。"),
        ("中州", "斗气大陆强者和顶级势力集中的核心舞台；玩家低阶时只能通过传闻和远期目标接触。"),
    ]
    npcs = [
        ("药老", "高阶炼药师灵魂体，能提供炼药、功法和修炼判断；他的建议是情报和指导，不等于自动成功或无代价通关。"),
        ("萧炎", "萧家少年，主线气运与成长压力集中在其身上；与他的关系会影响萧家、药老、异火和三年之约相关事件。"),
        ("薰儿", "萧家中身份特殊的少女，背景深厚；她的信任、保护或疏离会影响早期安全与后续远古种族线索。"),
        ("纳兰嫣然", "云岚宗弟子，退婚事件核心人物；相关互动会影响萧家名誉、云岚宗态度和三年之约走向。"),
        ("雅妃", "米特尔拍卖场人物，擅长交易与人脉经营；玩家可通过她获取资源、情报或商业合作，但需付出利益交换。"),
        ("美杜莎", "蛇人族女王级强者，危险而强势；低阶玩家不能正面对抗，只能依靠谈判、筹码、时机或外力周旋。"),
    ]
    factions = [
        ("萧家", "乌坦城本土家族，早期提供身份、庇护和限制；玩家行为会改变家族声望、资源支持和敌对关系。"),
        ("云岚宗", "加玛帝国宗门级势力，拥有强者、弟子和政治影响；冲突必须考虑追杀、封锁和声望代价。"),
        ("米特尔家族", "加玛帝国商业与拍卖势力，可提供交易、情报和资源渠道；关系建立依赖信誉与利益。"),
        ("迦南学院", "以培养修炼者为核心的学院势力，适合试炼、晋升和结交同辈；规则竞争多于直接江湖厮杀。"),
        ("魂殿", "暗中猎取灵魂、布局大陆的危险势力；过早暴露会带来远超玩家等级的追踪风险。"),
        ("丹塔", "炼药师体系的重要高阶势力，和丹药、药方、炼药师身份认证相关。"),
    ]
    items = [
        ("异火", "天地奇火，能显著增强战斗与炼药能力；收服前必须确认位置、守护者、克制手段、丹药准备和失败代价。"),
        ("纳戒", "储物戒指，常用于隐藏物品、灵魂寄居或携带资源；检查纳戒可能触发秘密、机缘或风险。"),
        ("玄重尺", "沉重尺类武器，适合压制速度、锤炼力量和施展尺法；使用者需要足够体魄与斗气支撑。"),
        ("筑基灵液", "早期辅助修炼资源，可改善低阶修炼效率；需要药材、炼制能力或可靠购买渠道。"),
        ("聚气散", "辅助凝聚斗之气旋、冲击斗者的重要丹药；来源稀缺，可能引发竞争和交易条件。"),
        ("魔核", "魔兽体内能量核心，可用于炼药、交易和修炼资源；获取通常意味着猎杀或购买。"),
    ]
    techniques = [
        ("焚诀", "可随吞噬异火进化的特殊功法，成长潜力极高但风险极大；每次进化都需要异火线索、护法和失败预案。"),
        ("佛怒火莲", "融合多种火焰形成的高风险高爆发斗技；威力巨大，但对控制力、火焰条件和自身承受力要求极高。"),
        ("八极崩", "近身爆发型斗技，适合贴身破防；需要判断距离、体魄和敌人防御。"),
        ("紫云翼", "飞行斗技，可提升移动与逃生能力；使用消耗斗气，低阶玩家不能无限飞行。"),
        ("三千雷动", "高阶身法斗技，适合闪避、追击和脱身；修炼门槛与消耗较高。"),
    ]
    outputs["power_realm"] = merge_seeded([seed_entity(n, s, "power_realm", 1200 - i) for i, (n, s) in enumerate(realms)], outputs.get("power_realm", []))
    outputs["cultivation_rule"] = merge_seeded([seed_entity(n, s, "cultivation_rule", 1100 - i) for i, (n, s) in enumerate(rules)], outputs.get("cultivation_rule", []))
    outputs["world_law"] = merge_seeded([seed_entity(n, s, "world_law", 1000 - i) for i, (n, s) in enumerate(laws)], outputs.get("world_law", []))
    outputs["playable_hook"] = merge_seeded([seed_entity(n, s, "playable_hook", 900 - i) for i, (n, s) in enumerate(hooks)], outputs.get("playable_hook", []))
    outputs["location"] = merge_seeded([seed_entity(n, s, "location", 850 - i) for i, (n, s) in enumerate(locations)], outputs.get("location", []))
    outputs["npc"] = merge_seeded([seed_entity(n, s, "npc", 830 - i) for i, (n, s) in enumerate(npcs)], outputs.get("npc", []))
    outputs["faction"] = merge_seeded([seed_entity(n, s, "faction", 820 - i) for i, (n, s) in enumerate(factions)], outputs.get("faction", []))
    outputs["item"] = merge_seeded([seed_entity(n, s, "item", 800 - i) for i, (n, s) in enumerate(items)], outputs.get("item", []))
    outputs["technique"] = merge_seeded([seed_entity(n, s, "technique", 780 - i) for i, (n, s) in enumerate(techniques)], outputs.get("technique", []))
    return outputs


def build_game_rules(grouped: dict[str, dict[str, dict[str, Any]]]) -> dict[str, Any]:
    cultivation = entities(grouped, "cultivation_rule")
    locations = entities(grouped, "location")
    items = entities(grouped, "item")
    hooks = entities(grouped, "playable_hook")
    return {
        "action_rules": [
            {
                "action": "修炼/突破",
                "requirements": ["满足当前境界条件", "安全地点", "足够资源或机缘", "不能直接声明成功"],
                "risks": ["失败反噬", "资源损耗", "暴露气息", "被强者或势力注意"],
                "rewards": ["境界提升", "能力边界扩大", "解锁新地点或身份"],
                "source_entities": [row["name"] for row in cultivation[:20]],
            },
            {
                "action": "探索地点",
                "requirements": ["知道入口或路线", "具备最低自保能力"],
                "risks": ["敌对势力", "陷阱", "时间流逝", "错过其他事件"],
                "rewards": ["资源", "情报", "NPC关系", "任务线索"],
                "source_entities": [row["name"] for row in locations[:20]],
            },
            {
                "action": "交易/炼制/使用物品",
                "requirements": ["拥有货币、材料或对应技艺"],
                "risks": ["赝品", "价格波动", "副作用", "引人觊觎"],
                "rewards": ["恢复", "增益", "突破辅助", "剧情线索"],
                "source_entities": [row["name"] for row in items[:20]],
            },
        ],
        "hooks_to_surface": [row["summary"] for row in hooks[:30]],
    }


def curated_rows(outputs: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for ftype, entities_for_type in outputs.items():
        for entity in entities_for_type:
            rows.append(
                {
                    "type": ftype,
                    "name": entity.get("name", ""),
                    "claim": entity.get("summary", ""),
                    "aliases": entity.get("aliases", []),
                    "evidence_chunk_ids": entity.get("evidence_chunk_ids", []),
                    "confidence": entity.get("confidence", 0.0),
                    "quality": entity.get("quality", 0.0),
                    "score": entity.get("score", 0.0),
                    "conflict_status": entity.get("conflict_status", "clear"),
                }
            )
    rows.sort(key=lambda row: (float(row.get("score", 0)), float(row.get("quality", 0))), reverse=True)
    return rows


def quality_report(facts: list[dict[str, Any]], grouped: dict[str, dict[str, dict[str, Any]]], outputs: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    fact_counts = Counter(fact["type"] for fact in facts)
    entity_counts = {ftype: len(rows) for ftype, rows in outputs.items()}
    avg_quality = {
        ftype: round(sum(row.get("quality", 0) for row in rows) / len(rows), 3) if rows else 0.0
        for ftype, rows in outputs.items()
    }
    return {
        "fact_counts": dict(sorted(fact_counts.items())),
        "entity_counts": entity_counts,
        "average_quality": avg_quality,
        "notes": [
            "V2 favors canonical names, repeated mentions, and profile-specific terms.",
            "High-recall JSON files are still private working data; publish curated template slices instead of raw worlds.",
        ],
    }


def merge(world: str) -> None:
    wdir = world_dir(world)
    manifest = load_manifest(wdir, world)
    facts = read_jsonl(wdir / "facts.jsonl")
    if not facts:
        raise SystemExit("No facts found. Run extract.py first.")

    grouped = group_facts(facts)
    outputs = {
        "world_law": entities(grouped, "world_law"),
        "style_signal": entities(grouped, "style_signal"),
        "power_realm": entities(grouped, "power_realm"),
        "cultivation_rule": entities(grouped, "cultivation_rule"),
        "faction": entities(grouped, "faction"),
        "location": entities(grouped, "location"),
        "npc": entities(grouped, "npc"),
        "item": entities(grouped, "item"),
        "technique": entities(grouped, "technique"),
        "event": entities(grouped, "event"),
        "playable_hook": entities(grouped, "playable_hook"),
    }
    if manifest.get("profile") == "doupo":
        outputs = doupo_seed_outputs(outputs)

    write_json(wdir / "world_bible.json", {"world": world, "world_laws": outputs["world_law"], "style_signals": outputs["style_signal"]})
    write_json(wdir / "power_system.json", {"realms": outputs["power_realm"], "cultivation_rules": outputs["cultivation_rule"]})
    write_json(wdir / "factions.json", {"factions": outputs["faction"]})
    write_json(wdir / "locations.json", {"locations": outputs["location"]})
    write_json(wdir / "npcs.json", {"npcs": outputs["npc"]})
    write_json(wdir / "items.json", {"items": outputs["item"]})
    write_json(wdir / "techniques.json", {"techniques": outputs["technique"]})
    write_json(wdir / "timeline.json", {"events": outputs["event"]})
    write_json(wdir / "adventure_hooks.json", {"hooks": outputs["playable_hook"]})
    write_json(wdir / "game_rules.json", build_game_rules(grouped))
    write_jsonl(wdir / "curated_facts.jsonl", curated_rows(outputs))
    write_json(wdir / "quality_report.json", quality_report(facts, grouped, outputs))

    profile = build_rpg_profile(world)
    build_economy(world)
    build_quests(world)
    build_locations(world)
    build_relationship_rules(world)
    build_encounter_state(world)
    manifest["rpg_profile"] = "rpg_profile.json"
    manifest["item_market"] = "item_market.json"
    manifest["quest_templates"] = "quest_templates.json"
    manifest["location_runtime"] = "location_runtime.json"
    manifest["relationship_rules"] = "relationship_rules.json"
    manifest["encounter_state"] = "encounter_state.json"
    patches_path = wdir / "canon_patches.jsonl"
    if not patches_path.exists():
        write_jsonl(patches_path, [])
    player_state_path = wdir / "player_state.json"
    if not player_state_path.exists():
        write_json(player_state_path, apply_rpg_profile_to_state(default_player_state(world), profile, force_starter=True))
    else:
        state = read_json(player_state_path, {})
        state = migrate_player_state(state, world)
        state = apply_rpg_profile_to_state(state, load_rpg_profile(world))
        if "action_log" in state:
            state["action_log"] = state["action_log"][-30:]
        write_json(player_state_path, state)

    manifest["merged_files"] = [
        "world_bible.json",
        "power_system.json",
        "factions.json",
        "locations.json",
        "npcs.json",
        "items.json",
        "techniques.json",
        "timeline.json",
        "game_rules.json",
        "adventure_hooks.json",
        "rpg_profile.json",
        "item_market.json",
        "quest_templates.json",
        "location_runtime.json",
        "relationship_rules.json",
        "encounter_state.json",
        "curated_facts.jsonl",
        "quality_report.json",
    ]
    manifest["merger"] = "ranked_entities_v2"
    save_manifest(wdir, manifest)
    print(f"Merged {len(facts)} fact(s) into ranked canon files in {wdir}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Merge extracted facts into structured world canon.")
    parser.add_argument("--world", required=True)
    args = parser.parse_args()
    merge(args.world)


if __name__ == "__main__":
    main()
