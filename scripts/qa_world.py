#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path
from typing import Any

from common import read_json, read_jsonl, world_dir, write_json


FULL_REQUIRED_FILES = [
    "manifest.json",
    "chunks.jsonl",
    "facts.jsonl",
    "world_bible.json",
    "power_system.json",
    "factions.json",
    "locations.json",
    "npcs.json",
    "game_rules.json",
    "rpg_profile.json",
    "item_market.json",
    "quest_templates.json",
    "location_runtime.json",
    "relationship_rules.json",
    "scene_graph.json",
    "skill_tree.json",
    "equipment_sets.json",
    "economy_state.json",
    "acquisition_routes.json",
    "ooc_report.json",
    "director_plan.json",
    "quest_lifecycle.json",
    "npc_agency.json",
    "reward_policy.json",
    "evidence_cards.json",
    "canon_eval.json",
    "encounter_state.json",
    "npc_motives.json",
    "ability_boundaries.json",
    "foreshadowing.json",
    "event_chains.json",
    "story_arcs.json",
    "distillation_score.json",
    "gameplay_profile.json",
    "world_events.json",
    "opening.json",
    "playable_canon.json",
    "retrieval.sqlite",
]

PRESET_REQUIRED_FILES = [
    "manifest.json",
    "world_bible.json",
    "power_system.json",
    "factions.json",
    "locations.json",
    "npcs.json",
    "game_rules.json",
    "rpg_profile.json",
    "item_market.json",
    "quest_templates.json",
    "location_runtime.json",
    "relationship_rules.json",
    "scene_graph.json",
    "skill_tree.json",
    "equipment_sets.json",
    "economy_state.json",
    "acquisition_routes.json",
    "ooc_report.json",
    "director_plan.json",
    "quest_lifecycle.json",
    "npc_agency.json",
    "reward_policy.json",
    "evidence_cards.json",
    "canon_eval.json",
    "encounter_state.json",
    "npc_motives.json",
    "ability_boundaries.json",
    "foreshadowing.json",
    "event_chains.json",
    "story_arcs.json",
    "distillation_score.json",
    "gameplay_profile.json",
    "world_events.json",
    "opening.json",
    "playable_canon.json",
    "retrieval.sqlite",
]


def count_index_rows(path: Path) -> int:
    if not path.exists():
        return 0
    conn = sqlite3.connect(path)
    try:
        return int(conn.execute("SELECT count(*) FROM canon").fetchone()[0])
    finally:
        conn.close()


def long_summary_count(entries: list[dict[str, Any]], limit: int = 260) -> int:
    return sum(1 for row in entries if len(str(row.get("summary") or row.get("claim") or "")) > limit)


def status(ok: bool) -> str:
    return "OK" if ok else "WARN"


def score_checks(checks: list[tuple[str, bool, str]]) -> int:
    if not checks:
        return 0
    base = sum(1 for _, ok, _ in checks if ok) / len(checks)
    return round(base * 100)


