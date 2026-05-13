#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections import Counter
from typing import Any

from common import load_manifest, read_json, save_manifest, world_dir, write_json


CANON_FILES = [
    "world_bible.json",
    "power_system.json",
    "game_rules.json",
    "items.json",
    "techniques.json",
    "factions.json",
    "locations.json",
    "npcs.json",
    "timeline.json",
    "adventure_hooks.json",
    "playable_canon.json",
    "rpg_profile.json",
    "item_market.json",
    "story_arcs.json",
]

DIRECT_MECHANISM_SOURCES = {
    "world_bible.json",
    "power_system.json",
    "items.json",
    "techniques.json",
    "factions.json",
    "locations.json",
    "npcs.json",
    "timeline.json",
    "adventure_hooks.json",
    "story_arcs.json",
}

MECHANISM_KEYWORDS: dict[str, tuple[str, ...]] = {
    "power_tier_pressure": ("境界", "等级", "阶位", "位阶", "压制", "越级", "修为", "层级", "实力差距"),
    "resource_backlash": ("反噬", "走火", "失控", "过载", "副作用", "代价", "承受力", "失败代价"),
    "consumable_crafting": ("丹药", "药剂", "炼药", "炼制", "材料", "魔核", "药材", "消耗品", "配方"),
    "equipment_dependency": ("装备", "法宝", "武器", "护甲", "魂骨", "义体", "机甲", "模块", "封印物", "神器"),
    "ammo_or_charge": ("弹药", "子弹", "弹夹", "充能", "能量匣", "电池", "能源", "燃料"),
    "alert_tracking": ("警报", "监控", "追踪", "通缉", "暴露", "坐标", "摄像头", "痕迹"),
    "sanity_contamination": ("理智", "污染", "禁忌", "诅咒", "腐化", "畸变", "精神"),
    "infection_noise": ("感染", "噪音", "尸潮", "异变", "伤口", "饥饿", "物资"),
    "reputation_law": ("声望", "名声", "律法", "规矩", "通缉", "宗门规矩", "家法", "军纪"),
    "market_window": ("拍卖", "市场", "黑市", "商会", "交易", "价格", "缺货", "购买", "货币"),
    "faction_reaction": ("势力", "宗门", "家族", "公司", "教会", "军团", "公会", "阵营", "关系"),
    "location_access": ("入口", "路线", "禁地", "秘境", "遗迹", "副本", "封锁", "通行", "探索"),
}

MECHANISM_RULES: dict[str, dict[str, Any]] = {
    "power_tier_pressure": {
        "risk": "能力层级差会限制正面对抗，越级行动必须有资源、战术或外力依据。",
        "effect": {"type": "state", "key": "power_gap_checked", "value": True},
    },
    "resource_backlash": {
        "risk": "强行突破、过载使用能力或失败施法会带来反噬/副作用。",
        "effect": {"type": "state", "key": "backlash_risk_active", "value": True},
    },
    "consumable_crafting": {
        "risk": "关键消耗品、材料和制作能力会决定恢复、突破或交易空间。",
        "effect": {"type": "state", "key": "consumable_pressure_active", "value": True},
    },
    "equipment_dependency": {
        "risk": "装备、器物或外置能力会影响战斗边界，损坏和适配性需要裁定。",
        "effect": {"type": "state", "key": "equipment_dependency_checked", "value": True},
    },
    "ammo_or_charge": {
        "risk": "弹药、充能或能源不足会限制连续战斗和逃生选择。",
        "effect": {"type": "state", "key": "ammo_or_charge_pressure", "value": True},
    },
    "alert_tracking": {
        "risk": "战斗和高调行动可能留下可追踪痕迹，触发警报、通缉或追杀。",
        "effect": {"type": "state", "key": "alert_level", "value": "raised"},
    },
    "sanity_contamination": {
        "risk": "接触禁忌、污染或精神冲击时，胜利也可能留下长期代价。",
        "effect": {"type": "state", "key": "contamination_trace", "value": True},
    },
    "infection_noise": {
        "risk": "噪音、感染和物资消耗会把单场冲突扩散成持续生存压力。",
        "effect": {"type": "state", "key": "noise_or_infection_risk", "value": True},
    },
    "reputation_law": {
        "risk": "公开行为会改变名声、规矩评价或执法/宗门反应。",
        "effect": {"type": "state", "key": "reputation_consequence_pending", "value": True},
    },
    "market_window": {
        "risk": "交易窗口、价格、资格和竞争者会影响资源获取。",
        "effect": {"type": "state", "key": "market_window_checked", "value": True},
    },
    "faction_reaction": {
        "risk": "势力会记住玩家行为，庇护、敌意和人情债会随行动变化。",
        "effect": {"type": "state", "key": "faction_reaction_pending", "value": True},
    },
    "location_access": {
        "risk": "地点入口、路线和封锁条件会限制探索，不能无视距离和准入条件。",
        "effect": {"type": "state", "key": "location_access_checked", "value": True},
    },
}

