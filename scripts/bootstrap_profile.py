#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from collections import Counter
from typing import Any

from common import load_manifest, save_manifest, sentence_split, world_dir, read_jsonl, write_json


GENRE_HINTS: dict[str, tuple[str, ...]] = {
    "xuanhuan": ("斗气", "灵力", "修炼", "境界", "功法", "丹药", "宗门", "血脉", "妖兽", "灵石"),
    "xianxia": ("练气", "筑基", "金丹", "元婴", "飞升", "法宝", "灵根", "洞府", "仙门", "天劫"),
    "wuxia": ("内力", "真气", "经脉", "门派", "武功", "江湖", "镖局", "盟主", "掌门", "轻功"),
    "scifi": ("星舰", "机甲", "殖民", "星球", "跃迁", "舰队", "人工智能", "基因", "能源", "宇宙"),
    "cyberpunk": ("义体", "芯片", "黑客", "网络", "赛博", "公司", "霓虹", "数据", "仿生", "植入体"),
    "fantasy": ("魔法", "骑士", "精灵", "矮人", "巨龙", "王国", "神殿", "法师", "魔兽", "圣剑"),
    "game": ("玩家", "系统", "副本", "等级", "经验值", "技能点", "公会", "装备", "任务", "面板"),
    "historical": ("朝廷", "皇帝", "王爷", "将军", "县令", "科举", "银票", "江南", "边关", "诏书"),
    "military": ("部队", "军团", "战舰", "战场", "指挥官", "火力", "补给", "阵地", "侦察", "炮火"),
    "urban": ("公司", "学校", "医院", "警察", "城市", "手机", "合同", "商业", "集团", "直播"),
    "mystery": ("污染", "封印", "诡异", "仪式", "禁忌", "调查", "教会", "怪物", "异常", "失控"),
    "apocalypse": ("末日", "丧尸", "避难所", "物资", "感染", "基地", "变异", "灾变", "幸存者", "尸潮"),
}

SCHEMA_TEMPLATES: dict[str, dict[str, Any]] = {
    "xuanhuan": {
        "power_axis": "境界/功法/资源/血脉/机缘",
        "core_actions": ["修炼", "突破", "探索秘境", "交易资源", "加入势力", "炼药或炼器"],
        "risk_axes": ["境界压制", "资源不足", "势力敌意", "机缘反噬"],
    },
    "xianxia": {
        "power_axis": "境界/灵根/功法/法宝/因果",
        "core_actions": ["闭关", "渡劫", "炼丹", "炼器", "宗门任务", "探索洞府"],
        "risk_axes": ["心魔", "天劫", "因果", "宗门规矩", "资源争夺"],
    },
    "wuxia": {
        "power_axis": "内力/招式/门派/名望/江湖关系",
        "core_actions": ["练功", "切磋", "押镖", "查案", "拜师", "闯荡江湖"],
        "risk_axes": ["伤势", "仇家", "门派规矩", "名声后果"],
    },
    "scifi": {
        "power_axis": "科技/舰队/权限/资源/阵营",
        "core_actions": ["调查星域", "升级装备", "谈判", "潜入", "舰队战", "科研"],
        "risk_axes": ["能源", "权限", "暴露", "阵营关系", "技术失控"],
    },
    "cyberpunk": {
        "power_axis": "义体/黑客能力/公司权限/现金/街头关系",
        "core_actions": ["入侵", "潜入", "改造义体", "街头交易", "公司谈判", "追踪数据"],
        "risk_axes": ["追踪", "过载", "公司报复", "身份暴露", "债务"],
    },
    "fantasy": {
        "power_axis": "魔力/职业/法术/神器/阵营声望",
        "core_actions": ["施法", "探索遗迹", "接取委托", "加入阵营", "锻造装备", "对抗魔物"],
        "risk_axes": ["魔力枯竭", "诅咒", "阵营敌意", "神明代价", "怪物威胁"],
    },
    "game": {
        "power_axis": "等级/技能/装备/副本进度/公会关系",
        "core_actions": ["刷怪", "下副本", "接任务", "强化装备", "组队", "交易"],
        "risk_axes": ["死亡惩罚", "冷却", "资源消耗", "队伍关系", "副本机制"],
    },
    "historical": {
        "power_axis": "身份/钱粮/人脉/权力/声望",
        "core_actions": ["查案", "经营", "结交", "赶考", "行军", "周旋朝堂"],
        "risk_axes": ["律法", "名声", "派系", "钱粮", "时间窗口"],
    },
    "military": {
        "power_axis": "兵力/补给/情报/装备/指挥权",
        "core_actions": ["侦察", "布防", "突击", "谈判", "补给", "指挥战斗"],
        "risk_axes": ["伤亡", "弹药", "士气", "暴露", "战略后果"],
    },
    "mystery": {
        "power_axis": "知识/污染/仪式/封印物/组织权限",
        "core_actions": ["调查", "封印", "仪式", "潜入", "求援", "隐藏污染"],
        "risk_axes": ["理智", "污染", "禁忌知识", "组织审查", "失控"],
    },
    "apocalypse": {
        "power_axis": "物资/据点/感染/战力/团队关系",
        "core_actions": ["搜集物资", "加固据点", "救援", "交易", "突围", "清理威胁"],
        "risk_axes": ["感染", "饥饿", "弹药", "噪音", "团队士气"],
    },
    "urban": {
        "power_axis": "身份/资金/人脉/技能/法律风险",
        "core_actions": ["调查", "谈判", "交易", "社交", "创业", "解决危机"],
        "risk_axes": ["法律", "声誉", "资金", "人情债", "时间压力"],
    },
}

