#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
from typing import Any

from common import load_manifest, read_json, read_jsonl, save_manifest, world_dir, write_json


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
NPC_FACT_TYPES = {
    "npc",
    "relationship",
    "story_arc",
    "recurring_mission",
    "event",
    "item",
    "technique",
    "cultivation_rule",
    "location",
    "faction",
}


def clean_line(value: Any, limit: int = 120) -> str:
    text = " ".join(str(value or "").replace("\n", " ").split()).strip(" ；，。")
    if not text:
        return ""
    if any(noise in text for noise in ("['", "']", "{", "}", "目光", "脸色", "手掌", "微微", "笑道")):
        return ""
    return text[:limit].rstrip("，。； ")


def unique_lines(values: list[Any], fallback: str = "", limit: int = 4, width: int = 120) -> list[str]:
    rows: list[str] = []
    for value in values:
        text = clean_line(value, width)
        if text and text not in rows:
            rows.append(text)
        if len(rows) >= limit:
            break
    if not rows and fallback:
        rows.append(fallback)
    return rows


def split_clean_claims(text: str) -> list[str]:
    parts = []
    for part in str(text or "").replace("。", "；").replace("，", "；").split("；"):
        cleaned = clean_line(part, 110)
        if cleaned:
            parts.append(cleaned)
    return parts


def npc_aliases(name: str) -> set[str]:
    aliases = {name}
    if name.startswith("萧") and len(name) <= 3:
        aliases.add(name[1:])
    if name == "薰儿":
        aliases.add("萧薰儿")
    if name == "萧薰儿":
        aliases.add("薰儿")
    return {alias for alias in aliases if alias}


def canonical_npc_name(name: str, all_names: set[str]) -> str:
    if name == "薰儿" and "萧薰儿" in all_names:
        return "萧薰儿"
    if name.startswith("萧") and len(name) <= 3:
        short = name[1:]
        if short in all_names and name not in all_names:
            return short
    return name


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
    llm_facts: dict[str, list[dict[str, Any]]] = {
        "npcs": [],
        "items": [],
        "techniques": [],
        "realms": [],
        "rules": [],
    }
    type_map = {
        "npc": "npcs",
        "item": "items",
        "technique": "techniques",
        "power_realm": "realms",
        "cultivation_rule": "rules",
    }
    for fact in read_jsonl(wdir / "facts.jsonl"):
        if fact.get("source") != "llm_assisted":
            continue
        bucket = type_map.get(str(fact.get("type") or ""))
        name = str(fact.get("name") or "").strip()
        claim = str(fact.get("claim") or "").strip()
        if bucket and name and claim:
            llm_facts[bucket].append(
                {
                    "name": name,
                    "summary": claim,
                    "claim": claim,
                    "quality": float(fact.get("confidence") or fact.get("quality") or 0.9),
                    "source": "llm_assisted",
                    "evidence_chunk_ids": fact.get("evidence_chunk_ids", []),
                }
            )
    return {
        "npcs": prefer_llm_entities(llm_facts["npcs"], read_json(wdir / "npcs.json", {}).get("npcs", [])),
        "items": prefer_llm_entities(llm_facts["items"], read_json(wdir / "items.json", {}).get("items", [])),
        "techniques": prefer_llm_entities(llm_facts["techniques"], read_json(wdir / "techniques.json", {}).get("techniques", [])),
        "realms": prefer_llm_entities(llm_facts["realms"], read_json(wdir / "power_system.json", {}).get("realms", [])),
        "rules": prefer_llm_entities(llm_facts["rules"], read_json(wdir / "power_system.json", {}).get("cultivation_rules", [])),
        "events": read_json(wdir / "timeline.json", {}).get("events", []),
        "hooks": read_json(wdir / "adventure_hooks.json", {}).get("hooks", []),
        "factions": read_json(wdir / "factions.json", {}).get("factions", []),
        "locations": read_json(wdir / "locations.json", {}).get("locations", []),
    }


