#!/usr/bin/env python3
from __future__ import annotations

import argparse
from typing import Any

from common import load_manifest, read_json, read_jsonl, save_manifest, world_dir, write_json, write_jsonl


TYPE_RULES: dict[str, dict[str, list[str]]] = {
    "location": {
        "entry_conditions": ["知道路线或入口", "具备最低自保能力", "准备撤退方案"],
        "risks": ["敌对势力", "陷阱或环境危险", "时间流逝", "错过其他事件"],
        "rewards": ["资源", "情报", "NPC关系", "任务线索"],
    },
    "power_realm": {
        "entry_conditions": ["满足突破前置", "安全修炼地点", "足够资源或指导"],
        "risks": ["突破失败", "反噬或受伤", "资源损耗", "暴露气息"],
        "rewards": ["能力边界扩大", "可进入更危险区域", "获得更高势力评价"],
    },
    "cultivation_rule": {
        "entry_conditions": ["符合世界硬设定", "不能直接声明成功", "需要资源、时间或代价"],
        "risks": ["违反设定会失败", "代价被结算", "引发势力或环境反应"],
        "rewards": ["稳定成长", "解锁行动路线", "获得可解释的优势"],
    },
    "faction": {
        "entry_conditions": ["有接触渠道", "身份或利益足以开启互动", "行为未触发敌对阈值"],
        "risks": ["声望下降", "追杀或封锁", "人情债", "阵营绑定"],
        "rewards": ["庇护", "资源渠道", "任务", "身份背书"],
    },
    "npc": {
        "entry_conditions": ["找到对方", "给出合理话题或筹码", "尊重对方立场与实力"],
        "risks": ["被拒绝", "关系恶化", "暴露秘密", "被索要代价"],
        "rewards": ["情报", "指导", "交易", "任务或关系提升"],
    },
    "item": {
        "entry_conditions": ["拥有或能取得该物", "知道正确用途", "满足使用境界或技能"],
        "risks": ["副作用", "损耗", "被觊觎", "使用失败"],
        "rewards": ["恢复", "增益", "突破辅助", "交换价值"],
    },
    "technique": {
        "entry_conditions": ["拥有传承或口诀", "满足体质/境界/资源要求", "有训练时间"],
        "risks": ["走火入魔", "消耗过大", "熟练度不足", "暴露底牌"],
        "rewards": ["战斗选项", "移动或防御能力", "越级周旋的可能性"],
    },
    "event": {
        "entry_conditions": ["处于相关时间或地点", "知道线索", "愿意承担后果"],
        "risks": ["事件升级", "错失窗口", "势力介入", "不可逆后果"],
        "rewards": ["剧情推进", "声望变化", "关键线索", "新任务"],
    },
    "playable_hook": {
        "entry_conditions": ["接受钩子", "确认目标", "准备承担风险"],
        "risks": ["任务失败", "关系变化", "时间压力", "资源消耗"],
        "rewards": ["冒险入口", "成长机会", "新关系", "世界动态"],
    },
}


SOURCE_FILES = {
    "world_law": ("world_bible.json", "world_laws"),
    "style_signal": ("world_bible.json", "style_signals"),
    "power_realm": ("power_system.json", "realms"),
    "cultivation_rule": ("power_system.json", "cultivation_rules"),
    "faction": ("factions.json", "factions"),
    "location": ("locations.json", "locations"),
    "npc": ("npcs.json", "npcs"),
    "item": ("items.json", "items"),
    "technique": ("techniques.json", "techniques"),
    "event": ("timeline.json", "events"),
    "playable_hook": ("adventure_hooks.json", "hooks"),
}


def load_entities(wdir) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for ftype, (filename, key) in SOURCE_FILES.items():
        data = read_json(wdir / filename, {})
        for entity in data.get(key, []):
            row = dict(entity)
            row["type"] = ftype
            rows.append(row)
    return rows


def compact_summary(text: str, limit: int = 180) -> str:
    text = " ".join(str(text or "").split())
    return text[:limit]


def playable_entry(entity: dict[str, Any], schema: dict[str, Any]) -> dict[str, Any]:
    ftype = entity.get("type", "unknown")
    rules = TYPE_RULES.get(ftype, {
        "entry_conditions": ["有合理触发条件", "符合当前状态", "不违反 canon"],
        "risks": ["失败后果", "资源消耗", "关系变化"],
        "rewards": ["线索", "推进", "状态变化"],
    })
    name = str(entity.get("name") or ftype)
    summary = compact_summary(entity.get("summary") or entity.get("claim") or "")
    risk_axes = schema.get("risk_axes", [])
    core_actions = schema.get("core_actions", [])
    return {
        "name": name,
        "type": ftype,
        "summary": summary,
        "play_rule": f"当玩家围绕「{name}」行动时，先检查当前状态、地点、资源和关系；只能给出有代价、有风险、可解释的结果。",
        "entry_conditions": rules["entry_conditions"],
        "risks": rules["risks"] + [axis for axis in risk_axes if axis not in rules["risks"]][:2],
        "rewards": rules["rewards"],
        "suggested_actions": core_actions[:4],
        "hard_limits": [
            "玩家不能用一句话跳过前置条件",
            "缺少资源、等级、地点或情报时，只能得到部分进展或失败结果",
            "主持人可以补小设定，但不能改写硬 canon",
        ],
        "source_type": ftype,
        "source_quality": entity.get("quality", 0.0),
        "source_score": entity.get("score", 0.0),
    }


def distill(world: str) -> None:
    wdir = world_dir(world)
    manifest = load_manifest(wdir, world)
    world_profile = read_json(wdir / "world_profile.json", {})
    schema = world_profile.get("schema") or {}
    rows = load_entities(wdir)
    playable = [playable_entry(row, schema) for row in rows if row.get("name")]
    playable.sort(key=lambda row: (float(row.get("source_quality") or 0), float(row.get("source_score") or 0)), reverse=True)

    output = {
        "world": world,
        "profile": manifest.get("profile", "generic"),
        "genre": manifest.get("genre", world_profile.get("genre", "unknown")),
        "schema": schema,
        "entries": playable,
    }
    write_json(wdir / "playable_canon.json", output)
    write_jsonl(wdir / "playable_canon.jsonl", playable)
    manifest["playable_canon"] = "playable_canon.json"
    manifest["playable_canon_count"] = len(playable)
    save_manifest(wdir, manifest)
    print(f"Distilled {len(playable)} playable canon entries into {wdir / 'playable_canon.json'}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Turn merged canon into game-ready playable rules.")
    parser.add_argument("--world", required=True)
    args = parser.parse_args()
    distill(args.world)


if __name__ == "__main__":
    main()
