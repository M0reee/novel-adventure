#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from typing import Any

from common import load_manifest, read_json, save_manifest, world_dir, write_json
from economy_runtime import apply_economy_state_to_market, build_economy_state
from rpg_profile import load_rpg_profile


RARITY_PRICE = {
    "common": (5, 20),
    "uncommon": (30, 120),
    "rare": (300, 1200),
    "epic": (3000, 12000),
    "legendary": (50000, 200000),
    "mythic": (500000, 5000000),
}

RARITY_KEYWORDS = [
    ("mythic", ("异火", "帝", "神", "菩提心", "净莲妖火", "虚无吞炎")),
    ("legendary", ("天阶", "菩提", "玄龙丹", "骨灵冷火", "陨落心炎", "青莲地心火")),
    ("epic", ("地阶", "玄重尺", "飞行", "高阶", "血莲丹")),
    ("rare", ("聚气散", "魔核", "纳戒", "复灵紫丹", "药方", "灵液")),
    ("uncommon", ("丹", "药", "草", "花", "卷轴", "令牌")),
]

DOUPO_OVERRIDES = {
    "筑基灵液": {
        "rarity": "rare",
        "price_range": [800, 1600],
        "purchase_conditions": ["可靠药坊或拍卖场有货", "确认不是赝品", "支付足够金币或拿出等价人情/药材"],
        "alternate_acquisition": ["收集药材请炼药师炼制", "替药坊完成低风险委托", "向熟识 NPC 借钱或换取人情债"],
        "use_effect": {
            "effect_id": "foundation_elixir_training",
            "name": "筑基灵液辅助",
            "duration_turns": 3,
            "modifiers": {"damage_reduction": 0.02},
            "notes": "主要用于早期修炼效率，不直接保证突破。",
        },
    },
    "聚气散": {
        "rarity": "epic",
        "price_range": [6000, 15000],
        "purchase_conditions": ["拍卖或高阶炼药渠道", "有足够金币或势力担保", "确认适合冲击斗者"],
        "alternate_acquisition": ["取得药方与材料后请炼药师炼制", "完成势力任务换取", "等待拍卖会机会"],
    },
    "魔核": {
        "rarity": "uncommon",
        "price_range": [80, 300],
        "purchase_conditions": ["坊市或佣兵渠道有货", "确认阶别和属性"],
        "alternate_acquisition": ["猎杀低阶魔兽", "雇佣佣兵", "用药材交换"],
    },
    "纳戒": {
        "rarity": "rare",
        "price_range": [1200, 5000],
        "purchase_conditions": ["拍卖场或炼器渠道", "防止被强者盯上"],
        "alternate_acquisition": ["任务奖励", "遗迹探索", "长辈赠予"],
    },
    "异火": {
        "rarity": "mythic",
        "price_range": [0, 0],
        "purchase_conditions": ["不可常规购买", "必须有位置情报、护法、丹药、克制手段和退路"],
        "alternate_acquisition": ["长期主线探索", "高风险收服", "势力争夺"],
    },
}

BAD_MARKET_NAMES = {
    "炼药",
    "炼丹",
    "炼制丹药",
    "卷轴",
    "丹药",
    "药材",
    "这些药",
    "听得药",
    "一名炼药",
    "那神秘炼药",
    "罪一名六品炼药",
    "这座丹",
    "收入纳戒",
    "一些药",
    "四品炼药",
    "传出药",
    "两种丹药",
    "其纳戒",
    "七瓶筑基灵液",
    "当筑基灵液",
    "第一瓶筑基灵液",
    "场中剑",
}
BAD_MARKET_FRAGMENTS = ("。", "，", "、", "：", "；", "？", "！", "\n", "听得", "这些", "一名", "那神秘", "罪一名", "这座", "收入", "炼制")
ITEM_NAME_WORDS = (
    "丹",
    "灵液",
    "药",
    "魔核",
    "晶核",
    "灵石",
    "戒指",
    "纳戒",
    "枪",
    "剑",
    "尺",
    "刀",
    "火焰",
    "异火",
    "骨",
    "环",
    "令牌",
    "残图",
    "地图",
    "乳",
    "鼎",
    "草",
    "花",
    "果",
)


def stable_id(prefix: str, name: str) -> str:
    digest = hashlib.sha1(name.encode("utf-8")).hexdigest()[:10]
    return f"{prefix}_{digest}"


