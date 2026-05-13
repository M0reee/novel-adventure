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
TEACHER_WORDS = ("老师", "师父", "导师", "药老", "长老", "管事", "教", "请教", "指点", "传授")
SCROLL_WORDS = ("卷轴", "秘籍", "功法", "斗技", "传承", "玉简", "书", "残篇")
SOURCE_WORDS = (*TEACHER_WORDS, *SCROLL_WORDS, "获得", "得到", "购买", "交换", "拜师", "准许", "资格")
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


def infer_source_type(summary: str) -> str:
    if any(word in summary for word in TEACHER_WORDS):
        return "teacher"
    if any(word in summary for word in SCROLL_WORDS):
        return "scroll"
    if any(word in summary for word in ("血脉", "体质", "种族")):
        return "bloodline"
    if any(word in summary for word in ("宗门", "家族", "学院", "势力")):
        return "faction"
    if any(word in summary for word in ("自创", "领悟", "顿悟")):
        return "self_created"
    return "unknown"


def canon_gate(row: dict[str, Any], name: str, summary: str, tier: int) -> dict[str, Any]:
    source_type = infer_source_type(summary)
    evidence_chunks = row.get("evidence_chunk_ids") or row.get("evidence") or []
    if not isinstance(evidence_chunks, list):
        evidence_chunks = [evidence_chunks]
    fact_id = row.get("fact_id") or row.get("id")
    evidence_fact_ids = [fact_id] if fact_id else []
    canon_confidence = "high" if evidence_chunks or evidence_fact_ids or row.get("source") == "profile_seed" else "medium"
    return {
        "canon_status": "confirmed" if canon_confidence == "high" else "inferred",
        "canon_confidence": canon_confidence,
        "playable_confidence": "medium" if source_type != "unknown" else "low",
        "source_type": source_type,
        "availability": "rumored",
        "learnable_by_player": "conditional",
        "acquisition_required": True,
        "numeric_source": "derived_low_impact",
        "unlock_conditions": {
            "level": max(1, tier),
            "requires_source": True,
            "source_type": source_type,
            "relationship_or_permission": source_type in {"teacher", "faction"},
            "item_or_text": source_type == "scroll",
            "safe_training": True,
        },
        "evidence_fact_ids": evidence_fact_ids,
        "evidence_chunk_ids": evidence_chunks[:5],
        "ooc_policy": f"原著出现「{name}」不等于玩家已学会；必须先获得来源、许可或传承，再训练到可用。",
    }


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
            "canon_gate": {
                "canon_status": "starter",
                "canon_confidence": "medium",
                "playable_confidence": "high",
                "source_type": "starter",
                "availability": "learned_at_start",
                "learnable_by_player": True,
                "acquisition_required": False,
                "numeric_source": "starter_low_impact",
                "unlock_conditions": {"level": 1, "requires_source": False},
                "evidence_fact_ids": [],
                "evidence_chunk_ids": [],
                "ooc_policy": "起步技能只代表最低限度自保能力，不声称来自原著主角传承。",
            },
            "category": "attack",
            "tier": 1,
            "unlock": {"level": 1, "requires": []},
            "runtime": {"mp_cost": 0, "power": 1.0, "accuracy_modifier": 0.0, "crit_modifier": 0.0},
            "canon_summary": "默认起步技能，只提供低影响战斗能力。",
        },
        {
            "skill_id": "steady_guard",
            "name": f"稳守{skill_label}",
            "canon_gate": {
                "canon_status": "starter",
                "canon_confidence": "medium",
                "playable_confidence": "medium",
                "source_type": "starter",
                "availability": "trainable_basic",
                "learnable_by_player": "conditional",
                "acquisition_required": False,
                "numeric_source": "starter_low_impact",
                "unlock_conditions": {"level": 2, "requires_source": False},
                "evidence_fact_ids": [],
                "evidence_chunk_ids": [],
                "ooc_policy": "基础防守动作只提供低影响数值，不冒充原著专属技能。",
            },
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
        gate = canon_gate(row, name, summary, tier)
        nodes.append(
            {
                "skill_id": stable_id("skill", name),
                "name": name,
                "canon_gate": gate,
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
        "policy": "Skill nodes are canon-gated availability records. A skill appearing in the source does not mean the player can learn it; source, permission, prerequisites and training state must be satisfied first.",
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


def skill_runtime(state: dict[str, Any]) -> dict[str, Any]:
    return state.setdefault("runtime", {}).setdefault("skill_progress", {})


def source_access_granted(node: dict[str, Any], player_input: str, state: dict[str, Any]) -> bool:
    gate = node.get("canon_gate", {})
    if not gate.get("acquisition_required", True):
        return True
    if any(word in player_input for word in SOURCE_WORDS):
        return True
    progress = skill_runtime(state).get(str(node.get("skill_id")), {})
    return progress.get("state") in {"source_acquired", "training", "usable"}


def training_gain(player_input: str) -> int:
    if any(word in player_input for word in ("练成", "掌握", "小成", "反复", "闭关")):
        return 45
    if any(word in player_input for word in ("训练", "练习", "修习", "学习", "领悟")):
        return 30
    return 15


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
        progress_rows = skill_runtime(state)
        progress = progress_rows.setdefault(
            str(node.get("skill_id")),
            {
                "skill_id": node.get("skill_id"),
                "name": name,
                "state": "rumored",
                "progress": 0,
                "source_type": node.get("canon_gate", {}).get("source_type", "unknown"),
                "notes": [],
            },
        )
        if not source_access_granted(node, player_input, state):
            progress["state"] = "source_known"
            progress.setdefault("notes", []).append("已知道该技能存在，但尚未获得传承、卷轴、导师许可或资格。")
            progress["notes"] = progress["notes"][-5:]
            return {
                "ok": False,
                "reason": f"你知道「{name}」存在，但还没有获得来源/传承，不能直接学会。",
                "progress": progress,
                "gate": node.get("canon_gate", {}),
            }
        unlock = node.get("unlock", {})
        level_req = int(unlock.get("level", 1))
        missing = [req for req in unlock.get("requires", []) if req not in known]
        if int(stats.get("level", 1)) < level_req or missing:
            progress["state"] = "blocked_by_prereq"
            return {"ok": False, "reason": f"「{name}」还不满足学习条件：等级至少 {level_req}，前置 {missing or '无'}。", "progress": progress, "gate": node.get("canon_gate", {})}
        progress["state"] = "training"
        progress["progress"] = min(100, int(progress.get("progress", 0)) + training_gain(player_input))
        progress.setdefault("notes", []).append(f"训练推进到 {progress['progress']}%。")
        progress["notes"] = progress["notes"][-5:]
        if progress["progress"] < 100:
            return {
                "ok": False,
                "reason": f"你开始修习「{name}」，但还没有达到可实战使用。当前训练进度 {progress['progress']}%。",
                "progress": progress,
                "gate": node.get("canon_gate", {}),
            }
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
        progress["state"] = "usable"
        return {"ok": True, "skill": learned, "node": node, "progress": progress}
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