EVENT_TO_MECHANISMS = {
    "auction": ("market_window", "consumable_crafting", "faction_reaction"),
    "faction": ("faction_reaction", "reputation_law"),
    "exploration": ("location_access", "resource_backlash"),
    "threat": ("alert_tracking", "infection_noise", "sanity_contamination", "faction_reaction"),
    "training": ("power_tier_pressure", "resource_backlash", "consumable_crafting"),
}


def rows_from(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [row for row in value if isinstance(row, dict)]
    if isinstance(value, dict):
        rows: list[dict[str, Any]] = []
        for child in value.values():
            rows.extend(rows_from(child))
        return rows
    return []


def text_of(row: dict[str, Any]) -> str:
    parts: list[str] = []
    for key in ("name", "summary", "claim", "description", "action"):
        if row.get(key):
            parts.append(str(row[key]))
    for key in ("requirements", "risks", "rewards", "source_entities", "aliases"):
        value = row.get(key)
        if isinstance(value, list):
            parts.extend(str(item) for item in value[:20])
    for key in ("why_it_matters", "entry_conditions", "progression_loops", "key_terms"):
        value = row.get(key)
        if isinstance(value, list):
            parts.extend(str(item) for item in value[:20])
    claims = row.get("claims")
    if isinstance(claims, list):
        for claim in claims[:5]:
            if isinstance(claim, dict):
                parts.append(str(claim.get("claim", "")))
            else:
                parts.append(str(claim))
    return " ".join(part for part in parts if part)


def load_canon_rows(world: str) -> tuple[dict[str, list[dict[str, Any]]], list[dict[str, Any]]]:
    wdir = world_dir(world)
    by_file: dict[str, list[dict[str, Any]]] = {}
    evidence: list[dict[str, Any]] = []
    for filename in CANON_FILES:
        data = read_json(wdir / filename, {})
        rows = rows_from(data)
        by_file[filename] = rows
        for row in rows:
            text = text_of(row)
            if not text:
                continue
            evidence.append(
                {
                    "source": filename,
                    "name": str(row.get("name") or row.get("action") or row.get("title") or ""),
                    "text": text,
                }
            )
    return by_file, evidence


def evidence_for_mechanisms(evidence: list[dict[str, Any]]) -> dict[str, list[dict[str, str]]]:
    hits: dict[str, list[dict[str, str]]] = {key: [] for key in MECHANISM_KEYWORDS}
    for item in evidence:
        if item["source"] not in DIRECT_MECHANISM_SOURCES:
            continue
        text = item["text"]
        for mechanism, words in MECHANISM_KEYWORDS.items():
            matched = [word for word in words if word in text]
            if matched:
                hits[mechanism].append(
                    {
                        "source": item["source"],
                        "name": item["name"],
                        "matched": matched[0],
                        "claim": text[:180],
                    }
                )
    return {key: value for key, value in hits.items() if value}


def top_names(rows: list[dict[str, Any]], limit: int = 8) -> list[str]:
    names: list[str] = []
    for row in rows:
        name = str(row.get("name") or row.get("title") or "").strip()
        if name and name not in names:
            names.append(name)
        if len(names) >= limit:
            break
    return names


def choose_named(rows: list[dict[str, Any]], keywords: tuple[str, ...], fallback_limit: int = 1) -> list[str]:
    preferred: list[str] = []
    fallback = top_names(rows, fallback_limit)
    for row in rows:
        text = text_of(row)
        name = str(row.get("name") or row.get("title") or "").strip()
        if name and any(word in text for word in keywords) and name not in preferred:
            preferred.append(name)
    return (preferred or fallback)[:fallback_limit]


def choose_market_items(rows: list[dict[str, Any]], fallback_rows: list[dict[str, Any]], limit: int = 3) -> list[str]:
    scored: list[tuple[int, int, str]] = []
    for index, row in enumerate(rows):
        name = str(row.get("name") or "").strip()
        if not name:
            continue
        text = text_of(row)
        score = 0
        price = row.get("price_range")
        if isinstance(price, list) and len(price) == 2 and (int(price[0]) > 0 or int(price[1]) > 0):
            score += 2
        if any(word in text for word in ("突破", "辅助", "修炼", "恢复")):
            score += 4
        if "不可常规购买" in text or "长期主线探索" in text:
            score -= 5
        if any(word in text for word in ("丹药", "药剂", "药材", "材料", "辅助", "恢复", "购买", "拍卖")):
            score += 3
        if any(word in text for word in ("神话", "终极", "传说", "不可", "唯一")):
            score -= 2
        if score > 0:
            scored.append((score, -index, name))
    scored.sort(reverse=True)
    names = []
    for _, _, name in scored:
        if name not in names:
            names.append(name)
        if len(names) >= limit:
            return names
    for name in choose_named(fallback_rows, ("丹药", "药剂", "药材", "材料", "资源", "辅助", "恢复", "消耗"), limit):
        if name not in names:
            names.append(name)
        if len(names) >= limit:
            break
    return names


def event_effect_templates(
    mechanisms: set[str],
    items: list[str],
    locations: list[str],
    factions: list[str],
) -> dict[str, dict[str, list[dict[str, Any]]]]:
    templates: dict[str, dict[str, list[dict[str, Any]]]] = {}
    if "market_window" in mechanisms and items:
        auction_item = items[0]
        templates["auction"] = {
            "ignored": [
                {
                    "type": "market",
                    "item": auction_item,
                    "availability": "scarce",
                    "price_multiplier": 1.2,
                    "source": "gameplay_profile",
                },
                {"type": "state", "key": "missed_market_window", "value": True, "source": "gameplay_profile"},
            ],
            "intervened": [
                {"type": "state", "key": "market_contact_open", "value": True, "source": "gameplay_profile"}
            ],
        }
        if locations:
            templates["auction"]["intervened"].append(
                {
                    "type": "location",
                    "location": locations[0],
                    "add_actions": [f"追踪{auction_item}相关交易"],
                    "source": "gameplay_profile",
                }
            )
    if "faction_reaction" in mechanisms and factions:
        templates["faction"] = {
            "ignored": [{"type": "relationship", "target": factions[0], "delta": -5, "source": "gameplay_profile"}],
            "intervened": [{"type": "relationship", "target": factions[0], "delta": 5, "source": "gameplay_profile"}],
        }
    if ("location_access" in mechanisms or "alert_tracking" in mechanisms) and locations:
        templates["threat"] = {
            "ignored": [
                {"type": "location", "location": locations[0], "risk_level": "high", "source": "gameplay_profile"}
            ],
            "intervened": [{"type": "state", "key": "threat_contained", "value": True, "source": "gameplay_profile"}],
        }
    return templates


def event_trigger_templates(mechanisms: set[str], items: list[str]) -> dict[str, list[dict[str, Any]]]:
    if "market_window" not in mechanisms or not items:
        return {}
    item = items[0]
    return {
        "auction": [
            {
                "when": "intervened",
                "create_event": {
                    "title_suffix": f"后续：筹措{item}",
                    "summary": f"玩家获得{item}相关入口后，需要在窗口期内筹措货币、材料、人情或替代资源。",
                    "type": "opportunity",
                    "starts_after": 1,
                    "duration": 4,
                    "if_ignored": [f"{item}获取窗口关闭", "竞争者获得先机"],
                    "if_intervened": [f"获得{item}、替代资源或折扣入口"],
                },
            }
        ]
    }


def build_combat_profile(
    mechanisms: set[str],
    hits: dict[str, list[dict[str, str]]],
    rpg_profile: dict[str, Any],
) -> dict[str, Any]:
    enabled = [key for key in MECHANISM_RULES if key in mechanisms]
    effects = [MECHANISM_RULES[key]["effect"] | {"source": "gameplay_profile"} for key in enabled if MECHANISM_RULES[key].get("effect")]
    resource_name = rpg_profile.get("systems", {}).get("resource_name") or rpg_profile.get("terminology", {}).get("mp") or "资源"
    risks = [MECHANISM_RULES[key]["risk"] for key in enabled]
    if not risks:
        risks = ["没有足够 canon 证据启用题材专属战斗机制；仅使用通用生命、资源、攻击、防御和行动代价裁定。"]
    confidence = "high" if len(enabled) >= 5 else "medium" if len(enabled) >= 2 else "low"
    return {
        "derived_from_canon": bool(enabled),
        "canon_confidence": confidence,
        "enabled_mechanics": enabled,
        "disabled_mechanics": [key for key in MECHANISM_RULES if key not in mechanisms],
        "secondary_risks": risks[:8],
        "resource_pressure": f"战斗必须检查{resource_name}、生命、位置、装备/能力条件和 canon 边界；不能只按玩家声明成功。",
        "effects_on_attack": effects[:6],
        "victory_note": "胜利仍需结算资源消耗、关系/声望、追踪痕迹和地点后果；只结算有 canon 证据支持的后果。",
        "fallback_used": not bool(enabled),
        "evidence_count": sum(len(hits.get(key, [])) for key in enabled),
    }


def build_gameplay_profile(world: str) -> dict[str, Any]:
    wdir = world_dir(world)
    by_file, evidence = load_canon_rows(world)
    hits = evidence_for_mechanisms(evidence)
    mechanisms = set(hits)
    rpg_profile = read_json(wdir / "rpg_profile.json", {})
    item_rows = by_file.get("items.json", [])
    market_rows = by_file.get("item_market.json", [])
    items = choose_named(item_rows, ("丹药", "药剂", "材料", "资源", "弹药", "能源", "关键", "消耗"), 3)
    if not items:
        items = choose_named(by_file.get("playable_canon.json", []), ("资源", "物品", "材料", "装备", "消耗"), 3)
    market_items = choose_market_items(market_rows, item_rows, 3)
    locations = choose_named(by_file.get("locations.json", []), ("城", "市场", "拍卖", "禁地", "入口", "区域", "地点", "学院"), 3)
    factions = choose_named(by_file.get("factions.json", []), ("家族", "宗门", "公司", "教会", "军团", "公会", "势力", "阵营"), 3)
    story_arcs = top_names(by_file.get("story_arcs.json", []), 6)
    confidence_counts = Counter(source for values in hits.values() for row in values[:5] for source in [row["source"]])
    profile = {
        "version": 1,
        "world": world,
        "policy": "Canon-first gameplay profile. Mechanics are enabled only when distilled canon contains supporting evidence; broad genre labels are low-confidence fallback and must not override canon.",
        "source_priority": [
            "canon_patches",
            "distilled_canon",
            "gameplay_profile",
            "genre_fallback_low_confidence",
            "generic_fallback",
        ],
        "canon_confidence": "high" if len(mechanisms) >= 7 else "medium" if len(mechanisms) >= 3 else "low",
        "canon_entities": {
            "items": items,
            "market_items": market_items,
            "locations": locations,
            "factions": factions,
            "story_arcs": story_arcs,
        },
        "mechanisms": {
            key: {
                "enabled": key in mechanisms,
                "evidence_count": len(hits.get(key, [])),
                "evidence": hits.get(key, [])[:5],
            }
            for key in MECHANISM_RULES
        },
        "combat": build_combat_profile(mechanisms, hits, rpg_profile),
        "events": {
            "enabled_mechanisms": sorted(mechanisms.intersection({m for values in EVENT_TO_MECHANISMS.values() for m in values})),
            "default_effects": event_effect_templates(mechanisms, market_items or items, locations, factions),
            "default_triggers": event_trigger_templates(mechanisms, market_items or items),
            "fallback_used": not bool(mechanisms),
        },
        "evidence_summary": {
            "total_evidence_rows": len(evidence),
            "sources": dict(sorted(confidence_counts.items())),
        },
    }
    write_json(wdir / "gameplay_profile.json", profile)
    manifest = load_manifest(wdir, world)
    manifest["gameplay_profile"] = "gameplay_profile.json"
    save_manifest(wdir, manifest)
    print(
        f"Built gameplay_profile.json mechanics={len(mechanisms)} "
        f"confidence={profile['canon_confidence']}"
    )
    return profile


def load_gameplay_profile(world: str) -> dict[str, Any]:
    wdir = world_dir(world)
    data = read_json(wdir / "gameplay_profile.json", {})
    return data if data else build_gameplay_profile(world)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build canon-derived gameplay profile.")
    parser.add_argument("--world", required=True)
    parser.add_argument("--rebuild", action="store_true")
    args = parser.parse_args()
    data = build_gameplay_profile(args.world) if args.rebuild else load_gameplay_profile(args.world)
    print(
        f"world={data.get('world')} confidence={data.get('canon_confidence')} "
        f"mechanics={len([k for k, v in data.get('mechanisms', {}).items() if v.get('enabled')])}"
    )


if __name__ == "__main__":
    main()
