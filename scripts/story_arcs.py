#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import re
from collections import Counter, defaultdict
from typing import Any

from common import load_manifest, read_json, read_jsonl, save_manifest, world_dir, write_json


ARC_WORDS = (
    "三年之约",
    "退婚",
    "复仇",
    "救援",
    "战争",
    "大会",
    "试炼",
    "学院",
    "招生",
    "追杀",
    "封锁",
    "争夺",
    "结盟",
    "回归",
    "重建",
    "寻找",
    "追寻",
    "收服",
    "传承",
    "秘境",
    "遗迹",
)

MISSION_WORDS = (
    "赚钱",
    "筹钱",
    "金币",
    "资源",
    "材料",
    "药材",
    "魔核",
    "修炼",
    "突破",
    "历练",
    "情报",
    "打听",
    "调查",
    "委托",
    "跑腿",
    "护送",
    "狩猎",
    "炼药",
    "交易",
    "拍卖",
    "人情",
    "信任",
)

GENERIC_NAMES = {
    "继续",
    "任务",
    "目标",
    "寻找",
    "发现",
    "获得",
    "开始",
    "大战",
    "战争",
    "追杀",
    "拍卖",
    "交易",
    "炼药",
    "炼制丹药",
    "丹药",
    "修炼",
    "突破",
    "资源",
    "试炼",
    "历练",
    "关系",
    "人情",
    "情报",
    "线索",
    "陨落",
    "大会",
    "争夺",
    "调查",
    "回归",
    "招生",
    "高阶",
    "低阶",
    "不会",
    "成功",
    "多次",
    "结盟",
    "封锁",
    "这些药",
    "这",
    "那",
}

NOISY_TERM_PARTS = (
    "玩家",
    "通过",
    "高风险",
    "继续",
    "可以",
    "需要",
    "这种",
    "那个",
    "什么",
    "如果",
    "因为",
    "但是",
    "微",
    "手掌",
    "脸色",
    "脸庞",
    "心中",
    "心头",
    "目光",
    "高级",
    "低级",
    "中级",
)

ARC_LABELS = {
    "revenge_or_vow": "赴约复仇线",
    "resource_pursuit": "资源筹措线",
    "training_growth": "修炼成长线",
    "faction_conflict": "势力冲突线",
    "exploration_secret": "探索线",
    "rescue_or_protection": "救援保护线",
    "open_world_loop": "长期行动线",
}

ARC_TYPE_WORDS: dict[str, tuple[str, ...]] = {
    "revenge_or_vow": ("三年之约", "退婚", "复仇", "约定", "雪耻"),
    "resource_pursuit": ("寻药", "药材", "魔核", "资源", "金币", "筹钱", "拍卖", "交易"),
    "training_growth": ("修炼", "突破", "试炼", "历练", "学院", "测试", "大会"),
    "faction_conflict": ("宗门", "家族", "势力", "战争", "结盟", "封锁", "追杀"),
    "exploration_secret": ("残图", "线索", "遗迹", "秘境", "地图", "调查", "寻找", "传承"),
    "rescue_or_protection": ("救援", "护送", "保护", "解救", "危机"),
}


def arc_id(name: str, summary: str = "") -> str:
    digest = hashlib.sha1(f"{name}|{summary[:80]}".encode("utf-8")).hexdigest()[:10]
    return f"arc_{digest}"


def clean_text(text: str, limit: int = 260) -> str:
    text = re.sub(r"\s+", " ", str(text or "")).strip()
    return text[:limit]


def is_noise_sentence(text: str) -> bool:
    text = clean_text(text, 160)
    if not text:
        return True
    if len(text) > 130 and any(word in text for word in ("目光", "脸色", "手掌", "心中", "微微", "笑道")):
        return True
    return any(part in text for part in ("['", "']", "{", "}", "source_quality"))


def is_generic_name(name: str) -> bool:
    name = name.strip(" 「」《》")
    if name.startswith("萧炎") and name != "萧炎":
        return True
    return not name or name in GENERIC_NAMES or len(name) < 2 or len(name) > 18 or any(part in name for part in NOISY_TERM_PARTS)