def build_readable_report(
    world: str,
    manifest: dict[str, Any],
    checks: list[tuple[str, bool, str]],
    entity_counts: dict[str, Any],
    index_rows: int,
    playable_count: int,
    gameplay_profile: dict[str, Any],
) -> dict[str, Any]:
    failed = [name for name, ok, _ in checks if not ok]
    strengths: list[str] = []
    risks: list[str] = []
    recommendations: list[str] = []

    if int(entity_counts.get("location", 0)) >= 8:
        strengths.append("地点数量较充足，适合做探索、移动和区域风险。")
    elif "locations" in failed:
        risks.append("地点不足，玩家容易感觉世界像单点场景，而不是可探索地图。")
        recommendations.append("增加 LLM-assisted 蒸馏 chunk 数，或手动补充 locations/canon_patches。")

    if int(entity_counts.get("npc", 0)) >= 8:
        strengths.append("NPC 覆盖较好，可以支撑关系、任务和社交玩法。")
    elif "npcs" in failed:
        risks.append("关键 NPC 不足，剧情驱动力和人际关系会偏弱。")
        recommendations.append("优先补 NPC 的身份、动机、关系和可提供的任务/资源。")

    if int(entity_counts.get("power_realm", 0)) >= 4 or int(entity_counts.get("cultivation_rule", 0)) >= 8:
        strengths.append("成长/能力体系已有基础，可转成突破条件和能力边界。")
    else:
        risks.append("成长体系不完整，玩家升级、突破或学习能力时容易缺规则依据。")
        recommendations.append("补充 power_system：阶段、突破条件、能力边界、失败代价、常见资源。")

    if playable_count >= 40:
        strengths.append("可玩 canon 数量较足，运行时检索能提供较多裁定依据。")
    else:
        risks.append("可玩规则偏少，运行时可能退回模板化主持。")
        recommendations.append("重跑 distill_playable 或启用 LLM-assisted distillation。")

    if index_rows >= playable_count and index_rows > 0:
        strengths.append("检索索引可用，运行时无需加载整本小说。")
    else:
        risks.append("检索索引不完整，运行时可能找不到相关 canon。")
        recommendations.append("重跑 python novel.py pipeline index <world> 或 python scripts/index.py --world <world>。")

    if "rpg_profile" not in failed and "worldview_labels" not in failed:
        strengths.append("RPG 术语已映射到世界观，资源/装备/技能名称不会固定成通用法力模板。")
    else:
        risks.append("RPG 术语映射不足，生命/能量/装备/技能可能不贴合小说世界。")
        recommendations.append("重跑 python novel.py rebuild-rpg <world>，必要时补充 world_profile.json。")

    if "item_market" in failed:
        risks.append("经济与物品市场不足，购买、奖励和资源替代路径会不稳定。")
        recommendations.append("补充 item_market：价格区间、购买条件、替代获取路径、稀有度。")
    if "quest_templates" in failed:
        risks.append("任务模板不足，玩家可能缺少明确的短中期目标。")
        recommendations.append("补充 adventure_hooks 或重跑 quest_runtime。")
    if "world_events" in failed:
        risks.append("长期世界事件不足，世界会显得静止，缺少时间窗口和忽略后果。")
        recommendations.append("重跑 world_events，或补充 adventure_hooks 生成会过期的事件压力。")
    elif any((event.get("effects") or event.get("triggers")) for event in read_json(world_dir(world) / "world_events.json", {}).get("events", [])):
        strengths.append("长期事件具备联动 effects/triggers，可影响市场、关系、地点或生成后续事件。")
    if "relationship_rules" in failed:
        risks.append("关系规则不足，NPC 好感、敌意、人情债和势力后果会偏弱。")
        recommendations.append("补充 NPC/势力关系规则，让社交行动能改变世界状态。")
    if "npc_motives" not in failed:
        strengths.append("NPC 动机层可用，社交、交易和求助裁定不再只看好感分。")
    else:
        risks.append("NPC 动机层缺失，人物容易像任务板，缺少欲望、底线和筹码。")
        recommendations.append("重跑 narrative_intelligence；LLM-assisted 时重点抽 public/private goal、fear、leverage、boundary。")
    if "ability_boundaries" not in failed:
        strengths.append("特殊能力边界层可用，能力使用有 can/cannot/cost/risk/requirement 约束。")
    else:
        risks.append("特殊能力边界不足，玩家能力容易变成万能钥匙。")
        recommendations.append("补充 ability_boundaries：能做什么、不能做什么、消耗、风险、前置、成长。")
    if "event_chains" not in failed:
        strengths.append("事件链层可用，冒险钩子可以转成因果推进和忽略后果。")
    else:
        risks.append("事件链不足，世界事件容易是孤立事件，缺少后续因果。")
        recommendations.append("补充 event_chains：节点、触发条件、介入收益、忽略后果、后续 effects。")
    if "story_arcs" not in failed:
        strengths.append("长期任务线层可用，原著反复出现的重要目标会进入任务、事件和检索。")
    else:
        risks.append("长期任务线不足，玩家容易只看到零散委托，缺少原著主线/支线代入感。")
        recommendations.append("重跑 story_arcs 或启用 LLM-assisted，重点抽反复出现的重要任务、资源追求、训练目标和势力冲突。")
    for check_name, strength, risk, recommendation in [
        ("director_plan", "导演层可用，能用 canon-derived beat 控制节奏但不强制玩家路线。", "导演层缺失，长期游玩可能缺章节节奏和机会窗口。", "重跑 director.py，确保 story_arcs/world_events 可生成 pacing beat。"),
        ("quest_lifecycle", "任务生命周期可用，任务会分成线索、接触、准备、执行、结算和余波。", "任务生命周期缺失，任务容易像 checklist 或反复无进展。", "重跑 quest_lifecycle.py，或补 quest_templates 的 objectives。"),
        ("npc_agency", "NPC 主动性层可用，重要 NPC 可按动机提出条件、拒绝或给有限线索。", "NPC 主动性缺失，人物容易只被动回应玩家。", "重跑 npc_agency.py，必要时补 npc_motives。"),
        ("reward_policy", "收益通道已结构化，非战斗玩法也能保留情报、关系、入口和资源收益。", "收益策略缺失，探索/社交/情报可能缺少明确回报。", "重跑 reward_policy.py，并检查 action_resolver 是否通过结构化脚本结算奖励。"),
        ("evidence_cards", "证据卡可用，运行时解释可减少长摘要和工程味提示。", "证据卡缺失，运行时证据解释可能仍偏粗糙。", "重跑 evidence_cards.py，必要时补短 canon 摘要。"),
        ("canon_eval", "canon regression cases 已生成，可用于测试反 OOC、任务阶段和能力边界。", "canon eval 缺失，换书后难以回归检查是否 OOC。", "重跑 canon_eval.py，并用多本小说建立评测集。"),
    ]:
        if check_name not in failed:
            strengths.append(strength)
        else:
            risks.append(risk)
            recommendations.append(recommendation)
    distillation_score = read_json(world_dir(world) / "distillation_score.json", {})
    score_value = int(distillation_score.get("overall_score", 0) or 0)
    if score_value >= 85:
        strengths.append(f"蒸馏质量评分 {score_value}/100，叙事智能层完整度较好。")
    else:
        risks.append(f"蒸馏质量评分偏低（{score_value}/100），文件存在但内容质量可能不足。")
        recommendations.append("运行 python novel.py score <world> 查看 distillation_score.md，并按建议补 LLM-assisted 或 canon_patches。")

    enabled_mechanics = [
        name for name, value in gameplay_profile.get("mechanisms", {}).items() if isinstance(value, dict) and value.get("enabled")
    ]
    if enabled_mechanics:
        strengths.append(f"玩法机制已从 canon 证据中启用 {len(enabled_mechanics)} 项，战斗和事件不再只依赖题材标签。")
    else:
        risks.append("玩法机制缺少 canon 证据，系统会退回低置信通用裁定，题材特色会偏弱。")
        recommendations.append("增加 LLM-assisted 蒸馏或补 canon_patches，重点补能力边界、资源、地点准入、势力后果。")
    if gameplay_profile.get("combat", {}).get("fallback_used"):
        risks.append("战斗 profile 当前仍使用低置信兜底，可能无法充分体现原著特殊规则。")
        recommendations.append("补充 power_system/game_rules/items/techniques 中的明确战斗代价和能力边界。")

    if not recommendations:
        recommendations.append("世界已达到基础可玩状态；下一步可增加长期世界事件和更多高质量 NPC 动机。")

    return {
        "world": world,
        "score": score_checks(checks),
        "genre": manifest.get("genre", "unknown"),
        "profile": manifest.get("profile", "unknown"),
        "strengths": strengths,
        "risks": risks,
        "recommendations": recommendations,
        "failed_checks": failed,
        "entity_counts": entity_counts,
        "index_rows": index_rows,
        "playable_count": playable_count,
    }


