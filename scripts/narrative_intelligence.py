#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
from typing import Any

from common import load_manifest, read_json, save_manifest, world_dir, write_json


MOTIVE_WORDS = ("目标", "野心", "希望", "想", "寻找", "维持", "保护", "复仇", "利益", "信任", "合作")
FEAR_WORDS = ("害怕", "担心", "忌惮", "风险", "得罪", "追杀", "暴露", "失败", "债务", "封锁")
LEVERAGE_WORDS = ("资源", "情报", "人脉", "渠道", "指导", "庇护", "交易", "身份", "实力")
BOUNDARY_WORDS = ("不会", "不能", "不可", "必须", "需要", "代价", "条件", "限制", "风险")

CAN_DO_WORDS = ("可以", "能够", "适合", "提升", "增强", "克制", "辅助", "提供", "解锁")
CANNOT_WORDS = ("不能", "不可", "无法", "不会", "不得", "不能直接", "不等于")
COST_WORDS = ("消耗", "代价", "材料", "货币", "时间", "精神", "体魄", "资源")
RISK_WORDS = ("反噬", "副作用", "暴露", "失败", "追踪", "觊觎", "过载", "污染", "重伤", "死亡")
REQ_WORDS = ("需要", "必须", "满足", "拥有", "知道", "准备", "境界", "身份", "技能", "地点")
SCALING_WORDS = ("随", "提升", "进化", "等级", "境界", "熟练", "高阶", "成长")

FORESHADOW_WORDS = ("传闻", "秘密", "过去", "身份", "异常", "残图", "线索", "隐藏", "暗中", "布局", "长期", "真相", "灵魂")
EVENT_WORDS = ("退婚", "拍卖", "试炼", "追杀", "争夺", "战争", "封锁", "招生", "结盟", "复仇", "主线")


def entity_text(row: dict[str, Any]) -> str:
    parts = [
        str(row.get("name", "")),
        str(row.get("summary", "")),
        str(row.get("claim", "")),
    ]
    for claim in row.get("claims", [])[:5] if isinstance(row.get("claims"), list) else []:
        if isinstance(claim, dict):
            parts.append(str(claim.get("claim", "")))
    return " ".join(part for part in parts if part)


def claim_sentences(text: str, words: tuple[str, ...], fallback: str, limit: int = 3) -> list[str]:
    chunks = [part.strip() for part in text.replace("。", "；").replace("，", "；").split("；") if part.strip()]
    hits = [chunk for chunk in chunks if any(word in chunk for word in words)]
    output = hits[:limit] or ([fallback] if fallback else [])
    deduped: list[str] = []
    for item in output:
        item = item[:80]
        if item and item not in deduped:
            deduped.append(item)
    return deduped


def confidence_from(row: dict[str, Any], default: float = 0.72) -> float:
    return round(float(row.get("quality") or row.get("confidence") or default), 2)


def row_id(prefix: str, *parts: str) -> str:
    digest = hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()[:10]
    return f"{prefix}_{digest}"


def read_entities(world: str) -> dict[str, list[dict[str, Any]]]:
    wdir = world_dir(world)
    return {
        "npcs": read_json(wdir / "npcs.json", {}).get("npcs", []),
        "items": read_json(wdir / "items.json", {}).get("items", []),
        "techniques": read_json(wdir / "techniques.json", {}).get("techniques", []),
        "realms": read_json(wdir / "power_system.json", {}).get("realms", []),
        "rules": read_json(wdir / "power_system.json", {}).get("cultivation_rules", []),
        "events": read_json(wdir / "timeline.json", {}).get("events", []),
        "hooks": read_json(wdir / "adventure_hooks.json", {}).get("hooks", []),
        "factions": read_json(wdir / "factions.json", {}).get("factions", []),
        "locations": read_json(wdir / "locations.json", {}).get("locations", []),
    }