def prefer_llm_entities(llm_rows: list[dict[str, Any]], fallback_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in llm_rows:
        name = str(row.get("name") or "")
        if not name or name in seen:
            continue
        seen.add(name)
        rows.append(row)
    for row in fallback_rows:
        name = str(row.get("name") or "")
        if not name or name in seen:
            continue
        rows.append(row)
    return rows


def read_llm_npc_context(world: str, npc_names: list[str]) -> dict[str, list[dict[str, Any]]]:
    wdir = world_dir(world)
    aliases = {name: npc_aliases(name) for name in npc_names}
    grouped: dict[str, list[dict[str, Any]]] = {name: [] for name in npc_names}
    for fact in read_jsonl(wdir / "facts.jsonl"):
        if fact.get("source") != "llm_assisted" or fact.get("type") not in NPC_FACT_TYPES:
            continue
        fact_name = str(fact.get("name") or "")
        claim = str(fact.get("claim") or "")
        haystack = f"{fact_name} {claim}"
        for npc, names in aliases.items():
            if any(alias and alias in haystack for alias in names):
                grouped[npc].append(fact)
    return grouped


def scored_claims(
    facts: list[dict[str, Any]],
    keywords: tuple[str, ...],
    fallback: str,
    limit: int = 3,
    preferred_types: set[str] | None = None,
    banned_types: set[str] | None = None,
) -> list[str]:
    candidates: list[tuple[float, str]] = []
    for fact in facts:
        claim = str(fact.get("claim") or "")
        fact_type = str(fact.get("type") or "")
        if banned_types and fact_type in banned_types:
            continue
        base = float(fact.get("confidence") or fact.get("quality") or 0.8)
        if preferred_types and fact_type in preferred_types:
            base += 0.5
        for line in split_clean_claims(claim):
            if any(word in line for word in keywords):
                bonus = 0.2 if fact_type in {"relationship", "story_arc", "recurring_mission", "npc"} else 0.0
                candidates.append((base + bonus, line))
    candidates.sort(key=lambda item: (item[0], len(item[1]) <= 90), reverse=True)
    return unique_lines([line for _, line in candidates], fallback, limit)


def npc_leverage(facts: list[dict[str, Any]], fallback: list[str]) -> list[str]:
    leverage: list[str] = []
    for fact in facts:
        ftype = str(fact.get("type") or "")
        name = str(fact.get("name") or "")
        claim = str(fact.get("claim") or "")
        if ftype in {"item", "technique", "cultivation_rule", "location", "faction"}:
            leverage.append(f"{name}：{claim}")
        elif ftype in {"relationship", "story_arc", "recurring_mission"} and any(word in claim for word in LEVERAGE_WORDS):
            leverage.append(claim)
    return unique_lines(leverage, limit=5, width=120) or fallback[:4]


def npc_relationship_edges(facts: list[dict[str, Any]]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for fact in facts:
        if fact.get("type") != "relationship":
            continue
        name = clean_line(fact.get("name"), 40)
        claim = clean_line(fact.get("claim"), 140)
        if not name or not claim or name in seen:
            continue
        rows.append({"name": name, "rule": claim})
        seen.add(name)
        if len(rows) >= 6:
            break
    return rows


def npc_player_hooks(name: str, facts: list[dict[str, Any]], leverage: list[str], boundaries: list[str]) -> list[str]:
    hooks: list[str] = []
    for fact in facts:
        ftype = str(fact.get("type") or "")
        fname = clean_line(fact.get("name"), 48)
        if ftype in {"story_arc", "recurring_mission"} and fname:
            hooks.append(f"围绕「{fname}」提出阶段性合作，而不是要求 {name} 直接解决问题。")
        elif ftype == "relationship" and fname:
            hooks.append(f"利用「{fname}」的关系规则推进互动，但接受关系代价。")
    if leverage:
        hooks.append(f"拿「{leverage[0].split('：')[0]}」相关筹码交换情报、指导或渠道。")
    if boundaries:
        hooks.append(f"先确认底线：{boundaries[0]}")
    hooks.append("询问对方当前最需要的筹码、承诺或保密条件。")
    return unique_lines(hooks, limit=5, width=130)


def build_npc_motives(world: str, entities: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    rows = []
    raw_names = {str(npc.get("name") or "").strip() for npc in entities["npcs"] if str(npc.get("name") or "").strip()}
    npc_by_name: dict[str, dict[str, Any]] = {}
    npc_alias_map: dict[str, set[str]] = {}
    for npc in entities["npcs"]:
        name = str(npc.get("name") or "").strip()
        if not name:
            continue
        canonical = canonical_npc_name(name, raw_names)
        npc_alias_map.setdefault(canonical, set()).add(name)
        old = npc_by_name.get(canonical)
        if old is None or confidence_from(npc) > confidence_from(old):
            copied = dict(npc)
            copied["name"] = canonical
            npc_by_name[canonical] = copied
    contexts = read_llm_npc_context(world, list(npc_by_name))
    for name, npc in npc_by_name.items():
        text = entity_text(npc)
        facts = contexts.get(name, [])
        combined_text = " ".join([text, *[str(fact.get("claim") or "") for fact in facts[:12]]])
        leverage = npc_leverage(facts, claim_sentences(combined_text, LEVERAGE_WORDS, "可提供情报、资源、指导、交易或关系入口。", 4))
        boundaries = scored_claims(
            facts,
            BOUNDARY_WORDS + ("不应", "不等于", "除非", "前置"),
            "不会无条件满足玩家要求；需要筹码、关系、时机或代价。",
            4,
        )
        rows.append(
            {
                "npc": name,
                "aliases": sorted(npc_alias_map.get(name, set()) - {name}),
                "public_goal": scored_claims(
                    facts,
                    MOTIVE_WORDS + ("可作为", "支持", "教导", "交易", "自称", "拜入", "到访"),
                    claim_sentences(text, MOTIVE_WORDS + ("是", "可作为", "自称"), "围绕自身身份和当前势力关系行动。", 1)[0],
                    1,
                    preferred_types={"npc", "relationship"},
                )[0],
                "private_goal": scored_claims(
                    facts,
                    ("秘密", "隐藏", "伏笔", "真相", "戒指", "流失", "背景", "延后揭示"),
                    "需要通过互动和信任逐步揭示。",
                    1,
                    preferred_types={"npc", "relationship"},
                    banned_types={"story_arc", "recurring_mission"},
                )[0],
                "fears": scored_claims(facts, FEAR_WORDS + ("敌意", "冲突", "报复", "无代价"), "关系恶化、资源损失或被更强势力注意。", 3),
                "leverage": leverage,
                "boundaries": boundaries,
                "relationship_edges": npc_relationship_edges(facts),
                "player_hooks": npc_player_hooks(name, facts, leverage, boundaries),
                "evidence": clean_line(text, 220),
                "fact_count": len(facts),
                "source": "llm_aggregated" if facts else str(npc.get("source") or "merged"),
                "confidence": round(max([confidence_from(npc), *[float(fact.get("confidence") or 0.0) for fact in facts]]), 2),
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
        acquisition_conditions = claim_sentences(
            text,
            ("获得", "传承", "卷轴", "老师", "师父", "许可", "资格", "购买", "交换", "拜入", "血脉", "身份"),
            "必须先获得来源、许可、传承、物品或资格；不能因为原著出现就直接可用。",
            4,
        )
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
                "acquisition_conditions": acquisition_conditions,
                "scaling": scaling,
                "ooc_policy": "出现于原著不等于玩家可用；必须检查获取路径、身份/境界、资源和失败代价。",
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


ARC_EVENT_KIND = {
    "resource_pursuit": "auction",
    "training_growth": "training",
    "faction_conflict": "faction",
    "exploration_secret": "exploration",
    "rescue_or_protection": "threat",
    "revenge_or_vow": "faction",
    "open_world_loop": "opportunity",
}


def arc_event_text(arc: dict[str, Any]) -> str:
    parts = [
        str(arc.get("summary") or ""),
        "；".join(str(item) for item in arc.get("why_it_matters", [])[:2]),
        "；".join(str(item) for item in arc.get("entry_conditions", [])[:2]),
        "；".join(str(item) for item in arc.get("progression_loops", [])[:2]),
        "；".join(str(item) for item in arc.get("risks", [])[:2]),
        "；".join(str(item) for item in arc.get("rewards", [])[:2]),
    ]
    return " ".join(part for part in parts if part).strip()


def clean_chain_lines(lines: list[str], fallback: str, limit: int = 2) -> list[str]:
    cleaned: list[str] = []
    for line in lines:
        text = str(line or "").replace("\n", " ").strip()
        if not text or len(text) > 120:
            continue
        if any(noise in text for noise in ("['", "']", "目光", "脸色", "手掌", "微微", "笑道")):
            continue
        if text not in cleaned:
            cleaned.append(text)
        if len(cleaned) >= limit:
            break
    return cleaned or [fallback]


def chain_from_story_arc(arc: dict[str, Any], index: int) -> dict[str, Any]:
    name = str(arc.get("name") or f"主线事件{index + 1}")
    text = arc_event_text(arc)
    kind = ARC_EVENT_KIND.get(str(arc.get("type") or ""), event_kind(text))
    defaults = EVENT_CHAIN_DEFAULTS[kind]
    intervened = clean_chain_lines(
        [
            *[str(item) for item in arc.get("rewards", [])],
            *[str(item) for item in arc.get("progression_loops", [])],
        ],
        defaults["intervened"][0],
    )
    ignored = clean_chain_lines(
        [str(item) for item in arc.get("risks", [])],
        defaults["ignored"][0],
    )
    return {
        "chain_id": row_id("chain", name, text[:80]),
        "name": name,
        "type": kind,
        "source": "story_arcs.json",
        "nodes": [
            {
                "node_id": "signal",
                "event": name,
                "deadline_turns": 4 if kind in {"auction", "threat"} else 6,
                "if_player_intervenes": intervened,
                "if_ignored": ignored,
            },
            {
                "node_id": "followup",
                "event": f"{name}后续",
                "trigger": "previous_intervened_or_ignored",
                "effects": [
                    "根据玩家是否介入，更新对应主线阶段、关系、资源、地点风险或世界标记。",
                    "后续节点必须继续遵守 canon、story_arcs 和当前 player_state。",
                ],
            },
        ],
        "evidence": text[:260],
        "confidence": confidence_from(arc, 0.78),
    }


def build_event_chains(world: str, entities: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    wdir = world_dir(world)
    arcs = [
        row
        for row in read_json(wdir / "story_arcs.json", {}).get("arcs", [])
        if row.get("name") and row.get("canon_strength") in {"high", "medium"}
    ]
    source = [row for row in [*entities["hooks"], *entities["events"]] if row.get("name")]
    chains = []
    seen: set[str] = set()
    for idx, arc in enumerate(arcs[:18]):
        chain = chain_from_story_arc(arc, idx)
        seen.add(str(chain["name"]))
        chains.append(chain)
    if len(arcs) >= 10:
        source = []
    for idx, row in enumerate(source[:24]):
        name = str(row.get("name") or f"事件链{idx + 1}")
        if name in seen:
            continue
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