COMMON_BAD_NAMES = {
    "他们", "我们", "你们", "自己", "这里", "那里", "这个", "那个", "什么", "只是", "已经",
    "不是", "没有", "忽然", "终于", "少年", "少女", "老人", "男子", "女子", "众人", "这个世界",
}
FACTION_SUFFIXES = ("宗", "门", "派", "族", "家族", "学院", "帝国", "皇室", "公会", "联盟", "佣兵团", "殿", "阁", "谷", "塔", "公司", "集团", "教会", "军团", "基地", "王国", "议会", "舰队", "帮", "会")
LOCATION_SUFFIXES = ("城", "镇", "村", "山", "谷", "林", "域", "国", "院", "塔", "沙漠", "山脉", "洞府", "遗迹", "空间", "界", "星", "星球", "基地", "港", "区", "王都", "要塞", "副本", "实验室", "空间站")
ITEM_SUFFIXES = ("丹", "药", "灵液", "卷轴", "令牌", "戒", "剑", "刀", "枪", "甲", "符", "法宝", "晶核", "魔核", "芯片", "药剂", "法杖", "圣剑", "义体", "模块", "装甲", "枪械", "遗物", "封印物")
TECHNIQUE_SUFFIXES = ("诀", "功", "掌", "拳", "剑法", "刀法", "身法", "秘法", "术", "阵", "仪式", "斗技", "技能", "法术", "魔法", "枪法", "战术", "算法", "协议")
REALM_SUFFIXES = ("境", "期", "阶", "级", "品", "星", "段", "重")


def usable_name(name: str, max_len: int = 10) -> bool:
    name = re.sub(r"\s+", "", name.strip(" “‘”《》、，。！？；：:.()[]【】"))
    if len(name) < 2 or len(name) > max_len:
        return False
    if name in COMMON_BAD_NAMES:
        return False
    if name.endswith(("宗掌", "门掌", "真人掌", "弟子擅长")):
        return False
    if any(mark in name for mark in ("的", "了", "着", "是", "在", "和", "与", "而", "就")):
        return False
    return re.fullmatch(r"[\u4e00-\u9fffA-Za-z0-9_-]+", name) is not None


def normalize_candidate(name: str) -> str:
    name = re.sub(r"\s+", "", name.strip(" “‘”《》、，。！？；：:.()[]【】"))
    splitters = (
        "分别是", "分为", "名为", "叫做", "掌控", "擅长", "修炼", "学习", "购买", "想买",
        "需要", "以及", "或者", "和", "与", "在", "向", "到", "从", "为", "拿",
    )
    for splitter in splitters:
        if splitter in name:
            name = name.split(splitter)[-1]
    name = re.sub(r"^[想可要能会将把拿控买找寻得有无]+", "", name)
    name = re.sub(r"[笑问说道喝]$", "", name)
    return name


def top_terms(counter: Counter[str], limit: int, min_count: int = 2) -> list[str]:
    rows = [name for name, count in counter.most_common(limit * 4) if count >= min_count and usable_name(name)]
    deduped: list[str] = []
    seen: set[str] = set()
    for name in rows:
        if name in seen:
            continue
        if any(name != other and name in other for other in seen):
            continue
        deduped.append(name)
        seen.add(name)
        if len(deduped) >= limit:
            break
    return deduped