def infer_rarity(name: str, summary: str) -> str:
    text = f"{name} {summary}"
    for rarity, keywords in RARITY_KEYWORDS:
        if any(keyword in text for keyword in keywords):
            return rarity
    return "common"


def valid_market_name(name: str) -> bool:
    stripped = name.strip(" 「」《》[]()（）")
    if not stripped or stripped in BAD_MARKET_NAMES:
        return False
    if len(stripped) > 12:
        return False
    if any(fragment in stripped for fragment in BAD_MARKET_FRAGMENTS):
        return False
    if stripped.startswith(("这", "那", "此", "该", "一名", "一种", "其", "当", "第一", "一瓶", "七瓶")):
        return False
    return any(word in stripped for word in ITEM_NAME_WORDS)


def market_entry(item: dict[str, Any], profile: dict[str, Any], world: str) -> dict[str, Any]:
    name = str(item.get("name", "未知物品"))
    summary = str(item.get("summary") or item.get("claim") or "")
    rarity = infer_rarity(name, summary)
    low, high = RARITY_PRICE[rarity]
    entry = {
        "item_id": stable_id("item", name),
        "name": name,
        "aliases": item.get("aliases", []),
        "summary": summary,
        "rarity": rarity,
        "currency": profile.get("systems", {}).get("currency_name", "货币"),
        "price_range": [low, high],
        "purchase_conditions": ["找到可靠卖家", "支付足够货币", "确认物品真伪与适用条件"],
        "alternate_acquisition": ["探索获得", "任务奖励", "与 NPC 交易或交换人情"],
        "use_requirements": ["拥有该物品", "满足境界/身份/技能条件", "有安全使用环境"],
        "use_effect": {},
        "canon_summary": summary,
    }
    if world.startswith("doupo") and name in DOUPO_OVERRIDES:
        entry.update(DOUPO_OVERRIDES[name])
        entry["currency"] = profile.get("systems", {}).get("currency_name", entry["currency"])
    return entry


def build_economy(world: str) -> dict[str, Any]:
    wdir = world_dir(world)
    profile = load_rpg_profile(world)
    items = read_json(wdir / "items.json", {}).get("items", [])
    entries = [market_entry(item, profile, world) for item in items if item.get("name") and valid_market_name(str(item.get("name")))]
    output = {
        "world": world,
        "currency": profile.get("systems", {}).get("currency_name", "货币"),
        "pricing_policy": "价格是可玩参数，不等同于原文硬 canon；如果用户指出原文价格，以 canon_patches 或本文件覆盖。",
        "items": entries,
    }
    write_json(wdir / "item_market.json", output)
    build_economy_state(world)
    manifest = load_manifest(wdir, world)
    manifest["item_market"] = "item_market.json"
    save_manifest(wdir, manifest)
    print(f"Built item_market.json items={len(entries)} currency={output['currency']}")
    return output


def load_market(world: str) -> dict[str, Any]:
    wdir = world_dir(world)
    market = read_json(wdir / "item_market.json", {})
    market = market if market else build_economy(world)
    return apply_economy_state_to_market(world, market)


def find_market_item(player_input: str, canon_rows: list[dict[str, Any]], market: dict[str, Any]) -> dict[str, Any] | None:
    items = market.get("items", [])
    candidates: list[str] = []
    candidates.extend(row.get("name", "") for row in canon_rows if "item" in str(row.get("type", "")))
    candidates.extend(item.get("name", "") for item in items)
    for name in candidates:
        if name and name in player_input:
            return next((item for item in items if item.get("name") == name), None)
    return None


def price_text(item: dict[str, Any]) -> str:
    low, high = item.get("effective_price_range") or item.get("price_range", [0, 0])
    currency = item.get("currency", "货币")
    if int(low) <= 0 and int(high) <= 0:
        return f"不可常规购买（{currency}价格无效）"
    return f"{int(low)}-{int(high)} {currency}"


def can_afford(player: dict[str, Any], item: dict[str, Any]) -> tuple[bool, int, int]:
    coins = int(player.get("currencies", {}).get("coins", 0))
    low = int((item.get("effective_price_range") or item.get("price_range", [0, 0]))[0])
    return coins >= low > 0, coins, low


def main() -> None:
    parser = argparse.ArgumentParser(description="Build or inspect item market data for a world.")
    parser.add_argument("--world", required=True)
    parser.add_argument("--rebuild", action="store_true")
    args = parser.parse_args()
    market = build_economy(args.world) if args.rebuild else load_market(args.world)
    print(json.dumps(market, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
