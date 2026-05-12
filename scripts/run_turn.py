#!/usr/bin/env python3
from __future__ import annotations

import argparse
from typing import Any

from action_resolver import resolve_action
from common import default_player_state, migrate_player_state, write_json, world_dir
from game_math import computed_stats
from retrieve import retrieve
from rpg_profile import apply_rpg_profile_to_state, format_stat_block, load_rpg_profile
from save_manager import load_save, save_path, write_save


HIGH_RISK_WORDS = ("硬闯", "强闯", "击杀", "挑战", "突破", "偷袭", "抢夺", "潜入", "威胁", "追杀")
INFO_WORDS = ("打听", "询问", "调查", "观察", "探查", "侦查")
CULTIVATION_WORDS = ("修炼", "闭关", "突破", "炼化", "冲关")
TRADE_WORDS = ("购买", "交易", "出售", "买", "卖")
DECLARED_SUCCESS_WORDS = ("直接成功", "一定成功", "秒杀", "无敌", "立刻突破", "马上成仙", "随便拿走")
BLOCKING_MARKERS = ("不可", "不能", "禁止", "无法", "必须", "需要", "代价", "风险", "失败")


def summarize_canon(rows: list[dict[str, Any]]) -> list[str]:
    lines = []
    seen: set[tuple[str, str]] = set()
    for row in rows:
        row_type = str(row.get("type", ""))
        if row_type.startswith("playable_"):
            continue
        key = (row_type, str(row.get("name", "")))
        if key in seen:
            continue
        seen.add(key)
        claim = row.get("claim", "").strip()
        if claim:
            lines.append(f"- [{row_type}] {row.get('name')}: {claim[:140]}")
        if len(lines) >= 6:
            break
    return lines


def summarize_playable(rows: list[dict[str, Any]]) -> list[str]:
    lines = []
    seen_names: set[str] = set()
    for row in rows:
        row_type = str(row.get("type", ""))
        if not row_type.startswith("playable_"):
            continue
        name = str(row.get("name", ""))
        if name in seen_names:
            continue
        seen_names.add(name)
        claim = row.get("claim", "").strip()
        if claim:
            lines.append(f"- [{row_type}] {name}: {claim[:180]}")
        if len(lines) >= 4:
            break
    return lines


def adjudicate_action(player_input: str, state: dict[str, Any], canon_rows: list[dict[str, Any]]) -> dict[str, str]:
    hard_claims = " ".join(row.get("claim", "") for row in canon_rows if row.get("type") == "canon_patch")
    all_claims = hard_claims + " " + " ".join(row.get("claim", "") for row in canon_rows[:10])
    player = state.get("player", {})
    realm = str(player.get("realm_or_level", player.get("realm", "")))
    status = "allowed"
    verdict = "可执行"
    consequence = "行动被纳入当前场景推进，世界会根据已检索到的设定给出相应反馈。"

    if any(word in player_input for word in DECLARED_SUCCESS_WORDS):
        status = "blocked"
        verdict = "声明式成功无效"
        consequence = "你不能直接声明结果；本回合只裁定你的尝试，并根据 canon、状态和风险决定后果。"
    elif any(word in player_input for word in HIGH_RISK_WORDS) and any(word in all_claims for word in BLOCKING_MARKERS):
        status = "partial_or_blocked"
        verdict = "高风险行动需要前置条件"
        consequence = "你的行动触碰了当前世界硬规则或高风险边界，不能直接成功；本回合转为试探、准备或寻找替代路径。"
    elif any(word in player_input for word in INFO_WORDS):
        status = "allowed"
        verdict = "信息行动可执行但消耗时间"
        consequence = "你放慢节奏收集信息，获得了更清晰的局势判断，但也消耗了一段时间。"
    elif any(word in player_input for word in TRADE_WORDS):
        status = "conditional"
        verdict = "交易行动受价格、稀缺度和势力关系影响"
        consequence = "交易行动展开；价格、真假和旁人觊觎会根据当地势力与物品稀缺度变化。"
    elif any(word in player_input for word in CULTIVATION_WORDS):
        status = "conditional"
        verdict = "修炼行动受境界、资源和地点限制"
        consequence = "你尝试运转力量体系内的修炼路径，进展取决于资源、地点安全和当前境界限制。"

    if "凡人" in realm and any(word in player_input for word in ("御剑", "飞行", "天劫", "元婴", "金丹")):
        status = "blocked"
        verdict = "当前实力不支持该行动"
        consequence = "以你当前层级无法直接完成这个行动；你需要先获得外物、导师、情报或更低风险的路径。"

    return {"status": status, "verdict": verdict, "consequence": consequence}


