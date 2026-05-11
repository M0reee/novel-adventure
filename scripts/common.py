#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable


FACT_TYPES = {
    "world_law",
    "power_realm",
    "cultivation_rule",
    "faction",
    "location",
    "npc",
    "item",
    "technique",
    "event",
    "relationship",
    "style_signal",
    "playable_hook",
}

SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
WORLDS_DIR = SKILL_DIR / "worlds"

CHINESE_PUNCT_RE = re.compile(r"(?<=[。！？!?；;])\s*")

DOUPO_REALMS = [
    "斗之力",
    "斗之气",
    "斗者",
    "斗师",
    "大斗师",
    "斗灵",
    "斗王",
    "斗皇",
    "斗宗",
    "斗尊",
    "半圣",
    "斗圣",
    "斗帝",
]

DOUPO_NPCS = [
    "萧炎",
    "药老",
    "药尘",
    "纳兰嫣然",
    "萧薰儿",
    "薰儿",
    "美杜莎",
    "彩鳞",
    "云韵",
    "萧战",
    "萧玄",
    "小医仙",
    "紫研",
    "海波东",
    "雅妃",
    "韩枫",
    "云山",
    "云棱",
    "古河",
    "林焱",
    "苏千",
    "萧厉",
    "萧鼎",
    "魂天帝",
    "古元",
    "烛坤",
    "净莲妖圣",
    "萧媚",
    "萧玉",
    "若琳",
    "琥嘉",
    "吴昊",
    "白山",
    "范痨",
    "范凌",
    "莫天行",
    "曜天火",
    "风尊者",
    "慕青鸾",
    "曹颖",
    "丹晨",
    "玄空子",
    "慕骨老人",
    "凤清儿",
    "凰天",
    "魂玉",
    "萧潇",
]


DOUPO_FACTIONS = [
    "萧家",
    "云岚宗",
    "纳兰家",
    "米特尔家族",
    "特米尔家族",
    "加玛帝国",
    "迦南学院",
    "内院",
    "炼药师公会",
    "狼头佣兵团",
    "蛇人族",
    "黑角域",
    "魂殿",
    "魂族",
    "古族",
    "炎盟",
    "星陨阁",
    "丹塔",
    "焚炎谷",
    "花宗",
    "天府联盟",
    "太虚古龙族",
    "萧族",
    "雷族",
    "炎族",
    "药族",
    "石族",
    "灵族",
    "天妖凰族",
    "九幽地冥蟒族",
    "狮冥宗",
    "冰河谷",
    "冥河盟",
]


DOUPO_LOCATIONS = [
    "乌坦城",
    "萧家后山",
    "魔兽山脉",
    "加玛帝国",
    "塔戈尔沙漠",
    "黑岩城",
    "云岚山",
    "云岚宗",
    "迦南学院",
    "黑角域",
    "中州",
    "星陨阁",
    "丹塔",
    "古界",
    "魂界",
    "天焚炼气塔",
    "岩浆世界",
    "萧家",
    "特米尔拍卖场",
    "米特尔拍卖场",
    "漠城",
    "石漠城",
    "蛇人圣城",
    "黑印城",
    "枫城",
    "星界",
    "兽域",
    "莽荒古域",
    "菩提古树",
    "妖火空间",
]


DOUPO_ITEMS = [
    "玄重尺",
    "纳戒",
    "筑基灵液",
    "聚气散",
    "青莲地心火",
    "陨落心炎",
    "骨灵冷火",
    "海心焰",
    "净莲妖火",
    "虚无吞炎",
    "异火",
    "魔核",
    "紫叶兰草",
    "洗骨花",
    "冰灵寒泉",
    "血莲丹",
    "复灵紫丹",
    "阴阳玄龙丹",
    "菩提子",
    "菩提心",
]


DOUPO_TECHNIQUES = [
    "焚诀",
    "佛怒火莲",
    "八极崩",
    "吸掌",
    "吹火掌",
    "焰分噬浪尺",
    "三千雷动",
    "天火三玄变",
    "黄泉天怒",
    "怒狮狂罡",
    "紫云翼",
    "狮山裂",
    "大天造化掌",
    "帝印决",
    "开山印",
    "翻海印",
    "覆地印",
]



PROFILES: dict[str, dict[str, Any]] = {
    "generic": {
        "realm_terms": [],
        "known_npcs": [],
        "known_factions": [],
        "known_locations": [],
        "known_items": [],
        "known_techniques": [],
        "faction_suffixes": ("宗", "门", "派", "族", "家族", "学院", "帝国", "皇室", "公会", "联盟", "佣兵团", "殿", "阁", "谷", "塔"),
        "location_suffixes": ("城", "山", "谷", "林", "域", "国", "院", "塔", "沙漠", "山脉", "洞府", "遗迹", "空间", "界"),
    },
    "doupo": {
        "realm_terms": DOUPO_REALMS,
        "known_npcs": DOUPO_NPCS,
        "known_factions": DOUPO_FACTIONS,
        "known_locations": DOUPO_LOCATIONS,
        "known_items": DOUPO_ITEMS,
        "known_techniques": DOUPO_TECHNIQUES,
        "faction_suffixes": ("宗", "族", "家族", "学院", "帝国", "皇室", "公会", "联盟", "佣兵团", "殿"),
        "location_suffixes": ("城", "山", "山脉", "沙漠", "学院", "帝国", "域", "塔", "界", "谷", "空间"),
    },
}


