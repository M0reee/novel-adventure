#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from typing import Any

from common import load_manifest, read_json, save_manifest, world_dir, write_json


DEFAULT_CHANNELS = [
    {"kind": "combat", "rewards": ["历练/经验", "少量货币", "掉落物"], "rule": "必须由 combat.py 结算。"},
    {"kind": "quest", "rewards": ["报酬", "关系", "情报", "地点入口"], "rule": "必须完成任务阶段或交付证据后结算。"},
    {"kind": "info", "rewards": ["线索", "价格", "风险边界"], "rule": "不能直接给物品、技能或突破。"},
    {"kind": "trade", "rewards": ["价格", "货源", "真假风险", "购买机会"], "rule": "必须检查货币、库存、可信卖家和使用条件。"},
    {"kind": "social", "rewards": ["关系", "人情", "条件", "低风险机会"], "rule": "不能让 NPC 违背动机和底线。"},
    {"kind": "cultivation", "rewards": ["历练", "熟练度", "状态理解"], "rule": "不能跳过境界、资源和地点限制。"},
    {"kind": "location", "rewards": ["入口", "可见 NPC", "资源点", "风险信息"], "rule": "知道地点不等于安全进入。"},
    {"kind": "general", "rewards": ["场景推进", "轻微信息"], "rule": "普通行动不能替代明确的交易、社交、任务或修炼结算。"},
]


def build_reward_policy(world: str) -> dict[str, Any]:
    wdir = world_dir(world)
    rpg = read_json(wdir / "rpg_profile.json", {})
    currency = rpg.get("systems", {}).get("currency_name", "货币")
    output = {
        "world": world,
        "policy": "Rewards must be earned through structured resolution and canon-compatible channels. Hints are not grants.",
        "currency": currency,
        "channels": DEFAULT_CHANNELS,
    }
    write_json(wdir / "reward_policy.json", output)
    manifest = load_manifest(wdir, world)
    manifest["reward_policy"] = "reward_policy.json"
    save_manifest(wdir, manifest)
    print("Built reward_policy.json")
    return output


def record_reward_channel(world: str, state: dict[str, Any], resolution: dict[str, Any], turn: int) -> list[str]:
    policy = read_json(world_dir(world) / "reward_policy.json", {})
    kind = str(resolution.get("kind") or "general")
    channel = next((row for row in policy.get("channels", []) if row.get("kind") == kind), None)
    if not channel:
        channel = next((row for row in DEFAULT_CHANNELS if row.get("kind") == kind), None)
    if not channel:
        channel = next(row for row in DEFAULT_CHANNELS if row.get("kind") == "general")
    ledger = state.setdefault("runtime", {}).setdefault("reward_ledger", [])
    entry = {
        "turn": turn,
        "kind": kind,
        "status": resolution.get("status"),
        "eligible_rewards": channel.get("rewards", []),
        "rule": channel.get("rule"),
        "grant_status": "线索或资格，不直接发放" if resolution.get("status") != "resolved" else "按结构化结算记录",
    }
    ledger.append(entry)
    del ledger[:-50]
    return [f"收益通道：{kind} 可产生 {'、'.join(channel.get('rewards', [])[:3])}；{channel.get('rule')}"]


def reward_policy_lines(state: dict[str, Any]) -> list[str]:
    ledger = state.get("runtime", {}).get("reward_ledger", [])
    if not ledger:
        return ["- 暂无收益记录。"]
    last = ledger[-1]
    return [f"- 本回合方向：{last.get('kind')}；可能收益：{'、'.join(last.get('eligible_rewards', [])[:4])}；状态：{last.get('grant_status')}"]


def main() -> None:
    parser = argparse.ArgumentParser(description="Build reward policy projection.")
    parser.add_argument("--world", required=True)
    parser.add_argument("--rebuild", action="store_true")
    args = parser.parse_args()
    data = build_reward_policy(args.world) if args.rebuild else read_json(world_dir(args.world) / "reward_policy.json", {})
    print(json.dumps(data, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
