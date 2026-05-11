#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from typing import Any

from common import (
    default_player_state,
    load_manifest,
    read_json,
    read_jsonl,
    save_manifest,
    world_dir,
    write_json,
)


INTERNAL_STAT_LABELS = {
    "level": "等级",
    "exp": "经验",
    "exp_to_next": "下级经验",
    "hp": "生命",
    "max_hp": "生命上限",
    "mp": "能量",
    "max_mp": "能量上限",
    "attack": "攻击",
    "defense": "防御",
    "speed": "速度",
    "hit_rate": "命中",
    "dodge_rate": "闪避",
    "crit_rate": "暴击",
    "crit_damage": "暴伤",
    "damage_bonus": "增伤",
    "damage_reduction": "减伤",
}

RESOURCE_CANDIDATES = [
    ("斗气", ("斗气", "斗之气", "斗者", "斗师")),
    ("魂力", ("魂力", "魂环", "魂师", "魂骨")),
    ("灵力", ("灵力", "灵气", "灵根", "筑基", "金丹", "元婴")),
    ("法力", ("法力", "法术", "法师", "魔法")),
    ("魔力", ("魔力", "魔法", "魔导", "咒语")),
    ("真气", ("真气", "内力", "经脉", "武功")),
    ("查克拉", ("查克拉", "忍术", "忍者")),
    ("灵压", ("灵压", "斩魄刀", "死神")),
    ("气血", ("气血", "武者", "炼体", "血气")),
    ("精神力", ("精神力", "念力", "精神念师")),
    ("能源", ("能源", "机甲", "星舰", "电池", "动力炉")),
]

SPECIAL_SYSTEMS = [
    {
        "system_id": "soul_bones",
        "keywords": ("魂骨", "魂环", "武魂"),
        "equipment_name": "魂骨",
        "skill_name": "魂技",
        "slots": ["头部魂骨", "躯干魂骨", "左臂魂骨", "右臂魂骨", "左腿魂骨", "右腿魂骨", "外附魂骨"],
    },
    {
        "system_id": "artifacts",
        "keywords": ("法宝", "灵器", "飞剑", "符宝"),
        "equipment_name": "法宝",
        "skill_name": "术法",
        "slots": ["本命法宝", "护身法器", "飞行法器", "储物法器", "符箓"],
    },
    {
        "system_id": "douqi_gear",
        "keywords": ("纳戒", "异火", "斗技", "玄重尺"),
        "equipment_name": "随身器物",
        "skill_name": "斗技",
        "slots": ["武器", "护具", "纳戒", "异火", "丹药"],
    },
    {
        "system_id": "mecha_modules",
        "keywords": ("机甲", "装甲", "芯片", "星舰"),
        "equipment_name": "模块",
        "skill_name": "战术",
        "slots": ["主武器", "装甲", "核心芯片", "动力模块", "辅助模块"],
    },
]

GENRE_DEFAULTS = {
    "xuanhuan": {"resource": "灵力", "currency": "灵石", "skill": "功法/战技", "equipment": "装备"},
    "xianxia": {"resource": "灵力", "currency": "灵石", "skill": "术法", "equipment": "法宝"},
    "wuxia": {"resource": "内力", "currency": "银两", "skill": "武功", "equipment": "兵器"},
    "scifi": {"resource": "能源", "currency": "信用点", "skill": "战术", "equipment": "模块"},
    "mystery": {"resource": "理智", "currency": "资源点", "skill": "仪式", "equipment": "封印物"},
    "apocalypse": {"resource": "体力", "currency": "物资", "skill": "生存技能", "equipment": "装备"},
    "urban": {"resource": "精力", "currency": "现金", "skill": "技能", "equipment": "物品"},
    "generic": {"resource": "能量", "currency": "货币", "skill": "技能", "equipment": "装备"},
}

RESOURCE_CURRENCY_DEFAULTS = {
    "斗气": "金币",
    "魂力": "金魂币",
    "灵力": "灵石",
    "法力": "金币",
    "魔力": "金币",
    "真气": "银两",
    "内力": "银两",
    "能源": "信用点",
}


def compact_text(wdir) -> str:
    chunks = read_jsonl(wdir / "chunks.jsonl")
    sampled = chunks[:40] + chunks[-20:] if len(chunks) > 60 else chunks
    parts = [chunk.get("text", "") for chunk in sampled]
    for filename in ("power_system.json", "items.json", "techniques.json", "world_bible.json"):
        data = read_json(wdir / filename, {})
        parts.append(json.dumps(data, ensure_ascii=False))
    return "\n".join(parts)


def score_terms(text: str, terms: tuple[str, ...]) -> int:
    return sum(text.count(term) for term in terms)