def write_markdown_report(wdir: Path, report: dict[str, Any]) -> None:
    lines = [
        f"# Quality Report: {report['world']}",
        "",
        f"- Score: {report['score']}/100",
        f"- Genre: {report.get('genre')}",
        f"- Profile: {report.get('profile')}",
        f"- Retrieval rows: {report.get('index_rows')}",
        f"- Playable canon: {report.get('playable_count')}",
        "",
        "## Strengths",
        *(f"- {item}" for item in report.get("strengths", []) or ["暂无明显强项。"]),
        "",
        "## Risks",
        *(f"- {item}" for item in report.get("risks", []) or ["暂无明显风险。"]),
        "",
        "## Recommendations",
        *(f"- {item}" for item in report.get("recommendations", [])),
        "",
        "## Entity Counts",
        *(f"- {key}: {value}" for key, value in sorted(report.get("entity_counts", {}).items())),
        "",
    ]
    (wdir / "quality_report.md").write_text("\n".join(lines), encoding="utf-8")


def qa(world: str) -> None:
    wdir = world_dir(world)
    manifest = read_json(wdir / "manifest.json", {})
    quality = read_json(wdir / "quality_report.json", {})
    playable = read_json(wdir / "playable_canon.json", {})
    player_state = read_json(wdir / "player_state.json", {})
    rpg_profile = read_json(wdir / "rpg_profile.json", {})
    market = read_json(wdir / "item_market.json", {})
    quests = read_json(wdir / "quest_templates.json", {})
    location_runtime = read_json(wdir / "location_runtime.json", {})
    relationship_rules = read_json(wdir / "relationship_rules.json", {})
    scene_graph = read_json(wdir / "scene_graph.json", {})
    skill_tree = read_json(wdir / "skill_tree.json", {})
    equipment_sets = read_json(wdir / "equipment_sets.json", {})
    economy_state = read_json(wdir / "economy_state.json", {})
    acquisition_routes = read_json(wdir / "acquisition_routes.json", {})
    ooc_report = read_json(wdir / "ooc_report.json", {})
    director_plan = read_json(wdir / "director_plan.json", {})
    quest_lifecycle = read_json(wdir / "quest_lifecycle.json", {})
    npc_agency = read_json(wdir / "npc_agency.json", {})
    reward_policy = read_json(wdir / "reward_policy.json", {})
    evidence_cards = read_json(wdir / "evidence_cards.json", {})
    canon_eval = read_json(wdir / "canon_eval.json", {})
    encounter_state = read_json(wdir / "encounter_state.json", {})
    npc_motives = read_json(wdir / "npc_motives.json", {})
    ability_boundaries = read_json(wdir / "ability_boundaries.json", {})
    foreshadowing = read_json(wdir / "foreshadowing.json", {})
    event_chains = read_json(wdir / "event_chains.json", {})
    story_arcs = read_json(wdir / "story_arcs.json", {})
    distillation_score = read_json(wdir / "distillation_score.json", {})
    gameplay_profile = read_json(wdir / "gameplay_profile.json", {})
    world_events = read_json(wdir / "world_events.json", {})
    curated = read_jsonl(wdir / "curated_facts.jsonl")
    index_rows = count_index_rows(wdir / "retrieval.sqlite")
    is_preset = bool(manifest.get("preset_world"))
    required_files = PRESET_REQUIRED_FILES if is_preset else FULL_REQUIRED_FILES
    missing = [filename for filename in required_files if not (wdir / filename).exists()]
    entity_counts = quality.get("entity_counts", {})
    playable_entries = playable.get("entries", [])

    checks = [
        ("required_files", not missing, f"missing={missing}" if missing else "all present"),
        ("chunks", is_preset or int(manifest.get("chunk_count", 0)) > 0, "redacted preset" if is_preset else str(manifest.get("chunk_count", 0))),
        ("facts", is_preset or int(manifest.get("fact_count", 0)) > 0, "redacted preset" if is_preset else str(manifest.get("fact_count", 0))),
        ("curated_facts", len(curated) >= 30, str(len(curated))),
        ("playable_canon", len(playable_entries) >= 30, str(len(playable_entries))),
        ("retrieval_index", index_rows >= len(curated), str(index_rows)),
        ("long_summaries", long_summary_count(playable_entries) <= max(5, len(playable_entries) // 10), str(long_summary_count(playable_entries))),
        ("locations", int(entity_counts.get("location", 0)) >= 5, str(entity_counts.get("location", 0))),
        ("npcs", int(entity_counts.get("npc", 0)) >= 5, str(entity_counts.get("npc", 0))),
        ("rpg_stats", bool(player_state.get("player", {}).get("stats")), "present" if player_state.get("player", {}).get("stats") else "missing"),
        ("rpg_profile", bool(rpg_profile.get("systems", {}).get("resource_name")), rpg_profile.get("systems", {}).get("resource_name", "missing")),
        ("worldview_labels", bool(player_state.get("player", {}).get("stat_labels", {}).get("mp")), player_state.get("player", {}).get("stat_labels", {}).get("mp", "missing")),
        ("item_market", len(market.get("items", [])) >= 3, str(len(market.get("items", [])))),
        ("quest_templates", len(quests.get("quests", [])) >= 1, str(len(quests.get("quests", [])))),
        ("location_runtime", len(location_runtime.get("locations", [])) >= 3, str(len(location_runtime.get("locations", [])))),
        ("relationship_rules", len(relationship_rules.get("npcs", [])) + len(relationship_rules.get("factions", [])) >= 3, str(len(relationship_rules.get("npcs", [])) + len(relationship_rules.get("factions", [])))),
        ("scene_graph", len(scene_graph.get("locations", [])) >= 1 and len(scene_graph.get("npcs", [])) >= 1, f"locations={len(scene_graph.get('locations', []))} npcs={len(scene_graph.get('npcs', []))}"),
        ("skill_tree", len(skill_tree.get("nodes", [])) >= 1, str(len(skill_tree.get("nodes", [])))),
        (
            "skill_canon_gate",
            all(isinstance(row, dict) and row.get("canon_gate") for row in skill_tree.get("nodes", [])),
            "gated" if all(isinstance(row, dict) and row.get("canon_gate") for row in skill_tree.get("nodes", [])) else "missing gates",
        ),
        ("equipment_sets", len(equipment_sets.get("sets", [])) >= 1, str(len(equipment_sets.get("sets", [])))),
        (
            "equipment_canon_gate",
            all(isinstance(row, dict) and row.get("canon_gate") and "enabled" in row for row in equipment_sets.get("sets", [])),
            "gated" if all(isinstance(row, dict) and row.get("canon_gate") and "enabled" in row for row in equipment_sets.get("sets", [])) else "missing gates",
        ),
        ("economy_state", "items" in economy_state, str(len(economy_state.get("items", [])))),
        ("acquisition_routes", len(acquisition_routes.get("routes", [])) >= len(skill_tree.get("nodes", [])), str(len(acquisition_routes.get("routes", [])))),
        ("ooc_qa", bool(ooc_report.get("passed", False)), f"score={ooc_report.get('score', 'missing')} issues={len(ooc_report.get('issues', []))}"),
        ("director_plan", len(director_plan.get("beats", [])) >= 1, str(len(director_plan.get("beats", [])))),
        ("quest_lifecycle", len(quest_lifecycle.get("quests", [])) >= len(quests.get("quests", [])), str(len(quest_lifecycle.get("quests", [])))),
        ("npc_agency", len(npc_agency.get("npcs", [])) >= 1, str(len(npc_agency.get("npcs", [])))),
        ("reward_policy", len(reward_policy.get("channels", [])) >= 5, str(len(reward_policy.get("channels", [])))),
        ("evidence_cards", len(evidence_cards.get("cards", [])) >= 20, str(len(evidence_cards.get("cards", [])))),
        ("canon_eval", len(canon_eval.get("cases", [])) >= 3, str(len(canon_eval.get("cases", [])))),
        ("encounter_state", "active" in encounter_state and "history" in encounter_state, "present" if "active" in encounter_state and "history" in encounter_state else "missing"),
        ("npc_motives", len(npc_motives.get("npcs", [])) >= min(3, max(1, int(entity_counts.get("npc", 0)))), str(len(npc_motives.get("npcs", [])))),
        ("ability_boundaries", len(ability_boundaries.get("abilities", [])) >= 5, str(len(ability_boundaries.get("abilities", [])))),
        ("foreshadowing", "foreshadows" in foreshadowing, str(len(foreshadowing.get("foreshadows", [])))),
        ("event_chains", len(event_chains.get("chains", [])) >= 1, str(len(event_chains.get("chains", [])))),
        ("story_arcs", len(story_arcs.get("arcs", [])) >= 1, str(len(story_arcs.get("arcs", [])))),
        ("distillation_score", int(distillation_score.get("overall_score", 0) or 0) >= 75, str(distillation_score.get("overall_score", "missing"))),
        (
            "gameplay_profile",
            bool(gameplay_profile.get("source_priority")) and bool(gameplay_profile.get("mechanisms")),
            gameplay_profile.get("canon_confidence", "missing"),
        ),
        ("world_events", len(world_events.get("events", [])) >= 1, str(len(world_events.get("events", [])))),
        ("opening", bool(read_json(wdir / "opening.json", {})), "present" if read_json(wdir / "opening.json", {}) else "missing"),
    ]

    print(f"World QA: {world}")
    print(f"profile={manifest.get('profile')} genre={manifest.get('genre', 'unknown')} preset={is_preset}")
    for name, ok, detail in checks:
        print(f"[{status(ok)}] {name}: {detail}")
    report = build_readable_report(world, manifest, checks, entity_counts, index_rows, len(playable_entries), gameplay_profile)
    write_json(wdir / "quality_report.json", {**quality, "readable_report": report})
    write_markdown_report(wdir, report)
    print(f"Quality score: {report['score']}/100")
    if report["risks"]:
        print("Top risks:")
        for item in report["risks"][:3]:
            print(f"- {item}")
    print("Wrote quality_report.md")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run deterministic quality checks for a distilled world.")
    parser.add_argument("--world", required=True)
    args = parser.parse_args()
    qa(args.world)


if __name__ == "__main__":
    main()