def entity_text(row: dict[str, Any]) -> str:
    parts = [
        str(row.get("name") or row.get("title") or ""),
        str(row.get("summary") or ""),
        str(row.get("claim") or ""),
        str(row.get("aliases") or ""),
    ]
    for claim in row.get("claims", [])[:4] if isinstance(row.get("claims"), list) else []:
        if isinstance(claim, dict):
            parts.append(str(claim.get("claim") or ""))
    return " ".join(part for part in parts if part)


def split_claims(text: str, words: tuple[str, ...], fallback: str, limit: int = 3) -> list[str]:
    pieces = [part.strip() for part in re.split(r"[。！？；;，,]\s*", text) if part.strip()]
    hits = [clean_text(piece, 90) for piece in pieces if any(word in piece for word in words) and not is_noise_sentence(piece)]
    output = hits[:limit] or ([fallback] if fallback else [])
    deduped: list[str] = []
    for item in output:
        if item and item not in deduped:
            deduped.append(item)
    return deduped


def confidence(row: dict[str, Any], default: float = 0.68) -> float:
    return round(float(row.get("quality") or row.get("confidence") or default), 2)


def source_rank(row: dict[str, Any]) -> int:
    fact_source = str(row.get("fact_source") or row.get("source") or "")
    source = str(row.get("source") or row.get("_source") or "")
    ftype = str(row.get("type") or "")
    if fact_source == "llm_assisted":
        return 5
    if source.startswith("curated:") and ftype in {"story_arc", "recurring_mission"}:
        return 3
    if source.startswith("facts:") and ftype in {"story_arc", "recurring_mission"}:
        return 2
    if source == "timeline_event":
        return 2
    return 1


def trusted_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    trusted = [row for row in rows if source_rank(row) >= 5 and not is_noise_sentence(row.get("summary", ""))]
    return trusted or [row for row in rows if source_rank(row) >= 3 and not is_noise_sentence(row.get("summary", ""))]


def trusted_text(rows: list[dict[str, Any]]) -> str:
    chosen = trusted_rows(rows)
    return " ".join(str(row.get("summary") or row.get("text") or "") for row in chosen) or " ".join(
        str(row.get("summary") or row.get("text") or "") for row in rows[:3]
    )


def read_sources(world: str) -> list[dict[str, Any]]:
    wdir = world_dir(world)
    sources: list[dict[str, Any]] = []
    for source_name, filename, key in [
        ("adventure_hook", "adventure_hooks.json", "hooks"),
        ("timeline_event", "timeline.json", "events"),
    ]:
        for row in read_json(wdir / filename, {}).get(key, []):
            if isinstance(row, dict):
                sources.append({**row, "_source": source_name})
    for row in read_jsonl(wdir / "curated_facts.jsonl"):
        if row.get("type") in {"story_arc", "recurring_mission", "playable_hook", "event"}:
            sources.append({**row, "_source": f"curated:{row.get('type')}"})
    for row in read_jsonl(wdir / "facts.jsonl"):
        if row.get("type") in {"story_arc", "recurring_mission"}:
            sources.append({**row, "_source": f"facts:{row.get('type')}"})
    return sources


def read_named_terms(world: str) -> list[str]:
    wdir = world_dir(world)
    terms: list[str] = []
    for filename, key in [
        ("items.json", "items"),
        ("techniques.json", "techniques"),
        ("locations.json", "locations"),
        ("factions.json", "factions"),
    ]:
        rows = read_json(wdir / filename, {}).get(key, [])
        for row in rows:
            if not isinstance(row, dict):
                continue
            name = str(row.get("name") or "").strip(" 「」《》")
            if is_generic_name(name):
                continue
            terms.append(name)
    return sorted(set(terms), key=lambda item: (len(item), item), reverse=True)


def classify_arc(text: str) -> str:
    for kind, words in ARC_TYPE_WORDS.items():
        if any(word in text for word in words):
            return kind
    return "open_world_loop"