def get_profile(name: str | None) -> dict[str, Any]:
    profile_name = (name or "generic").lower()
    if profile_name not in PROFILES:
        raise SystemExit(f"Unknown profile: {profile_name}. Available: {', '.join(sorted(PROFILES))}")
    profile = dict(PROFILES["generic"])
    profile.update(PROFILES[profile_name])
    profile["name"] = profile_name
    return profile


def _as_list(value: Any) -> list[str]:
    if not value:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [str(value).strip()]


def _as_tuple(value: Any, fallback: tuple[str, ...]) -> tuple[str, ...]:
    values = _as_list(value)
    return tuple(values) if values else fallback


def load_world_profile(wdir: Path, profile_name: str | None = None) -> dict[str, Any]:
    """Load a built-in profile or a generated worlds/<slug>/world_profile.json."""
    requested = (profile_name or "").lower()
    if requested in PROFILES:
        return get_profile(requested)

    manifest = read_json(wdir / "manifest.json", {})
    manifest_profile = str(manifest.get("profile") or "").lower()
    if not requested:
        requested = manifest_profile or "generic"
    if requested in PROFILES:
        return get_profile(requested)

    profile_path = wdir / "world_profile.json"
    if not profile_path.exists():
        return get_profile("generic")

    generated = read_json(profile_path, {})
    profile = get_profile("generic")
    for key in ("realm_terms", "known_npcs", "known_factions", "known_locations", "known_items", "known_techniques"):
        profile[key] = _as_list(generated.get(key))
    profile["faction_suffixes"] = _as_tuple(generated.get("faction_suffixes"), profile["faction_suffixes"])
    profile["location_suffixes"] = _as_tuple(generated.get("location_suffixes"), profile["location_suffixes"])
    profile["genre"] = generated.get("genre", "unknown")
    profile["schema"] = generated.get("schema", {})
    profile["name"] = generated.get("profile", requested or "auto")
    return profile


def world_dir(slug: str) -> Path:
    if not re.fullmatch(r"[A-Za-z0-9_-]+", slug):
        raise SystemExit("World slug must contain only letters, numbers, underscores, and hyphens.")
    path = WORLDS_DIR / slug
    path.mkdir(parents=True, exist_ok=True)
    return path


def read_text(path: Path) -> str:
    for encoding in ("utf-8", "utf-8-sig", "gb18030", "gbk"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    raise UnicodeDecodeError("unknown", b"", 0, 1, f"Could not decode {path}")


def write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def sha1_text(text: str, length: int = 12) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:length]


