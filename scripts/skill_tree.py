#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
from typing import Any

from common import load_manifest, read_json, save_manifest, world_dir, write_json
from rpg_profile import load_rpg_profile


ATTACK_WORDS = ("攻击", "掌", "拳", "剑", "刀", "枪", "尺", "火", "雷", "斩", "击", "斗技")
DEFENSE_WORDS = ("防", "护", "盾", "甲", "身法", "躲", "避", "守")
SUPPORT_WORDS = ("炼", "丹", "药", "恢复", "治疗", "增幅", "辅助", "阵", "符")
MOVEMENT_WORDS = ("步", "身", "遁", "飞", "行", "闪", "移")
SKILL_NAME_WORDS = ("掌", "拳", "印", "决", "诀", "步", "剑", "刀", "枪", "尺", "术", "法", "功", "技", "崩", "火", "雷")
GENERIC_NAMES = {"成功", "斗技", "功法", "高级斗技", "玄阶斗技", "天阶斗技", "玄阶功", "斗气功", "成人仪式"}
BAD_NAME_PARTS = (
    "手掌",
    "脚掌",
    "手指",
    "拳头",
    "一阵",
    "嘴角",
    "伸出",
    "旋即",
    "其",
    "萧炎",
    "少女",
    "男子",
    "老者",
    "成功",
    "属性",
    "可能",
    "恐怕",
    "这是",
    "你那",
    "比天",
    "方才",
)


def stable_id(prefix: str, name: str) -> str:
    digest = hashlib.sha1(name.encode("utf-8")).hexdigest()[:10]
    return f"{prefix}_{digest}"


def valid_name(name: str) -> bool:
    stripped = name.strip(" 「」《》“”？！!?.。")
    if not stripped or len(stripped) > 8:
        return False
    if stripped in GENERIC_NAMES:
        return False
    if any(part in stripped for part in BAD_NAME_PARTS):
        return False
    if any(word in stripped for word in ("这", "那", "你", "我", "他", "她", "是", "的", "了", "有", "级", "阶", "什么")):
        return False
    if any(mark in stripped for mark in ("。", "，", "；", "：", "\n", "什么", "不会", "没有")):
        return False
    return any(word in stripped for word in SKILL_NAME_WORDS)


def quoted_skill_names(text: str) -> list[str]:
    names: list[str] = []
    for match in re.findall(r"[:：]\s*([一-龥A-Za-z0-9]{2,8})", text):
        candidate = match.strip()
        if valid_name(candidate) and candidate not in names:
            names.append(candidate)
    for match in re.findall(r"[“「《]([^”」》]{2,18})[”」》]", text):
        candidate = match.split("：")[-1].split(":")[-1].strip("？！!?.。 ")
        if valid_name(candidate) and candidate not in names:
            names.append(candidate)
    return names


def skill_category(name: str, summary: str) -> str:
    text = f"{name} {summary}"
    if any(word in text for word in ATTACK_WORDS):
        return "attack"
    if any(word in text for word in DEFENSE_WORDS):
        return "defense"
    if any(word in text for word in MOVEMENT_WORDS):
        return "movement"
    if any(word in text for word in SUPPORT_WORDS):
        return "support"
    return "utility"


def node_stats(category: str, tier: int) -> dict[str, Any]:
    mp_cost = max(0, tier * 3)
    if category == "attack":
        return {"mp_cost": mp_cost, "power": round(1.0 + tier * 0.15, 2), "accuracy_modifier": 0.0, "crit_modifier": min(0.1, tier * 0.01)}
    if category == "defense":
        return {"mp_cost": mp_cost, "power": 0.8, "accuracy_modifier": 0.03, "crit_modifier": 0.0, "effect": {"modifiers": {"damage_reduction": min(0.12, tier * 0.02)}, "duration_turns": 2}}
    if category == "movement":
        return {"mp_cost": mp_cost, "power": 0.75, "accuracy_modifier": 0.05, "crit_modifier": 0.0, "effect": {"modifiers": {"dodge_rate": min(0.12, tier * 0.02)}, "duration_turns": 2}}
    if category == "support":
        return {"mp_cost": mp_cost, "power": 0.7, "accuracy_modifier": 0.0, "crit_modifier": 0.0, "effect": {"modifiers": {"damage_bonus": min(0.1, tier * 0.015)}, "duration_turns": 3}}
    return {"mp_cost": mp_cost, "power": 1.0, "accuracy_modifier": 0.0, "crit_modifier": 0.0}