def infer_resource(text: str, genre: str) -> str:
    scored = [(score_terms(text, terms), label) for label, terms in RESOURCE_CANDIDATES]
    scored.sort(reverse=True)
    if scored and scored[0][0] > 0:
        return scored[0][1]
    return GENRE_DEFAULTS.get(genre, GENRE_DEFAULTS["generic"])["resource"]


def infer_special_system(text: str, genre: str) -> dict[str, Any]:
    best = None
    best_score = 0
    for system in SPECIAL_SYSTEMS:
        score = score_terms(text, system["keywords"])
        if score > best_score:
            best = system
            best_score = score
    if best:
        return dict(best)
    defaults = GENRE_DEFAULTS.get(genre, GENRE_DEFAULTS["generic"])
    return {
        "system_id": f"{genre}_default",
        "equipment_name": defaults["equipment"],
        "skill_name": defaults["skill"],
        "slots": ["武器", "防具", "饰品"],
    }


def starter_kit(profile: dict[str, Any]) -> dict[str, Any]:
    resource = profile["terminology"]["mp"]
    equipment_name = profile["systems"]["equipment_name"]
    skill_name = profile["systems"]["skill_name"]
    slots = profile["systems"]["equipment_slots"]
    weapon_slot = slots[0] if slots else "武器"
    armor_slot = slots[1] if len(slots) > 1 else "防具"
    return {
        "equipment": {
            "primary": {
                "item_id": "starter_primary",
                "name": f"入门{weapon_slot}",
                "slot": weapon_slot,
                "stats": {"attack": 2},
                "description": f"符合当前世界观的基础{equipment_name}，只提供少量攻击加成。",
            },
            "defense": {
                "item_id": "starter_defense",
                "name": f"粗制{armor_slot}",
                "slot": armor_slot,
                "stats": {"defense": 1},
                "description": f"基础防护型{equipment_name}，防护有限。",
            },
            "special": None,
        },
        "skills": [
            {
                "skill_id": "starter_attack",
                "name": f"入门{skill_name}",
                "type": "attack",
                "mp_cost": 0,
                "resource_cost_label": resource,
                "cooldown": 0,
                "power": 1.0,
                "accuracy_modifier": 0.0,
                "crit_modifier": 0.0,
                "effects": [],
                "description": f"最基础的{skill_name}运用，伤害稳定，没有额外消耗。",
            }
        ],
    }


def default_rpg_profile(world: str, genre: str, text: str) -> dict[str, Any]:
    resource = infer_resource(text, genre)
    special = infer_special_system(text, genre)
    currency = RESOURCE_CURRENCY_DEFAULTS.get(resource, GENRE_DEFAULTS.get(genre, GENRE_DEFAULTS["generic"])["currency"])
    terminology = dict(INTERNAL_STAT_LABELS)
    terminology.update(
        {
            "mp": resource,
            "max_mp": f"{resource}上限",
            "exp": "历练",
            "exp_to_next": "下阶段历练",
            "level": "实力阶位",
            "coins": currency,
            "equipment": special["equipment_name"],
            "skills": special["skill_name"],
            "active_effects": "状态效果",
            "inventory": "行囊",
        }
    )
    profile = {
        "version": 1,
        "world": world,
        "genre": genre,
        "design": "内部计算字段保持通用；面向玩家的名称、装备槽、技能类型和货币由本文件映射到世界观。",
        "terminology": terminology,
        "systems": {
            "resource_name": resource,
            "currency_name": currency,
            "equipment_name": special["equipment_name"],
            "skill_name": special["skill_name"],
            "effect_name": "状态效果",
            "equipment_slots": special["slots"],
            "special_system_id": special["system_id"],
            "canon_first_completion": True,
            "allow_ai_gap_filling": True,
            "gap_filling_rule": "先用原文蒸馏到的硬设定；缺失数值只允许补成低影响、可解释、可被 canon_patches 覆盖的游戏参数。",
        },
        "formulas": {
            "hit_chance": "clamp(命中 + 技能命中修正 - 目标闪避, 5%, 98%)",
            "damage": "max(1, 攻击 * 技能倍率 - 目标防御) * 暴击倍率 * (1 + 增伤) * (1 - 目标减伤)",
            "resource_cost": f"技能先检查并扣除{resource}；不足则行动失败。",
            "rewards": f"击败敌人可获得历练、{currency}和掉落物，具体数值必须写入 player_state.json。",
        },
        "starter_kit": {},
        "derived_from": {
            "method": "keyword_profile_and_canon_files",
            "resource_candidates": [label for label, _ in RESOURCE_CANDIDATES],
            "completion_policy": "canon first, then conservative playable defaults",
        },
    }
    profile["starter_kit"] = starter_kit(profile)
    return profile