def now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def normalize_space(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("\u3000", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{4,}", "\n\n\n", text)
    return text.strip()


def clean_source_text(text: str) -> str:
    text = normalize_space(text)
    text = re.sub(r"-{6,}.*?用户上传之内容开始.*?-{6,}", "\n", text, flags=re.S)
    text = re.sub(r"声明：本书为TXT图书下载网.*?(?:免费下载服务。|内容开始)", "\n", text, flags=re.S)
    text = re.sub(r"分节阅读\s*\d+", "\n", text)
    text = re.sub(r"更多.*?请到.*?(?:\n|$)", "\n", text)
    text = re.sub(r"www\.[A-Za-z0-9_.-]+|bookdown\.com\.cn", "", text, flags=re.I)
    text = re.sub(r"\n\s*[-=]{8,}\s*\n", "\n", text)
    return normalize_space(text)


def sentence_split(text: str) -> list[str]:
    pieces = CHINESE_PUNCT_RE.split(text)
    return [piece.strip() for piece in pieces if piece and piece.strip()]


def text_window(text: str, start: int, end: int, before: int = 80, after: int = 140) -> str:
    return normalize_space(text[max(0, start - before) : min(len(text), end + after)]).replace("\n", " ")


def default_stats() -> dict[str, float]:
    return {
        "level": 1,
        "exp": 0,
        "exp_to_next": 100,
        "hp": 100,
        "max_hp": 100,
        "mp": 40,
        "max_mp": 40,
        "attack": 12,
        "defense": 5,
        "speed": 8,
        "hit_rate": 0.95,
        "dodge_rate": 0.03,
        "crit_rate": 0.05,
        "crit_damage": 1.5,
        "damage_bonus": 0.0,
        "damage_reduction": 0.0,
    }


def starter_skill() -> dict[str, Any]:
    return {
        "skill_id": "guarded_strike",
        "name": "稳健一击",
        "type": "attack",
        "mp_cost": 0,
        "cooldown": 0,
        "power": 1.0,
        "accuracy_modifier": 0.0,
        "crit_modifier": 0.0,
        "effects": [],
        "description": "基础攻击动作，伤害稳定，没有额外消耗。",
    }


def starter_equipment() -> dict[str, Any]:
    return {
        "weapon": {
            "item_id": "worn_training_staff",
            "name": "旧练习木棍",
            "slot": "weapon",
            "stats": {"attack": 2},
            "description": "普通练习武器，只提供少量攻击力。",
        },
        "armor": {
            "item_id": "plain_cloth",
            "name": "粗布衣",
            "slot": "armor",
            "stats": {"defense": 1},
            "description": "普通衣物，防护有限。",
        },
        "accessory": None,
    }


def default_background(world_name: str) -> dict[str, Any]:
    if "doupo" in world_name:
        return {
            "origin": "乌坦城无名少年",
            "opening_scene": "清晨的乌坦城尚未完全醒来，你站在萧家练武场外，听见场内少年们运转斗气时压低的呼吸声。",
            "motivation": "你不甘心一辈子只在旁边看别人修炼，想真正踏入斗气之路。",
            "starting_conflict": "你没有丹药、没有正式师承，也没有足够的钱，连稳定使用练武场都需要争取。",
            "starting_hooks": ["萧家练武场", "乌坦城拍卖场", "薰儿的善意", "药老与异火的传闻"],
        }
    return {
        "origin": "无名旅人",
        "opening_scene": "你站在这个世界的边缘，身上只有最基础的装备和一点尚未验证的野心。",
        "motivation": "你想在这个世界获得立足之地，并找到属于自己的道路。",
        "starting_conflict": "你缺少资源、关系和可靠情报，任何成长都需要付出时间与代价。",
        "starting_hooks": ["观察周围", "寻找安全地点", "打听资源", "接触本地人物"],
    }


def default_player_state(world_name: str) -> dict[str, Any]:
    return {
        "meta": {
            "world": world_name,
            "current_time": "第一日 清晨",
            "current_location": "乌坦城萧家后山" if "doupo" in world_name else "未确定起点",
            "current_stage": "开局",
            "turn": 0,
        },
        "player": {
            "name": "旅人",
            "identity": "乌坦城无名少年" if "doupo" in world_name else "未定",
            "realm_or_level": "斗之气低段" if "doupo" in world_name else "凡人",
            "stats": default_stats(),
            "currencies": {"coins": 0},
            "attributes": {},
            "resources": {},
            "inventory": [],
            "equipment": starter_equipment(),
            "skills": [starter_skill()],
            "active_effects": [],
            "status_effects": [],
        },
        "background": default_background(world_name),
        "relationships": [],
        "active_quests": [],
        "world_events": [],
        "action_log": [],
    }


def migrate_player_state(state: dict[str, Any], world_name: str) -> dict[str, Any]:
    default = default_player_state(world_name)
    state.setdefault("meta", default["meta"])
    state.setdefault("background", default["background"])
    player = state.setdefault("player", {})
    player.setdefault("name", default["player"]["name"])
    player.setdefault("identity", default["player"]["identity"])
    player.setdefault("realm_or_level", default["player"]["realm_or_level"])
    player.setdefault("stats", default_stats())
    for key, value in default_stats().items():
        player["stats"].setdefault(key, value)
    player.setdefault("currencies", {"coins": 0})
    player.setdefault("inventory", [])
    if isinstance(player.get("equipment"), list):
        old_equipment = player.get("equipment", [])
        player["equipment"] = starter_equipment()
        player["legacy_equipment_notes"] = old_equipment
    player.setdefault("equipment", starter_equipment())
    player.setdefault("skills", [starter_skill()])
    player.setdefault("active_effects", [])
    player.setdefault("status_effects", [])
    player.setdefault("attributes", {})
    player.setdefault("resources", {})
    state.setdefault("relationships", [])
    state.setdefault("active_quests", [])
    state.setdefault("world_events", [])
    state.setdefault("action_log", [])
    return state


def load_manifest(path: Path, world: str) -> dict[str, Any]:
    manifest_path = path / "manifest.json"
    manifest = read_json(manifest_path, {})
    if not manifest:
        manifest = {
            "world": world,
            "created_at": now_iso(),
            "updated_at": now_iso(),
            "source_files": [],
            "chunk_count": 0,
            "fact_count": 0,
        }
    return manifest


def save_manifest(path: Path, manifest: dict[str, Any]) -> None:
    manifest["updated_at"] = now_iso()
    write_json(path / "manifest.json", manifest)
