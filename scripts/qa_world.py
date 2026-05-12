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
    "encounter_state.json",
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
    "encounter_state.json",
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
    if "relationship_rules" in failed:
        risks.append("关系规则不足，NPC 好感、敌意、人情债和势力后果会偏弱。")
        recommendations.append("补充 NPC/势力关系规则，让社交行动能改变世界状态。")

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
    encounter_state = read_json(wdir / "encounter_state.json", {})
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
        ("encounter_state", "active" in encounter_state and "history" in encounter_state, "present" if "active" in encounter_state and "history" in encounter_state else "missing"),
        ("world_events", len(world_events.get("events", [])) >= 1, str(len(world_events.get("events", [])))),
        ("opening", bool(read_json(wdir / "opening.json", {})), "present" if read_json(wdir / "opening.json", {}) else "missing"),
    ]

    print(f"World QA: {world}")
    print(f"profile={manifest.get('profile')} genre={manifest.get('genre', 'unknown')} preset={is_preset}")
    for name, ok, detail in checks:
        print(f"[{status(ok)}] {name}: {detail}")
    report = build_readable_report(world, manifest, checks, entity_counts, index_rows, len(playable_entries))
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
