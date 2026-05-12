#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from common import load_manifest, read_json, save_manifest, world_dir, write_json


REQUIRED_ABILITY_FIELDS = ("can_do", "cannot_do", "costs", "risks", "requirements")
TEMPLATE_RISK_WORDS = ("法力", "灵力", "义体", "魂骨", "弹药", "理智", "污染", "机甲")


def ratio(count: int, total: int) -> int:
    if total <= 0:
        return 0
    return round(min(1.0, count / total) * 100)


def nonempty_list(row: dict[str, Any], key: str) -> bool:
    value = row.get(key)
    return isinstance(value, list) and any(str(item).strip() for item in value)


def score_npc_motives(data: dict[str, Any]) -> tuple[int, list[str]]:
    rows = data.get("npcs", [])
    if not rows:
        return 0, ["NPC 动机层为空。"]
    complete = 0
    for row in rows:
        if row.get("public_goal") and nonempty_list(row, "fears") and nonempty_list(row, "leverage") and nonempty_list(row, "boundaries"):
            complete += 1
    notes = [] if complete == len(rows) else [f"NPC 动机完整度 {complete}/{len(rows)}。"]
    return ratio(complete, len(rows)), notes


def score_ability_boundaries(data: dict[str, Any]) -> tuple[int, list[str]]:
    rows = data.get("abilities", [])
    if not rows:
        return 0, ["能力边界层为空。"]
    complete = 0
    for row in rows:
        if all(nonempty_list(row, key) for key in REQUIRED_ABILITY_FIELDS) and row.get("evidence"):
            complete += 1
    notes = [] if complete == len(rows) else [f"能力边界完整度 {complete}/{len(rows)}。"]
    return ratio(complete, len(rows)), notes


def score_foreshadowing(data: dict[str, Any]) -> tuple[int, list[str]]:
    rows = data.get("foreshadows", [])
    if not isinstance(rows, list):
        return 0, ["伏笔文件结构异常。"]
    if not rows:
        return 75, ["未发现伏笔；这不一定是错误，但长线剧情味道会偏弱。"]
    complete = 0
    for row in rows:
        if row.get("surface_clue") and nonempty_list(row, "reveal_conditions") and nonempty_list(row, "payoff") and row.get("spoiler_level"):
            complete += 1
    return ratio(complete, len(rows)), ([] if complete == len(rows) else [f"伏笔完整度 {complete}/{len(rows)}。"])


def score_event_chains(data: dict[str, Any]) -> tuple[int, list[str]]:
    rows = data.get("chains", [])
    if not rows:
        return 0, ["事件链为空。"]
    complete = 0
    for row in rows:
        nodes = row.get("nodes", [])
        signal = next((node for node in nodes if isinstance(node, dict) and node.get("node_id") == "signal"), {})
        if signal.get("if_player_intervenes") and signal.get("if_ignored") and signal.get("deadline_turns"):
            complete += 1
    return ratio(complete, len(rows)), ([] if complete == len(rows) else [f"事件链完整度 {complete}/{len(rows)}。"])


def score_evidence_quality(*datasets: dict[str, Any]) -> tuple[int, list[str]]:
    total = 0
    with_evidence = 0
    for data in datasets:
        for key in ("npcs", "abilities", "foreshadows", "chains"):
            for row in data.get(key, []):
                total += 1
                if row.get("evidence") or row.get("confidence", 0) >= 0.8:
                    with_evidence += 1
    return ratio(with_evidence, total), ([] if with_evidence == total else [f"证据覆盖 {with_evidence}/{total}。"])


def score_template_pollution(world_text: str, *datasets: dict[str, Any]) -> tuple[int, list[str]]:
    false_hits = []
    combined = " ".join(str(data) for data in datasets)
    for word in TEMPLATE_RISK_WORDS:
        if word in combined and word not in world_text:
            false_hits.append(word)
    if not false_hits:
        return 100, []
    score = max(0, 100 - len(false_hits) * 15)
    return score, [f"疑似题材模板污染词：{', '.join(false_hits)}。"]


def markdown(report: dict[str, Any]) -> str:
    lines = [
        f"# Distillation Score: {report['world']}",
        "",
        f"- Overall: {report['overall_score']}/100",
        "",
        "## Scores",
    ]
    for key, value in report["scores"].items():
        lines.append(f"- {key}: {value}/100")
    lines.extend(["", "## Notes"])
    notes = report.get("notes", []) or ["暂无明显问题。"]
    lines.extend(f"- {note}" for note in notes)
    lines.extend(["", "## Recommendations"])
    lines.extend(f"- {item}" for item in report.get("recommendations", []))
    lines.append("")
    return "\n".join(lines)


def distillation_qa(world: str) -> dict[str, Any]:
    wdir = world_dir(world)
    npc = read_json(wdir / "npc_motives.json", {})
    ability = read_json(wdir / "ability_boundaries.json", {})
    foreshadow = read_json(wdir / "foreshadowing.json", {})
    chains = read_json(wdir / "event_chains.json", {})
    direct_world = " ".join(
        str(read_json(wdir / filename, {}))
        for filename in ["world_bible.json", "power_system.json", "items.json", "techniques.json", "factions.json", "locations.json", "npcs.json"]
    )

    checks = {
        "npc_motives_quality": score_npc_motives(npc),
        "ability_boundaries_quality": score_ability_boundaries(ability),
        "foreshadowing_quality": score_foreshadowing(foreshadow),
        "event_chains_quality": score_event_chains(chains),
        "canon_evidence_quality": score_evidence_quality(npc, ability, foreshadow, chains),
        "template_pollution_risk": score_template_pollution(direct_world, npc, ability, foreshadow, chains),
    }
    scores = {key: value[0] for key, value in checks.items()}
    notes = [note for _, result_notes in checks.values() for note in result_notes]
    overall = round(sum(scores.values()) / len(scores)) if scores else 0
    recommendations = []
    if scores.get("npc_motives_quality", 0) < 85:
        recommendations.append("增加 LLM-assisted chunk 数，并重点抽 NPC 目标、恐惧、筹码、底线。")
    if scores.get("ability_boundaries_quality", 0) < 85:
        recommendations.append("补充 ability_boundaries 的 cannot_do、costs、risks、requirements。")
    if scores.get("foreshadowing_quality", 0) < 85:
        recommendations.append("补充伏笔 surface_clue、reveal_conditions 和 payoff；不要提前剧透 hidden_truth。")
    if scores.get("event_chains_quality", 0) < 85:
        recommendations.append("补充事件链 deadline、intervention outcome、ignored consequence 和 follow-up。")
    if scores.get("template_pollution_risk", 100) < 100:
        recommendations.append("检查疑似题材模板污染词，确认它们是否有原著证据。")
    if not recommendations:
        recommendations.append("叙事智能层质量良好；下一步可以增加真实试玩用例。")

    report = {
        "world": world,
        "overall_score": overall,
        "scores": scores,
        "notes": notes,
        "recommendations": recommendations,
    }
    write_json(wdir / "distillation_score.json", report)
    (wdir / "distillation_score.md").write_text(markdown(report), encoding="utf-8")
    manifest = load_manifest(wdir, world)
    manifest["distillation_score"] = "distillation_score.json"
    save_manifest(wdir, manifest)
    print(f"Distillation score: {overall}/100")
    print(f"Wrote {wdir / 'distillation_score.md'}")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Score narrative distillation quality, not just file completeness.")
    parser.add_argument("--world", required=True)
    args = parser.parse_args()
    distillation_qa(args.world)


if __name__ == "__main__":
    main()
