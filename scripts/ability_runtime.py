#!/usr/bin/env python3
from __future__ import annotations

from typing import Any

from common import read_json, world_dir


BOUNDARY_ACTION_WORDS = (
    "使用",
    "发动",
    "施展",
    "催动",
    "炼化",
    "吞噬",
    "收服",
    "突破",
    "攻击",
    "战斗",
    "秒杀",
    "烧死",
    "强行",
)
OVERREACH_WORDS = ("秒杀", "无视", "直接", "一定", "随便", "无代价", "强行", "硬抗", "碾压")


def load_ability_boundaries(world: str) -> dict[str, Any]:
    return read_json(world_dir(world) / "ability_boundaries.json", {})


def find_ability_boundary(world: str, player_input: str) -> dict[str, Any] | None:
    data = load_ability_boundaries(world)
    for row in data.get("abilities", []):
        name = str(row.get("name") or "")
        if name and name in player_input:
            return row
    return None


def _short(value: Any, limit: int = 42) -> str:
    text = str(value or "").replace("\n", " ").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip("，。；： ") + "…"


def _join(values: list[Any], limit: int = 2) -> str:
    return "；".join(_short(value) for value in values[:limit] if str(value))


def _clean(text: str) -> str:
    return text.rstrip("。；; ")


def evaluate_ability_use(world: str, player_input: str, state: dict[str, Any]) -> dict[str, Any] | None:
    if not any(word in player_input for word in BOUNDARY_ACTION_WORDS):
        return None
    boundary = find_ability_boundary(world, player_input)
    if not boundary:
        return None

    name = str(boundary.get("name") or "能力")
    can_do = _clean(_join(boundary.get("can_do", [])) or "只能提供与 canon 描述一致的有限优势")
    cannot_do = _clean(_join(boundary.get("cannot_do", [])) or "不能绕过硬前置或声明自动成功")
    costs = _clean(_join(boundary.get("costs", [])) or "需要资源、时间或状态代价")
    risks = _clean(_join(boundary.get("risks", [])) or "失败会带来资源、关系或状态后果")
    requirements = _clean(_join(boundary.get("requirements", [])) or "需要满足当前状态、地点、资源或能力前置")

    player = state.setdefault("player", {})
    stats = player.setdefault("stats", {})
    resource = float(stats.get("mp", 0) or 0)
    overreach = any(word in player_input for word in OVERREACH_WORDS)
    if overreach:
        return {
            "kind": "ability_boundary",
            "status": "partial_or_blocked",
            "verdict": f"「{name}」不能越过能力边界",
            "consequence": (
                f"「{name}」可以：{can_do}。但边界是：{cannot_do}。"
                f"本回合最多转为试探、威慑、准备或低风险使用；不能把能力当万能钥匙。"
                f"前置：{requirements}。风险：{risks}。"
            ),
            "state_changes": [f"检查能力边界：{name}"],
            "options": [
                f"按「{name}」的前置条件做准备。",
                "改为低风险试探。",
                "寻找导师、材料、地点或护持。",
            ],
            "boundary": boundary,
        }

    if resource <= 0 and any(word in player_input for word in ("战斗", "攻击", "施展", "催动", "突破")):
        return {
            "kind": "ability_boundary",
            "status": "blocked",
            "verdict": f"「{name}」缺少可用资源",
            "consequence": f"你想使用「{name}」，但当前资源不足。该能力通常需要：{costs}。风险：{risks}。",
            "state_changes": [],
            "options": ["先恢复资源。", "寻找替代方案。", "改为信息或社交行动。"],
            "boundary": boundary,
        }

    return {
        "kind": "ability_boundary",
        "status": "allowed",
        "verdict": f"「{name}」可尝试但需结算代价",
        "consequence": f"「{name}」可支持本行动，但只提供有限优势；仍需结算资源消耗、地点条件和失败风险。",
        "state_changes": [f"检查能力边界：{name}"],
        "options": [
            f"按「{name}」的安全用法推进。",
            "先补足前置条件。",
            "准备失败后的撤退方案。",
        ],
        "boundary": boundary,
    }