def build_npc_motives(world: str, entities: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    rows = []
    for npc in entities["npcs"]:
        name = str(npc.get("name") or "").strip()
        if not name:
            continue
        text = entity_text(npc)
        leverage = claim_sentences(text, LEVERAGE_WORDS, "可提供情报、资源、指导、交易或关系入口。", 4)
        boundaries = claim_sentences(text, BOUNDARY_WORDS, "不会无条件满足玩家要求；需要筹码、关系、时机或代价。", 4)
        hooks = [
            f"提出与「{leverage[0]}」相关的具体交换条件。" if leverage else "提出具体交换条件。",
            "询问对方需要什么筹码或承诺。",
            "确认对方不能接受的底线。",
        ]
        rows.append(
            {
                "npc": name,
                "public_goal": claim_sentences(text, MOTIVE_WORDS, f"围绕自身身份和当前势力关系行动。", 1)[0],
                "private_goal": claim_sentences(text, ("秘密", "身份", "信任", "长期", "过去", "机缘"), "需要通过互动和信任逐步揭示。", 1)[0],
                "fears": claim_sentences(text, FEAR_WORDS, "关系恶化、资源损失或被更强势力注意。", 3),
                "leverage": leverage,
                "boundaries": boundaries,
                "player_hooks": hooks,
                "evidence": text[:220],
                "confidence": confidence_from(npc),
            }
        )
    return {
        "world": world,
        "policy": "NPC motives are host-facing guidance. They shape social rulings, but cannot override canon facts or relationship state.",
        "npcs": rows,
    }


def build_ability_boundaries(world: str, entities: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    rows = []
    ability_rows = [
        *[(row, "technique") for row in entities["techniques"]],
        *[(row, "item") for row in entities["items"]],
        *[(row, "power_realm") for row in entities["realms"]],
        *[(row, "cultivation_rule") for row in entities["rules"]],
    ]
    for row, ability_type in ability_rows:
        name = str(row.get("name") or "").strip()
        if not name:
            continue
        text = entity_text(row)
        can_do = claim_sentences(text, CAN_DO_WORDS, "提供与其 canon 描述一致的有限优势。", 4)
        costs = claim_sentences(text, COST_WORDS, "需要资源、时间、状态或环境条件。", 4)
        risks = claim_sentences(text, RISK_WORDS, "失败会带来资源损耗、暴露、反噬或关系后果。", 4)
        requirements = claim_sentences(text, REQ_WORDS, "需要满足当前状态、地点、资源、身份或能力前置。", 4)
        cannot_do = claim_sentences(
            text,
            CANNOT_WORDS,
            "不能绕过境界/等级/资源/地点/关系等硬前置；不能把尝试声明成自动成功。",
            4,
        )
        scaling = claim_sentences(text, SCALING_WORDS, "随玩家等级、熟练度、资源投入和 canon 条件逐步提升。", 1)[0]
        rows.append(
            {
                "ability_id": row_id("ability", ability_type, name),
                "name": name,
                "type": ability_type,
                "can_do": can_do,
                "cannot_do": cannot_do,
                "costs": costs,
                "risks": risks,
                "requirements": requirements,
                "scaling": scaling,
                "evidence": text[:260],
                "confidence": confidence_from(row),
            }
        )
    return {
        "world": world,
        "policy": "Ability boundaries prevent special powers from becoming universal keys. Player use must check can_do, cannot_do, costs, risks, requirements, and scaling.",
        "abilities": rows,
    }


def build_foreshadowing(world: str, entities: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    candidates = entities["npcs"] + entities["items"] + entities["techniques"] + entities["events"] + entities["hooks"] + entities["factions"]
    rows = []
    for row in candidates:
        text = entity_text(row)
        if not any(word in text for word in FORESHADOW_WORDS):
            continue
        name = str(row.get("name") or row.get("title") or "未命名伏笔")
        rows.append(
            {
                "foreshadow_id": row_id("foreshadow", name, text[:80]),
                "surface_clue": claim_sentences(text, FORESHADOW_WORDS, text[:80], 1)[0],
                "hidden_truth": "主持人隐藏信息：只在玩家满足揭示条件后逐步公开，不要开局剧透。",
                "reveal_conditions": claim_sentences(text, ("信任", "接触", "线索", "调查", "等级", "境界", "地点", "任务"), "玩家持续调查、建立关系或推进相关任务。", 4),
                "payoff": claim_sentences(text, ("解锁", "获得", "指导", "资源", "主线", "任务", "能力"), "解锁新任务、关系、能力边界或地点入口。", 3),
                "spoiler_level": "host_only",
                "related_entities": [name],
                "evidence": text[:260],
                "confidence": confidence_from(row, 0.66),
            }
        )
    return {
        "world": world,
        "policy": "Foreshadowing separates player-visible clues from host-only truths. Do not reveal hidden_truth unless reveal_conditions are met.",
        "foreshadows": rows[:80],
    }


def event_kind(text: str) -> str:
    if any(word in text for word in ("拍卖", "交易", "市场", "黑市")):
        return "auction"
    if any(word in text for word in ("势力", "宗门", "家族", "公司", "结盟")):
        return "faction"
    if any(word in text for word in ("秘境", "遗迹", "探索", "入口", "地点")):
        return "exploration"
    if any(word in text for word in ("追杀", "战争", "封锁", "灾变", "污染")):
        return "threat"
    if any(word in text for word in ("修炼", "训练", "突破", "试炼")):
        return "training"
    return "opportunity"


EVENT_CHAIN_DEFAULTS = {
    "auction": {
        "intervened": ["获得交易资格、折扣、联系人或资源筹措入口。"],
        "ignored": ["关键资源被竞争者拿走，价格上涨或交易资格降低。"],
    },
    "faction": {
        "intervened": ["建立势力接触入口，获得任务、庇护条件或人情债。"],
        "ignored": ["目标势力关注度下降，竞争者获得先机或敌意上升。"],
    },
    "exploration": {
        "intervened": ["获得地点入口、路线情报、资源线索或撤退方案。"],
        "ignored": ["入口线索过期，其他探索者提前进入并改变现场。"],
    },
    "threat": {
        "intervened": ["降低地区风险，获得声望、人情或威胁来源情报。"],
        "ignored": ["威胁扩大并影响当前地区，相关 NPC 或势力承受损失。"],
    },
    "training": {
        "intervened": ["获得历练、能力指导、资源准备路线或下一阶段目标。"],
        "ignored": ["试炼窗口关闭，玩家错过低风险成长机会。"],
    },
    "opportunity": {
        "intervened": ["获得情报、关系、资源或地点入口。"],
        "ignored": ["机会窗口关闭，竞争者或敌对势力获得先机。"],
    },
}


def build_event_chains(world: str, entities: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    source = [row for row in [*entities["hooks"], *entities["events"]] if row.get("name")]
    chains = []
    for idx, row in enumerate(source[:24]):
        name = str(row.get("name") or f"事件链{idx + 1}")
        text = entity_text(row)
        kind = event_kind(text)
        defaults = EVENT_CHAIN_DEFAULTS[kind]
        chains.append(
            {
                "chain_id": row_id("chain", name, text[:80]),
                "name": name,
                "type": kind,
                "source": "adventure_hooks.json" if row in entities["hooks"] else "timeline.json",
                "nodes": [
                    {
                        "node_id": "signal",
                        "event": name,
                        "deadline_turns": 4 if kind in {"auction", "threat"} else 6,
                        "if_player_intervenes": claim_sentences(text, ("获得", "建立", "发现", "解锁", "降低", "进入"), defaults["intervened"][0], 3),
                        "if_ignored": claim_sentences(text, ("错过", "竞争", "追杀", "封锁", "上涨", "损失"), defaults["ignored"][0], 3),
                    },
                    {
                        "node_id": "followup",
                        "event": f"{name}后续",
                        "trigger": "previous_intervened_or_ignored",
                        "effects": [
                            "根据玩家是否介入，更新市场、关系、地点风险、任务或世界标记。",
                            "后续节点必须继续遵守 canon 和当前 player_state。",
                        ],
                    },
                ],
                "evidence": text[:260],
                "confidence": confidence_from(row, 0.68),
            }
        )
    return {
        "world": world,
        "policy": "Event chains describe cause-and-effect pressure. They guide world_events generation and host narration, but do not force outcomes without player-state checks.",
        "chains": chains,
    }


def build_narrative_intelligence(world: str) -> dict[str, Any]:
    wdir = world_dir(world)
    entities = read_entities(world)
    outputs = {
        "npc_motives.json": build_npc_motives(world, entities),
        "ability_boundaries.json": build_ability_boundaries(world, entities),
        "foreshadowing.json": build_foreshadowing(world, entities),
        "event_chains.json": build_event_chains(world, entities),
    }
    for filename, data in outputs.items():
        write_json(wdir / filename, data)
    manifest = load_manifest(wdir, world)
    manifest["npc_motives"] = "npc_motives.json"
    manifest["ability_boundaries"] = "ability_boundaries.json"
    manifest["foreshadowing"] = "foreshadowing.json"
    manifest["event_chains"] = "event_chains.json"
    save_manifest(wdir, manifest)
    print(
        "Built narrative intelligence "
        f"npcs={len(outputs['npc_motives.json']['npcs'])} "
        f"abilities={len(outputs['ability_boundaries.json']['abilities'])} "
        f"foreshadows={len(outputs['foreshadowing.json']['foreshadows'])} "
        f"chains={len(outputs['event_chains.json']['chains'])}"
    )
    return outputs


def main() -> None:
    parser = argparse.ArgumentParser(description="Build NPC motives, ability boundaries, foreshadowing, and event chains.")
    parser.add_argument("--world", required=True)
    parser.add_argument("--rebuild", action="store_true")
    args = parser.parse_args()
    build_narrative_intelligence(args.world)


if __name__ == "__main__":
    main()