def build_options(player_input: str, state: dict[str, Any], canon_rows: list[dict[str, Any]], resolution: dict[str, Any]) -> list[str]:
    location = state.get("meta", {}).get("current_location", "当前位置")
    options = list(resolution.get("options", []))
    options.extend([
        f"继续在{location}谨慎探索，优先确认风险。",
        "寻找可交流的 NPC，打听势力、资源或任务线索。",
        "整理背包和状态，选择是否修炼、休整或交易。",
    ])
    for row in canon_rows:
        if row.get("type") == "location" or "location" in row.get("type", ""):
            options.append(f"转向与「{row.get('name')}」相关的地点线索。")
            break
    for row in canon_rows:
        if "hook" in row.get("type", "") or row.get("source_json") == "adventure_hooks.json":
            options.append(f"追踪冒险钩子：{row.get('name')}。")
            break
    deduped: list[str] = []
    for option in options:
        if option and option not in deduped:
            deduped.append(option)
        if len(deduped) >= 5:
            break
    return deduped


def run_turn(world: str, player_input: str, limit: int, dry_run: bool, slot: str | None = None) -> str:
    wdir = world_dir(world)
    state_path = save_path(world, slot)
    state = migrate_player_state(load_save(world, slot, default_player_state(world)), world)
    rpg_profile = load_rpg_profile(world)
    state = apply_rpg_profile_to_state(state, rpg_profile)
    meta = state.setdefault("meta", {})
    player = state.setdefault("player", {})
    query = " ".join(
        [
            player_input,
            str(meta.get("current_location", "")),
            str(meta.get("current_stage", "")),
            str(player.get("realm_or_level", "")),
        ]
    )
    canon_rows = retrieve(world, query, limit)
    resolution = resolve_action(world, player_input, state, canon_rows)
    result = resolution["consequence"]
    turn = int(meta.get("turn", 0)) + 1

    state_changes = [
        f"回合数：{meta.get('turn', 0)} -> {turn}",
        *resolution.get("state_changes", []),
        "行动记录已追加。" if not dry_run else "dry-run 未写入行动记录。",
    ]
    meta["turn"] = turn
    meta["current_stage"] = "自由冒险推进中"
    state.setdefault("action_log", []).append(
        {
            "turn": turn,
            "action": player_input,
            "result": result,
            "resolution": {
                "kind": resolution.get("kind"),
                "status": resolution.get("status"),
                "verdict": resolution.get("verdict"),
            },
            "canon_used": [row.get("id") for row in canon_rows[:8]],
        }
    )
    state["action_log"] = state["action_log"][-30:]
    if not dry_run:
        write_save(world, slot, state)
        for filename, data in resolution.get("runtime_files", {}).items():
            write_json(wdir / filename, data)

    canon_lines = summarize_canon(canon_rows)
    playable_lines = summarize_playable(canon_rows)
    stats = computed_stats(state)
    options = build_options(player_input, state, canon_rows, resolution)
    output = [
        "## 场景叙事",
        f"你选择：{player_input}",
        "当前世界以检索到的设定为边界推进。相关规则和线索在暗处收束，场景不会脱离既有 canon。",
        "",
        "## 规则裁定",
        f"- 行动类型：{resolution.get('kind', 'general')}",
        f"- 裁定：{resolution['verdict']}",
        f"- 状态：{resolution['status']}",
        "",
        "## 行动结果",
        result,
        "",
        "## 状态变化",
        *[f"- {line}" for line in state_changes],
        f"- 存档：{state_path}",
        "",
        "## 人物属性",
        *format_stat_block(stats, rpg_profile),
        "",
        "## 世界动态",
        *(canon_lines or ["- 暂未检索到强相关 canon；本回合只做低影响推进。"]),
        "",
        "## 主持约束",
        *(playable_lines or ["- 未检索到额外可玩规则；按基础 canon、状态和风险裁定。"]),
        "",
        "## 可执行行动",
        *[f"{idx}. {option}" for idx, option in enumerate(options, 1)],
        "",
        "## 自定义行动",
        "你也可以输入任意自定义行动；下一回合会先检索相关 canon，再判断结果。",
    ]
    return "\n".join(output)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run one text adventure turn using retrieved canon.")
    parser.add_argument("--world", required=True)
    parser.add_argument("--input", required=True)
    parser.add_argument("--slot", help="Named save slot. Default uses player_state.json.")
    parser.add_argument("--limit", type=int, default=30)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    print(run_turn(args.world, args.input, args.limit, args.dry_run, args.slot))


if __name__ == "__main__":
    main()