def sample_chunks(chunks: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    if len(chunks) <= limit:
        return chunks
    head = chunks[: max(1, limit // 2)]
    stride = max(1, len(chunks) // max(1, limit - len(head)))
    tail = chunks[len(head) :: stride][: limit - len(head)]
    return head + tail


def infer_genre(text: str) -> tuple[str, dict[str, int]]:
    scores = {genre: sum(text.count(word) for word in hints) for genre, hints in GENRE_HINTS.items()}
    genre = max(scores, key=scores.get)
    if scores[genre] == 0:
        return "generic", scores
    return genre, scores


def count_suffix_terms(text: str, suffixes: tuple[str, ...], max_prefix: int = 8) -> Counter[str]:
    suffix_pattern = "|".join(re.escape(suffix) for suffix in sorted(suffixes, key=len, reverse=True))
    pattern = rf"([\u4e00-\u9fff]{{2,{max_prefix}}}(?:{suffix_pattern}))"
    counter: Counter[str] = Counter()
    for match in re.finditer(pattern, text):
        name = normalize_candidate(match.group(1))
        if name.endswith(("掌门", "宗主", "族长", "院长", "会长")):
            continue
        counter[name] += 1
    return counter


def count_dialogue_names(text: str) -> Counter[str]:
    patterns = [
        r"([\u4e00-\u9fff]{2,4})(?:低声|淡淡|沉声|冷笑|笑着|笑道|喝|问|说|道|叹道|怒道)",
        r"(?:“[^”]{1,40}”|\"[^\"]{1,40}\")\s*([\u4e00-\u9fff]{2,4})(?:道|说|问|喝道|笑道)",
    ]
    counter: Counter[str] = Counter()
    for pattern in patterns:
        counter.update(normalize_candidate(match.group(1)) for match in re.finditer(pattern, text))
    return counter


def count_realm_terms(text: str) -> Counter[str]:
    counter: Counter[str] = Counter()
    suffix_pattern = "|".join(re.escape(suffix) for suffix in REALM_SUFFIXES)
    for match in re.finditer(rf"([\u4e00-\u9fff]{{1,6}}(?:{suffix_pattern}))", text):
        name = match.group(1)
        name = normalize_candidate(name)
        window = text[max(0, match.start() - 24) : min(len(text), match.end() + 24)]
        if any(word in window for word in ("修炼", "突破", "境界", "等级", "实力", "晋升", "瓶颈", "功法", "力量")):
            counter[name] += 1
    return counter


def build_profile(world: str, sample_limit: int) -> dict[str, Any]:
    wdir = world_dir(world)
    chunks = read_jsonl(wdir / "chunks.jsonl")
    if not chunks:
        raise SystemExit("No chunks found. Run ingest.py first, then bootstrap_profile.py.")

    sampled = sample_chunks(chunks, sample_limit)
    text = "\n".join(chunk.get("text", "") for chunk in sampled)
    genre, genre_scores = infer_genre(text)
    sentences = sentence_split(text)

    min_count = 1 if len(text) < 10000 or len(sampled) < 20 else 2
    factions = count_suffix_terms(text, FACTION_SUFFIXES)
    locations = count_suffix_terms(text, LOCATION_SUFFIXES)
    items = count_suffix_terms(text, ITEM_SUFFIXES)
    techniques = count_suffix_terms(text, TECHNIQUE_SUFFIXES)
    realms = count_realm_terms(text)
    npcs = count_dialogue_names(text)

    profile = {
        "profile": "auto",
        "genre": genre,
        "schema": SCHEMA_TEMPLATES.get(genre, {
            "power_axis": "身份/资源/能力/关系/风险",
            "core_actions": ["调查", "探索", "交易", "社交", "训练", "解决危机"],
            "risk_axes": ["时间", "资源", "敌意", "暴露", "失败后果"],
        }),
        "realm_terms": top_terms(realms, 40, min_count=min_count),
        "known_npcs": top_terms(npcs, 80, min_count=min_count),
        "known_factions": top_terms(factions, 80, min_count=min_count),
        "known_locations": top_terms(locations, 80, min_count=min_count),
        "known_items": top_terms(items, 80, min_count=min_count),
        "known_techniques": top_terms(techniques, 80, min_count=min_count),
        "faction_suffixes": list(FACTION_SUFFIXES),
        "location_suffixes": list(LOCATION_SUFFIXES),
        "bootstrap": {
            "sampled_chunks": len(sampled),
            "sampled_chars": len(text),
            "genre_scores": genre_scores,
            "sentence_count": len(sentences),
            "term_min_count": min_count,
        },
    }
    write_json(wdir / "world_profile.json", profile)
    manifest = load_manifest(wdir, world)
    manifest["profile"] = "auto"
    manifest["genre"] = genre
    manifest["world_profile"] = "world_profile.json"
    save_manifest(wdir, manifest)
    return profile


def main() -> None:
    parser = argparse.ArgumentParser(description="Infer a reusable world profile from sampled novel chunks.")
    parser.add_argument("--world", required=True)
    parser.add_argument("--sample-chunks", type=int, default=80)
    args = parser.parse_args()
    profile = build_profile(args.world, args.sample_chunks)
    print(
        "Built world_profile.json "
        f"genre={profile['genre']} "
        f"realms={len(profile['realm_terms'])} "
        f"npcs={len(profile['known_npcs'])} "
        f"factions={len(profile['known_factions'])} "
        f"locations={len(profile['known_locations'])}"
    )


if __name__ == "__main__":
    main()