def key_terms(text: str, named_terms: list[str] | None = None) -> list[str]:
    terms: list[str] = []
    for term in named_terms or []:
        if term in text and term not in terms:
            terms.append(term)
        if len(terms) >= 5:
            break
    for word in (*ARC_WORDS, *MISSION_WORDS):
        if word in text and word not in terms and not is_generic_name(word):
            terms.append(word)
    quoted = re.findall(r"[「《“]?([\u4e00-\u9fff]{2,10}(?:之约|大会|试炼|拍卖|追杀|退婚|战争|遗迹|秘境|残图|异火|学院|家族|宗门))[」》”]?", text)
    for term in quoted:
        if is_generic_name(term) or len(term) > 8 or any(noise in term for noise in ("和", "但", "可以", "通过", "高风险", "玩家")):
            continue
        if term not in terms:
            terms.append(term)
    return terms[:8]


def canonical_name(row: dict[str, Any], text: str, idx: int, named_terms: list[str]) -> str:
    name = str(row.get("name") or row.get("title") or "").strip(" 「」《》")
    if not is_generic_name(name):
        return name
    terms = key_terms(text, named_terms)
    arc_type = classify_arc(text)
    specific = next((term for term in terms if not is_generic_name(term)), "")
    if specific:
        return f"{specific}{ARC_LABELS.get(arc_type, '长期行动线')}"
    if "炼药" in text or "药材" in text or "丹药" in text:
        return "炼药资源筹措线"
    if "拍卖" in text or "交易" in text or "金币" in text:
        return "拍卖交易筹资线"
    if "修炼" in text or "突破" in text:
        return "修炼突破准备线"
    if "情报" in text or "调查" in text or "线索" in text:
        return "情报调查线"
    return f"长期任务线{idx + 1}"


def is_arc_candidate(row: dict[str, Any], text: str, named_terms: list[str]) -> bool:
    ftype = str(row.get("type") or "")
    if ftype in {"story_arc", "recurring_mission"}:
        return any(term in text for term in named_terms[:160]) or sum(1 for word in (*ARC_WORDS, *MISSION_WORDS) if word in text) >= 2
    return any(word in text for word in ARC_WORDS if not is_generic_name(word)) or sum(1 for word in MISSION_WORDS if word in text) >= 3


def synthesize_summary(name: str, arc_type: str, rows: list[dict[str, Any]], text: str) -> str:
    trusted = trusted_rows(rows)
    if trusted:
        snippets = []
        for row in trusted[:3]:
            snippet = clean_text(row.get("summary") or row.get("text") or "", 140)
            if snippet and snippet not in snippets and not is_noise_sentence(snippet):
                snippets.append(snippet)
        if snippets:
            return clean_text(" / ".join(snippets), 320)
    snippets = []
    for row in rows:
        snippet = clean_text(row.get("summary") or row.get("text") or "", 120)
        if snippet and not is_noise_sentence(snippet) and not any(snippet == old for old in snippets):
            snippets.append(snippet)
        if len(snippets) >= 2:
            break
    label = ARC_LABELS.get(arc_type, "长期行动线")
    evidence_hint = f" 代表线索：{' / '.join(snippets)}" if snippets else ""
    return clean_text(f"围绕「{name}」展开的{label}，可转成阶段式长期任务。{evidence_hint}", 300)


