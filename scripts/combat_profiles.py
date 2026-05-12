#!/usr/bin/env python3
from __future__ import annotations

from typing import Any

from gameplay_profile import load_gameplay_profile


COMBAT_PROFILES: dict[str, dict[str, Any]] = {
    "xuanhuan": {
        "secondary_risks": ["境界压制", "灵力反噬", "丹药消耗"],
        "resource_pressure": "境界和资源决定越级空间。",
        "effects_on_attack": [{"type": "state", "key": "combat_aura_exposed", "value": True}],
        "victory_note": "胜利会提升声望，但也可能引来更高境界注意。",
    },
    "xianxia": {
        "secondary_risks": ["因果牵连", "灵力反噬", "心魔"],
        "resource_pressure": "法宝、护身手段和灵力余量会显著影响战斗后果。",
        "effects_on_attack": [{"type": "state", "key": "karma_stirred", "value": True}],
        "victory_note": "胜利可能带来因果和宗门关注。",
    },
    "wuxia": {
        "secondary_risks": ["伤势", "名声", "仇家"],
        "resource_pressure": "内力、距离、招式克制和江湖声望比单纯伤害更重要。",
        "effects_on_attack": [{"type": "state", "key": "jianghu_reputation_changed", "value": True}],
        "victory_note": "胜负会影响名声，未必需要击杀。",
    },
    "cyberpunk": {
        "secondary_risks": ["公司追踪", "义体过载", "警报等级", "弹药消耗"],
        "resource_pressure": "算力、义体状态、监控和弹药会改变战斗成本。",
        "effects_on_attack": [{"type": "state", "key": "alert_level", "value": "raised"}],
        "victory_note": "战斗可能留下摄像头、弹道或网络追踪痕迹。",
    },
    "scifi": {
        "secondary_risks": ["能源消耗", "暴露坐标", "装备损耗"],
        "resource_pressure": "能源、护甲、舰队或设备权限会影响胜负。",
        "effects_on_attack": [{"type": "state", "key": "signal_exposure", "value": True}],
        "victory_note": "胜利可能暴露坐标或消耗关键能源。",
    },
    "mystery": {
        "secondary_risks": ["理智损耗", "污染", "禁忌知识反噬"],
        "resource_pressure": "理智和污染比生命更关键，获胜也可能付出精神代价。",
        "effects_on_attack": [{"type": "state", "key": "contamination_trace", "value": True}],
        "victory_note": "胜利不代表安全，污染和追踪可能继续存在。",
    },
    "apocalypse": {
        "secondary_risks": ["噪音", "感染", "弹药", "队友士气"],
        "resource_pressure": "弹药、体力、伤口感染和噪音会决定战斗是否值得。",
        "effects_on_attack": [{"type": "state", "key": "noise_generated", "value": True}],
        "victory_note": "战斗噪音可能吸引更多威胁。",
    },
    "fantasy": {
        "secondary_risks": ["魔力枯竭", "诅咒", "阵营敌意"],
        "resource_pressure": "魔力、职业能力和装备祝福决定战斗上限。",
        "effects_on_attack": [{"type": "state", "key": "magic_signature", "value": True}],
        "victory_note": "法术痕迹可能被敌对阵营追踪。",
    },
    "generic": {
        "secondary_risks": ["受伤", "资源消耗", "暴露"],
        "resource_pressure": "战斗会消耗状态和机会成本。",
        "effects_on_attack": [],
        "victory_note": "胜利仍会产生时间、声望或资源后果。",
    },
}


def combat_profile_for(rpg_profile: dict[str, Any], world: str | None = None) -> dict[str, Any]:
    if world:
        gameplay = load_gameplay_profile(world)
        combat = gameplay.get("combat", {})
        if isinstance(combat, dict) and combat:
            return {
                **combat,
                "source": "gameplay_profile",
                "source_policy": gameplay.get("policy", "canon-first gameplay profile"),
            }
    genre = str(rpg_profile.get("genre") or "generic")
    fallback = COMBAT_PROFILES.get(genre, COMBAT_PROFILES["generic"])
    return {
        **fallback,
        "derived_from_canon": False,
        "fallback_used": True,
        "source": "genre_fallback_low_confidence",
    }


def combat_risk_note(profile: dict[str, Any]) -> str:
    risks = "；".join(str(risk).rstrip("。；;") for risk in profile.get("secondary_risks", [])[:4])
    pressure = profile.get("resource_pressure", "")
    prefix = "原著证据战斗风险" if profile.get("derived_from_canon") else "低置信通用战斗风险"
    return f"{prefix}：{risks}。{pressure}"
