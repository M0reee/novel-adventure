#!/usr/bin/env python3
from __future__ import annotations

from typing import Any


RISK_WORDS = ("硬闯", "强闯", "偷", "抢", "杀", "威胁", "潜入", "追杀", "突破", "收服", "挑战")
SOCIAL_WORDS = ("搭话", "询问", "请教", "交易", "交换", "打好关系", "贿赂", "承诺", "求助")
INFO_WORDS = ("观察", "打听", "确认", "调查", "判断", "探查", "偷听")
TRAINING_WORDS = ("修炼", "训练", "突破", "吐纳", "练习", "休整", "学习", "领悟", "参悟", "练成")
TRADE_WORDS = ("买", "卖", "购买", "出售", "询价", "核价", "拍卖")
COMBAT_WORDS = ("攻击", "战斗", "切磋", "击败", "反击", "打倒")
RESOURCE_WORDS = ("丹", "药", "魔核", "金币", "资源", "斗技", "功法", "装备", "材料", "线索")


def contains_any(text: str, words: tuple[str, ...]) -> bool:
    return any(word in text for word in words)


def infer_kind(text: str, forced_kind: str | None = None) -> str:
    if forced_kind and forced_kind != "general":
        return forced_kind
    if contains_any(text, COMBAT_WORDS):
        return "combat"
    if contains_any(text, TRADE_WORDS):
        return "trade"
    if contains_any(text, TRAINING_WORDS):
        return "cultivation"
    if contains_any(text, SOCIAL_WORDS):
        return "social"
    if contains_any(text, INFO_WORDS):
        return "info"
    return "general"


def infer_target(text: str, scene: dict[str, Any] | None = None) -> str:
    scene = scene or {}
    for bucket in ("npcs", "resources", "hooks", "locations"):
        for item in scene.get(bucket, []):
            name = str(item.get("name", ""))
            if name and name in text:
                return name
    quoted = []
    for left, right in (("「", "」"), ("《", "》"), ("\"", "\"")):
        if left in text and right in text:
            value = text.split(left, 1)[1].split(right, 1)[0].strip()
            if value:
                quoted.append(value)
    return quoted[0] if quoted else ""


def estimate_risk(text: str, kind: str, scene: dict[str, Any] | None = None) -> str:
    scene_risk = str((scene or {}).get("risk", "medium"))
    if contains_any(text, RISK_WORDS):
        return "high"
    if kind in {"combat"}:
        return "high" if scene_risk != "low" else "medium"
    if kind in {"trade", "social", "info"}:
        return "low" if scene_risk == "low" else "medium"
    return scene_risk


def required_checks(kind: str, text: str) -> list[str]:
    checks = ["当前地点", "玩家状态", "canon 边界"]
    if kind == "social":
        checks.extend(["目标 NPC 是否可接触", "关系分数", "可交换筹码"])
    elif kind == "trade":
        checks.extend(["金币/货币", "市场供应", "真假风险"])
    elif kind == "cultivation":
        checks.extend(["安全环境", "资源消耗", "能力边界"])
    elif kind == "combat":
        checks.extend(["敌我属性", "技能消耗", "撤退后果"])
    elif kind == "info":
        checks.extend(["信息来源", "耗时", "是否暴露意图"])
    if contains_any(text, RESOURCE_WORDS):
        checks.append("资源来源和稀缺度")
    return checks


def analyze_action(player_input: str, forced_kind: str | None = None, scene: dict[str, Any] | None = None) -> dict[str, Any]:
    text = str(player_input or "")
    kind = infer_kind(text, forced_kind)
    target = infer_target(text, scene)
    risk = estimate_risk(text, kind, scene)
    return {
        "kind": kind,
        "target": target,
        "risk": risk,
        "checks": required_checks(kind, text),
        "allows_auto_success": False,
        "policy": "玩家只能声明尝试；成功、代价和收益由 canon、状态、资源、关系、地点和风险共同裁定。",
    }


def action_intent_lines(intent: dict[str, Any]) -> list[str]:
    target = intent.get("target") or "未锁定具体对象"
    checks = "、".join(str(item) for item in intent.get("checks", [])[:6])
    return [
        f"- 意图：{intent.get('kind', 'general')}",
        f"- 对象：{target}",
        f"- 风险：{intent.get('risk', 'medium')}",
        f"- 必查：{checks}",
    ]