def infer_tier(name: str, summary: str, fallback_index: int) -> int:
    text = f"{name} {summary}"
    if any(word in text for word in ("低级", "入门", "基础")):
        return 1
    if any(word in text for word in ("帝", "佛怒", "异火", "天阶", "黄泉", "五轮", "离火")):
        return 5
    if any(word in text for word in ("地阶", "玄阶高级", "高阶", "八极崩")):
        return 3
    if any(word in text for word in ("玄阶", "弄炎", "身法")):
        return 2
    return min(5, 1 + fallback_index // 4)


def technique_rows(world: str) -> list[dict[str, Any]]:
    wdir = world_dir(world)
    techniques = read_json(wdir / "techniques.json", {}).get("techniques", [])
    playable = read_json(wdir / "playable_canon.json", {}).get("entries", [])
    rows: list[dict[str, Any]] = []
    for item in techniques:
        if isinstance(item, dict) and valid_name(str(item.get("name", ""))):
            rows.append(item)
        if isinstance(item, dict):
            summary = str(item.get("summary") or item.get("claim") or "")
            for name in quoted_skill_names(summary):
                rows.append({"name": name, "summary": summary, "source": "techniques.json"})
    for item in playable:
        if isinstance(item, dict) and "technique" in str(item.get("type", "")) and valid_name(str(item.get("name", ""))):
            rows.append({"name": item.get("name"), "summary": item.get("claim", ""), "source": item.get("source_json", "playable_canon.json")})
    seen: set[str] = set()
    unique = []
    for row in rows:
        name = str(row.get("name", ""))
        if name and name not in seen:
            seen.add(name)
            unique.append(row)
    return unique[:18]


def fallback_nodes(profile: dict[str, Any]) -> list[dict[str, Any]]:
    skill_label = profile.get("systems", {}).get("skill_name", "技能")
    return [
        {
            "skill_id": "guarded_strike",
            "name": f"入门{skill_label}",
            "category": "attack",
            "tier": 1,
            "unlock": {"level": 1, "requires": []},
            "runtime": {"mp_cost": 0, "power": 1.0, "accuracy_modifier": 0.0, "crit_modifier": 0.0},
            "canon_summary": "默认起步技能，只提供低影响战斗能力。",
        },
        {
            "skill_id": "steady_guard",
            "name": f"稳守{skill_label}",
            "category": "defense",
            "tier": 1,
            "unlock": {"level": 2, "requires": ["guarded_strike"]},
            "runtime": node_stats("defense", 1),
            "canon_summary": "低阶防守技能，用于把高风险行动降级为准备或试探。",
        },
    ]


def build_skill_tree(world: str) -> dict[str, Any]:
    wdir = world_dir(world)
    profile = load_rpg_profile(world)
    rows = technique_rows(world)
    nodes: list[dict[str, Any]] = []
    for idx, row in enumerate(rows):
        name = str(row.get("name", "")).strip()
        summary = str(row.get("summary") or row.get("claim") or "")
        category = skill_category(name, summary)
        tier = infer_tier(name, summary, idx)
        runtime = node_stats(category, tier)
        nodes.append(
            {
                "skill_id": stable_id("skill", name),
                "name": name,
                "category": category,
                "tier": tier,
                "unlock": {"level": max(1, tier), "requires": [] if tier <= 1 or not nodes else [nodes[-1]["skill_id"]]},
                "runtime": runtime,
                "canon_summary": summary[:180],
                "source": row.get("source", "techniques.json"),
            }
        )
    if not nodes:
        nodes = fallback_nodes(profile)
    else:
        nodes.sort(key=lambda row: (int(row.get("tier", 1)), str(row.get("name", ""))))
        previous_by_tier: dict[int, str] = {}
        for node in nodes:
            tier = int(node.get("tier", 1))
            requires = []
            lower = max((level for level in previous_by_tier if level < tier), default=0)
            if tier > 1 and lower:
                requires = [previous_by_tier[lower]]
            node["unlock"] = {"level": max(1, tier), "requires": requires}
            previous_by_tier[tier] = str(node.get("skill_id"))
    output = {
        "world": world,
        "policy": "Skill nodes are derived from distilled techniques/playable canon. Missing numeric values are low-impact playable parameters, not hard canon.",
        "resource_name": profile.get("systems", {}).get("resource_name", "能量"),
        "skill_name": profile.get("systems", {}).get("skill_name", "技能"),
        "nodes": nodes,
    }
    write_json(wdir / "skill_tree.json", output)
    manifest = load_manifest(wdir, world)
    manifest["skill_tree"] = "skill_tree.json"
    save_manifest(wdir, manifest)
    print(f"Built skill_tree.json nodes={len(nodes)}")
    return output


def load_skill_tree(world: str) -> dict[str, Any]:
    data = read_json(world_dir(world) / "skill_tree.json", {})
    return data if data else build_skill_tree(world)


def learned_skill_ids(player: dict[str, Any]) -> set[str]:
    return {str(skill.get("skill_id")) for skill in player.get("skills", []) if isinstance(skill, dict)}


def learn_skill(world: str, state: dict[str, Any], player_input: str) -> dict[str, Any] | None:
    if not any(word in player_input for word in ("学习", "修习", "领悟", "练成", "掌握")):
        return None
    tree = load_skill_tree(world)
    player = state.setdefault("player", {})
    stats = player.setdefault("stats", {})
    known = learned_skill_ids(player)
    for node in tree.get("nodes", []):
        name = str(node.get("name", ""))
        if not name or name not in player_input:
            continue
        if node.get("skill_id") in known:
            return {"ok": False, "reason": f"你已经掌握「{name}」。"}
        unlock = node.get("unlock", {})
        level_req = int(unlock.get("level", 1))
        missing = [req for req in unlock.get("requires", []) if req not in known]
        if int(stats.get("level", 1)) < level_req or missing:
            return {"ok": False, "reason": f"「{name}」还不满足学习条件：等级至少 {level_req}，前置 {missing or '无'}。"}
        runtime = node.get("runtime", {})
        learned = {
            "skill_id": node.get("skill_id"),
            "name": name,
            "type": node.get("category", "attack"),
            "mp_cost": runtime.get("mp_cost", 0),
            "power": runtime.get("power", 1.0),
            "accuracy_modifier": runtime.get("accuracy_modifier", 0.0),
            "crit_modifier": runtime.get("crit_modifier", 0.0),
            "effects": [runtime["effect"]] if runtime.get("effect") else [],
            "description": node.get("canon_summary", ""),
        }
        player.setdefault("skills", []).append(learned)
        return {"ok": True, "skill": learned, "node": node}
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description="Build or inspect canon-derived skill tree.")
    parser.add_argument("--world", required=True)
    parser.add_argument("--rebuild", action="store_true")
    args = parser.parse_args()
    data = build_skill_tree(args.world) if args.rebuild else load_skill_tree(args.world)
    print(json.dumps(data, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