def build_rpg_profile(world: str) -> dict[str, Any]:
    wdir = world_dir(world)
    manifest = load_manifest(wdir, world)
    world_profile = read_json(wdir / "world_profile.json", {})
    genre = manifest.get("genre") or world_profile.get("genre") or ("xuanhuan" if manifest.get("profile") == "doupo" else "generic")
    text = compact_text(wdir)
    profile = default_rpg_profile(world, genre, text)
    write_json(wdir / "rpg_profile.json", profile)
    manifest["rpg_profile"] = "rpg_profile.json"
    save_manifest(wdir, manifest)
    state_path = wdir / "player_state.json"
    state = read_json(state_path, default_player_state(world))
    state = apply_rpg_profile_to_state(state, profile)
    write_json(state_path, state)
    print(f"Built rpg_profile.json resource={profile['systems']['resource_name']} equipment={profile['systems']['equipment_name']}")
    return profile


def load_rpg_profile(world: str) -> dict[str, Any]:
    wdir = world_dir(world)
    profile = read_json(wdir / "rpg_profile.json", {})
    if profile:
        return profile
    return build_rpg_profile(world)


def is_default_starter(player: dict[str, Any]) -> bool:
    equipment = player.get("equipment", {})
    skills = player.get("skills", [])
    equipment_ids = json.dumps(equipment, ensure_ascii=False)
    skill_ids = {skill.get("skill_id") for skill in skills if isinstance(skill, dict)}
    return (
        "worn_training_staff" in equipment_ids
        or "plain_cloth" in equipment_ids
        or "guarded_strike" in skill_ids
        or not equipment
        or not skills
    )


def apply_rpg_profile_to_state(state: dict[str, Any], profile: dict[str, Any], force_starter: bool = False) -> dict[str, Any]:
    player = state.setdefault("player", {})
    player["stat_labels"] = profile.get("terminology", INTERNAL_STAT_LABELS)
    player["rpg_systems"] = profile.get("systems", {})
    player.setdefault("currencies", {})
    currency_name = profile.get("systems", {}).get("currency_name", "货币")
    player["currencies"].setdefault("coins", 0)
    player["currencies_display"] = {"coins": currency_name}
    kit = profile.get("starter_kit", {})
    if kit and (force_starter or is_default_starter(player)):
        player["equipment"] = kit.get("equipment", player.get("equipment", {}))
        player["skills"] = kit.get("skills", player.get("skills", []))
    state["rpg_profile"] = {
        "file": "rpg_profile.json",
        "version": profile.get("version", 1),
        "resource_name": profile.get("systems", {}).get("resource_name", "能量"),
        "equipment_name": profile.get("systems", {}).get("equipment_name", "装备"),
        "skill_name": profile.get("systems", {}).get("skill_name", "技能"),
    }
    return state


def stat_label(profile: dict[str, Any], key: str) -> str:
    return profile.get("terminology", {}).get(key, INTERNAL_STAT_LABELS.get(key, key))


def format_stat_block(stats: dict[str, float], profile: dict[str, Any]) -> list[str]:
    return [
        f"- {stat_label(profile, 'hp')}：{int(stats.get('hp', 0))}/{int(stats.get('max_hp', 0))}",
        f"- {stat_label(profile, 'mp')}：{int(stats.get('mp', 0))}/{int(stats.get('max_mp', 0))}",
        f"- {stat_label(profile, 'attack')}/{stat_label(profile, 'defense')}/{stat_label(profile, 'speed')}：{int(stats.get('attack', 0))}/{int(stats.get('defense', 0))}/{int(stats.get('speed', 0))}",
        f"- {stat_label(profile, 'hit_rate')}/{stat_label(profile, 'dodge_rate')}/{stat_label(profile, 'crit_rate')}：{stats.get('hit_rate', 0):.0%}/{stats.get('dodge_rate', 0):.0%}/{stats.get('crit_rate', 0):.0%}",
        f"- {stat_label(profile, 'crit_damage')}/{stat_label(profile, 'damage_bonus')}/{stat_label(profile, 'damage_reduction')}：{stats.get('crit_damage', 0):.1f}x/{stats.get('damage_bonus', 0):.0%}/{stats.get('damage_reduction', 0):.0%}",
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description="Build or inspect a world's RPG terminology and systems profile.")
    parser.add_argument("--world", required=True)
    parser.add_argument("--rebuild", action="store_true")
    args = parser.parse_args()
    profile = build_rpg_profile(args.world) if args.rebuild else load_rpg_profile(args.world)
    print(json.dumps(profile, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