def merge_candidates(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in candidates:
        key = str(item["name"]).lower()
        grouped[key].append(item)

    arcs: list[dict[str, Any]] = []
    for rows in grouped.values():
        rows.sort(key=lambda row: (source_rank(row), row["score"], row["confidence"]), reverse=True)
        primary = rows[0]
        evidence = []
        for row in rows:
            evidence.extend(row.get("evidence_chunk_ids", []))
        evidence = sorted({str(item) for item in evidence if item})
        mentions = sum(min(int(row.get("mentions") or 1), 12 if source_rank(row) >= 4 else 4) for row in rows)
        canon_strength = "high" if source_rank(primary) >= 5 or mentions >= 4 or len(evidence) >= 4 else "medium" if mentions >= 2 or len(evidence) >= 2 else "low"
        text = " ".join(row["text"] for row in rows)
        focused_text = trusted_text(rows) or text
        arc_type = classify_arc(text)
        summary = synthesize_summary(primary["name"], arc_type, rows, text)
        arcs.append(
            {
                "arc_id": arc_id(primary["name"], summary),
                "name": primary["name"],
                "type": arc_type,
                "summary": summary,
                "why_it_matters": split_claims(
                    focused_text,
                    ("复仇", "资源", "突破", "势力", "关系", "秘密", "威胁", "机会", "约定", "目标"),
                    "这是原著中反复出现或能持续推动玩家行动的目标线。",
                    2,
                ),
                "entry_conditions": split_claims(
                    focused_text,
                    ("需要", "必须", "入口", "线索", "资格", "金币", "关系", "情报", "地点"),
                    "玩家需要先获得线索、地点入口、关系许可或基础资源。",
                    3,
                ),
                "progression_loops": split_claims(
                    focused_text,
                    MISSION_WORDS,
                    "通过打听情报、筹措资源、完成小任务、训练或建立关系来推进。",
                    4,
                ),
                "risks": split_claims(
                    focused_text,
                    ("追杀", "失败", "反噬", "竞争", "封锁", "敌意", "暴露", "代价", "危险"),
                    "推进过急会带来竞争者、敌意、资源损耗或地点风险。",
                    3,
                ),
                "rewards": split_claims(
                    focused_text,
                    ("获得", "解锁", "金币", "资源", "情报", "关系", "声望", "突破", "进入"),
                    "成功推进可获得资源、关系、情报、地点入口或成长机会。",
                    3,
                ),
                "stages": build_stages(arc_type),
                "recurrence": "major_arc" if any(word in text for word in ARC_WORDS) else "repeatable_loop",
                "key_terms": sorted({term for row in rows for term in row.get("key_terms", [])})[:10],
                "source_rows": sorted({row["source"] for row in rows}),
                "source_priority": source_rank(primary),
                "evidence_chunk_ids": evidence[:20],
                "mentions": mentions,
                "canon_strength": canon_strength,
                "confidence": round(max(row["confidence"] for row in rows), 2),
            }
        )
    arcs.sort(
        key=lambda row: (
            row.get("source_priority", 0),
            {"high": 3, "medium": 2, "low": 1}[row["canon_strength"]],
            row["mentions"],
            row["confidence"],
        ),
        reverse=True,
    )
    return arcs[:40]


def build_stages(arc_type: str) -> list[dict[str, Any]]:
    templates = {
        "resource_pursuit": [
            ("discover_need", "确认需要什么资源、价格或替代路线"),
            ("earn_or_trade", "通过低风险委托、交易、跑腿或狩猎筹措筹码"),
            ("secure_source", "确认可靠来源并防止赝品、截胡或涨价"),
            ("convert_reward", "把资源转化为修炼、装备、关系或下一条线索"),
        ],
        "training_growth": [
            ("diagnose_limit", "确认当前瓶颈、能力边界和失败代价"),
            ("prepare_safely", "准备资源、指导、安全地点或恢复手段"),
            ("attempt_trial", "先做低风险训练或试炼验证"),
            ("advance_stage", "满足条件后推进突破、晋升或能力成长"),
        ],
        "faction_conflict": [
            ("identify_sides", "确认相关势力、联系人和敌意来源"),
            ("earn_leverage", "用情报、资源、人情或行动价值换取立场"),
            ("manage_escalation", "避免过早激化到玩家无法承受的冲突"),
            ("resolve_or_shift", "达成合作、撤退、反制或转入更大事件"),
        ],
        "exploration_secret": [
            ("find_clue", "取得可靠线索、地图、向导或入口条件"),
            ("prepare_route", "准备补给、撤退路线和最低自保手段"),
            ("scout_edge", "先侦察外围风险，不贸然深入核心"),
            ("claim_discovery", "获得资源、秘密、地点入口或后续线索"),
        ],
        "rescue_or_protection": [
            ("confirm_target", "确认需要保护或救援的对象与威胁来源"),
            ("choose_approach", "选择谈判、潜入、护送、引开或正面对抗"),
            ("pay_cost", "承担时间、资源、关系或安全代价"),
            ("settle_consequence", "结算人情、敌意、伤势和后续牵连"),
        ],
        "revenge_or_vow": [
            ("name_stake", "确认约定、羞辱、仇怨或长期目标的来源"),
            ("grow_power", "围绕资源、训练、关系和情报积累胜算"),
            ("face_pressure", "处理竞争者、势力阻挠、时间窗口和名声压力"),
            ("attempt_payoff", "在满足条件后挑战、赴约、和解或改写局势"),
        ],
    }
    stages = templates.get(arc_type, [
        ("identify_goal", "确认目标、来源、地点和相关人物"),
        ("prepare", "准备资源、关系、情报和风险预案"),
        ("act", "选择可承受的行动方式推进"),
        ("settle", "结算奖励、代价、关系和后续事件"),
    ])
    return [{"stage_id": sid, "objective": text, "done_by_default": False} for sid, text in stages]


def build_story_arcs(world: str) -> dict[str, Any]:
    sources = read_sources(world)
    named_terms = read_named_terms(world)
    candidates: list[dict[str, Any]] = []
    for idx, row in enumerate(sources):
        text = entity_text(row)
        if not is_arc_candidate(row, text, named_terms):
            continue
        name = canonical_name(row, text, idx, named_terms)
        terms = key_terms(text, named_terms)
        if is_generic_name(name):
            continue
        evidence = row.get("evidence_chunk_ids") or []
        if isinstance(evidence, str):
            evidence = [evidence]
        mentions = int(row.get("mentions") or max(1, len(evidence)))
        fact_source = str(row.get("source") or "")
        source_label = str(row.get("_source") or row.get("source") or "unknown")
        score = float(row.get("score") or 0.0) + min(mentions, 20) * 2.0 + len(terms)
        if str(row.get("type")) in {"story_arc", "recurring_mission"}:
            score += 20.0
        if fact_source == "llm_assisted":
            score += 1000.0
        candidates.append(
            {
                "name": name,
                "summary": clean_text(row.get("summary") or row.get("claim") or text, 280),
                "text": text,
                "source": source_label,
                "fact_source": fact_source,
                "type": str(row.get("type") or ""),
                "evidence_chunk_ids": [str(item) for item in evidence if item],
                "mentions": mentions,
                "key_terms": terms,
                "confidence": confidence(row),
                "score": score,
            }
        )

    arcs = merge_candidates(candidates)
    type_counts = Counter(arc["type"] for arc in arcs)
    output = {
        "world": world,
        "policy": (
            "Story arcs are canon-derived long-running goals and repeatable mission loops. "
            "They may guide quests and world events, but must not override retrieved canon, canon patches, or player state."
        ),
        "arcs": arcs,
        "stats": {
            "source_rows": len(sources),
            "candidate_rows": len(candidates),
            "arc_count": len(arcs),
            "named_terms": len(named_terms),
            "type_counts": dict(sorted(type_counts.items())),
        },
    }
    wdir = world_dir(world)
    write_json(wdir / "story_arcs.json", output)
    manifest = load_manifest(wdir, world)
    manifest["story_arcs"] = "story_arcs.json"
    save_manifest(wdir, manifest)
    print(f"Built story_arcs.json arcs={len(arcs)} candidates={len(candidates)}")
    return output


def load_story_arcs(world: str) -> dict[str, Any]:
    data = read_json(world_dir(world) / "story_arcs.json", {})
    return data if data else build_story_arcs(world)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build canon-derived long-running story arcs and recurring mission loops.")
    parser.add_argument("--world", required=True)
    parser.add_argument("--rebuild", action="store_true")
    args = parser.parse_args()
    data = build_story_arcs(args.world) if args.rebuild else load_story_arcs(args.world)
    print(f"world={data.get('world')} arcs={len(data.get('arcs', []))}")


if __name__ == "__main__":
    main()
