#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from typing import Any

from common import load_manifest, read_json, save_manifest, world_dir, write_json
from gameplay_profile import load_gameplay_profile
from runtime_effects import apply_effects


EVENT_KEYWORDS = {
    "auction": ("拍卖", "交易", "市场", "黑市", "商会"),
    "faction": ("势力", "宗门", "家族", "公司", "军团", "教会", "公会"),
    "exploration": ("秘境", "遗迹", "洞府", "星域", "副本", "禁地", "探索"),
    "threat": ("追杀", "灾变", "尸潮", "战争", "封锁", "污染", "失控"),
    "training": ("修炼", "训练", "突破", "学习", "试炼", "考核"),
}
BAD_EFFECT_TARGETS = {"不会", "没有理会", "对方", "当前", "这种等级"}
BAD_EFFECT_ITEMS = {"炼药", "炼丹", "卷轴", "丹药", "药材", "听得药", "这些药"}


def event_id(name: str) -> str:
    return "event_" + hashlib.sha1(name.encode("utf-8")).hexdigest()[:10]


def classify_event(name: str, summary: str) -> str:
    title = name.strip(" 「」")
    for kind in ("threat", "auction", "faction", "exploration", "training"):
        if any(word in title for word in EVENT_KEYWORDS[kind]):
            return kind
    text = f"{title} {summary[:220]}"
    for kind, words in EVENT_KEYWORDS.items():
        if any(word in text for word in words):
            return kind
    return "opportunity"


def event_from_hook(
    hook: dict[str, Any],
    index: int,
    gameplay_profile: dict[str, Any],
    event_chain: dict[str, Any] | None = None,
    start_turn: int = 1,
) -> dict[str, Any]:
    name = str(hook.get("name") or f"世界事件{index + 1}")
    summary = str(hook.get("summary") or hook.get("claim") or "")
    kind = classify_event(name, summary)
    start = start_turn + index * 2
    expires = start + (4 if kind in {"auction", "threat"} else 6)
    signal = {}
    if event_chain:
        signal = next((node for node in event_chain.get("nodes", []) if node.get("node_id") == "signal"), {})
    return {
        "event_id": event_id(name),
        "title": name,
        "summary": summary,
        "type": kind,
        "status": "scheduled" if index > 0 or start_turn > 1 else "active",
        "visibility": "known",
        "starts_at_turn": start,
        "expires_at_turn": expires,
        "related_locations": [],
        "related_npcs": [],
        "related_factions": [],
        "progress": 0,
        "if_ignored": signal.get("if_ignored") or ignored_consequences(kind),
        "if_intervened": signal.get("if_player_intervenes") or intervened_outcomes(kind),
        "effects": default_effects(kind, name, summary, gameplay_profile),
        "triggers": default_triggers(kind, name, summary, gameplay_profile),
        "source": str(hook.get("_source_json") or "adventure_hooks.json"),
        "event_chain_id": event_chain.get("chain_id") if event_chain else "",
    }


def ignored_consequences(kind: str) -> list[str]:
    return {
        "auction": ["关键资源被其他势力买走", "价格上涨或交易资格降低"],
        "faction": ["目标势力对玩家关注度下降", "竞争者获得先机"],
        "exploration": ["入口线索过期", "其他探索者提前进入并改变现场"],
        "threat": ["威胁扩大并影响当前地区", "相关 NPC 或势力承受损失"],
        "training": ["试炼窗口关闭", "玩家错过低风险成长机会"],
    }.get(kind, ["机会窗口关闭", "世界局势向不利方向推进"])


def intervened_outcomes(kind: str) -> list[str]:
    return {
        "auction": ["获得交易资格或折扣", "触发资源收集任务"],
        "faction": ["建立关系入口", "获得势力任务或庇护条件"],
        "exploration": ["获得地点入口", "发现资源、敌人或新路线"],
        "threat": ["降低地区风险", "获得声望或人情"],
        "training": ["获得历练或能力指导", "解锁下一阶段目标"],
    }.get(kind, ["获得情报、关系或资源入口"])


def mentioned_canon_item(text: str, gameplay_profile: dict[str, Any]) -> str | None:
    entities = gameplay_profile.get("canon_entities", {})
    for key in ("market_items", "items"):
        for item in entities.get(key, []):
            item_name = str(item)
            if item_name and item_name in text:
                return item_name
    return None


def replace_item_mentions(value: Any, old: str, new: str) -> Any:
    if isinstance(value, str):
        return value.replace(old, new)
    if isinstance(value, list):
        return [replace_item_mentions(item, old, new) for item in value]
    if isinstance(value, dict):
        return {key: replace_item_mentions(child, old, new) for key, child in value.items()}
    return value


def sanitize_effects(effects: dict[str, list[dict[str, Any]]], replacement_item: str | None = None) -> dict[str, list[dict[str, Any]]]:
    sanitized: dict[str, list[dict[str, Any]]] = {}
    for bucket, rows in effects.items():
        kept: list[dict[str, Any]] = []
        for effect in rows:
            if not isinstance(effect, dict):
                continue
            copied = dict(effect)
            target = str(copied.get("target", ""))
            if target in BAD_EFFECT_TARGETS:
                continue
            item = str(copied.get("item", ""))
            if item in BAD_EFFECT_ITEMS:
                if replacement_item and replacement_item not in BAD_EFFECT_ITEMS:
                    copied["item"] = replacement_item
                else:
                    continue
            kept.append(copied)
        sanitized[bucket] = kept
    return sanitized


def default_effects(kind: str, name: str, summary: str, gameplay_profile: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    templates = gameplay_profile.get("events", {}).get("default_effects", {})
    if isinstance(templates, dict) and isinstance(templates.get(kind), dict):
        effects = json.loads(json.dumps(templates[kind], ensure_ascii=False))
        mentioned = mentioned_canon_item(f"{name} {summary}", gameplay_profile)
        first_item = next((effect.get("item") for rows in effects.values() for effect in rows if isinstance(effect, dict) and effect.get("item")), None)
        if mentioned and first_item and mentioned != first_item:
            effects = replace_item_mentions(effects, str(first_item), mentioned)
        return sanitize_effects(effects, mentioned)
    return {
        "ignored": [{"type": "state", "key": f"ignored_{event_id(name)}", "value": True}],
        "intervened": [{"type": "state", "key": f"intervened_{event_id(name)}", "value": True}],
    }


def default_triggers(kind: str, name: str, summary: str, gameplay_profile: dict[str, Any]) -> list[dict[str, Any]]:
    templates = gameplay_profile.get("events", {}).get("default_triggers", {})
    triggers = templates.get(kind, []) if isinstance(templates, dict) else []
    normalized: list[dict[str, Any]] = []
    mentioned = mentioned_canon_item(f"{name} {summary}", gameplay_profile)
    fallback_item = next(iter(gameplay_profile.get("canon_entities", {}).get("market_items", [])), None)
    for trigger in triggers:
        if not isinstance(trigger, dict):
            continue
        copied = json.loads(json.dumps(trigger, ensure_ascii=False))
        if mentioned and fallback_item and mentioned != fallback_item:
            copied = replace_item_mentions(copied, str(fallback_item), mentioned)
        event_template = copied.get("create_event")
        if isinstance(event_template, dict) and not event_template.get("title"):
            suffix = str(event_template.pop("title_suffix", "后续"))
            event_template["title"] = f"{name}{suffix}"
        normalized.append(copied)
    return normalized


def instantiate_trigger_event(parent: dict[str, Any], trigger: dict[str, Any], current_turn: int) -> dict[str, Any] | None:
    template = trigger.get("create_event")
    if not isinstance(template, dict):
        return None
    title = str(template.get("title", f"{parent.get('title')}后续"))
    starts = current_turn + int(template.get("starts_after", 1))
    duration = int(template.get("duration", 5))
    return {
        "event_id": event_id(f"{parent.get('event_id')}:{title}"),
        "title": title,
        "summary": template.get("summary", ""),
        "type": template.get("type", "opportunity"),
        "status": "scheduled",
        "visibility": "known",
        "starts_at_turn": starts,
        "expires_at_turn": starts + duration,
        "related_locations": template.get("related_locations", []),
        "related_npcs": template.get("related_npcs", []),
        "related_factions": template.get("related_factions", []),
        "progress": 0,
        "if_ignored": template.get("if_ignored", ["后续机会窗口关闭"]),
        "if_intervened": template.get("if_intervened", ["获得后续收益"]),
        "effects": template.get("effects", {"ignored": [], "intervened": []}),
        "triggers": template.get("triggers", []),
        "source": f"trigger:{parent.get('event_id')}",
    }


def short_text(value: Any, limit: int = 90) -> str:
    text = str(value or "").replace("\n", " ").strip()
    if len(text) <= limit:
        return text
    return text[:limit].rstrip("，。；,; ") + "..."


def clean_event_summary(value: Any) -> str:
    text = str(value or "").replace("\n", " ").strip()
    if not text:
        return ""
    if "玩家" in text and len(text) <= 180:
        return text
    if text.startswith(("，", "。", "；", "：", "“", "”", "\"", "'")):
        return ""
    if len(text) > 160 and any(name in text for name in ("萧炎", "药老", "薰儿", "雅妃")):
        return ""
    if len(text) > 240:
        return ""
    return short_text(text, 96)


def event_source_line(event: dict[str, Any]) -> str:
    title = str(event.get("title") or "未命名事件")
    summary = clean_event_summary(event.get("summary"))
    kind = str(event.get("type") or "opportunity")
    location = "、".join(str(item) for item in event.get("related_locations", [])[:2] if item)
    npc = "、".join(str(item) for item in event.get("related_npcs", [])[:2] if item)
    faction = "、".join(str(item) for item in event.get("related_factions", [])[:2] if item)
    anchors = "；".join(item for item in (location, npc, faction) if item)
    if summary:
        return f"「{title}」开始浮出水面：{summary}"
    if kind == "auction":
        return f"「{title}」的消息从交易场和商队口中传开，可能牵涉资源、资格或价格窗口。"
    if kind == "faction":
        return f"「{title}」背后有势力动作，{anchors or '当地人只敢含糊提起相关人物和关系'}。"
    if kind == "threat":
        return f"「{title}」带来明显压力，附近人开始回避相关路线和人物。"
    if kind == "training":
        return f"「{title}」像一次短暂的成长窗口，错过后未必还能用同样代价进入。"
    if anchors:
        return f"「{title}」与 {anchors} 有关，线索还不完整。"
    return f"「{title}」只是刚传出的机会，来源和风险都还需要核实。"


def event_start_message(event: dict[str, Any]) -> str:
    return f"世界事件出现：{event_source_line(event)}"


def event_intervened_message(event: dict[str, Any]) -> str:
    outcomes = "；".join(str(item) for item in event.get("if_intervened", [])[:2] if item)
    suffix = f" 后续可能：{outcomes}。" if outcomes else ""
    return f"你介入了「{event.get('title')}」，先把它从传闻推进成可操作线索。{suffix}"


def event_expired_message(event: dict[str, Any], consequences: list[Any]) -> str:
    text = "；".join(str(item) for item in consequences[:2] if item)
    suffix = f" 结果：{text}。" if text else ""
    return f"世界事件错过：「{event.get('title')}」的窗口关闭。{suffix}"


def event_created_message(created: dict[str, Any], parent: dict[str, Any]) -> str:
    parent_title = str(parent.get("title") or "前一事件")
    return f"后续事件出现：因为「{parent_title}」的推进，{event_source_line(created)}"


def build_world_events(world: str, start_turn: int = 1) -> dict[str, Any]:
    wdir = world_dir(world)
    hooks = read_json(wdir / "adventure_hooks.json", {}).get("hooks", [])
    story_arcs = read_json(wdir / "story_arcs.json", {}).get("arcs", [])
    gameplay_profile = load_gameplay_profile(world)
    chains = read_json(wdir / "event_chains.json", {}).get("chains", [])
    chain_by_name = {chain.get("name"): chain for chain in chains if chain.get("name")}
    def arc_summary(arc: dict[str, Any]) -> str:
        summary = short_text(arc.get("summary"), 180)
        extras: list[str] = []
        for item in [*arc.get("why_it_matters", [])[:2], *arc.get("progression_loops", [])[:2]]:
            text = short_text(item, 90)
            if not text or text in summary or "这是原著中反复出现" in text:
                continue
            if text not in extras:
                extras.append(text)
        return "；".join([summary, *extras[:2]]) if extras else summary

    arc_hooks = [
        {
            "name": arc.get("name"),
            "summary": arc_summary(arc),
            "_source_json": "story_arcs.json",
        }
        for arc in story_arcs
        if arc.get("name") and arc.get("canon_strength") in {"high", "medium"}
    ]
    combined_hooks: list[dict[str, Any]] = []
    seen_names: set[str] = set()
    preferred_hooks = arc_hooks[:14]
    if len(preferred_hooks) < 10:
        preferred_hooks.extend(hooks[: 14 - len(preferred_hooks)])
    for hook in preferred_hooks:
        name = str(hook.get("name") or "")
        if not name or name in seen_names:
            continue
        seen_names.add(name)
        combined_hooks.append(hook)
    events = [
        event_from_hook(hook, idx, gameplay_profile, chain_by_name.get(hook.get("name")), start_turn)
        for idx, hook in enumerate(combined_hooks[:14])
        if hook.get("name")
    ]
    output = {
        "world": world,
        "policy": "World events create time pressure. Effects and triggers are derived from gameplay_profile.json when canon evidence supports them; otherwise events only set generic state flags.",
        "events": events,
        "history": [],
    }
    write_json(wdir / "world_events.json", output)
    manifest = load_manifest(wdir, world)
    manifest["world_events"] = "world_events.json"
    save_manifest(wdir, manifest)
    print(f"Built world_events.json events={len(events)} start_turn={start_turn}")
    return output


def load_world_events(world: str) -> dict[str, Any]:
    wdir = world_dir(world)
    data = read_json(wdir / "world_events.json", {})
    return data if data else build_world_events(world)


def event_matches(event: dict[str, Any], player_input: str) -> bool:
    title = str(event.get("title", ""))
    if title and title in player_input:
        return True
    haystack = " ".join([title, str(event.get("summary", "")), " ".join(event.get("related_locations", []))])
    return any(token and token in player_input for token in haystack.replace("，", " ").replace("。", " ").split()[:12])


def event_relevant_to_context(event: dict[str, Any], state: dict[str, Any], player_input: str) -> bool:
    if event_matches(event, player_input):
        return True
    title = str(event.get("title", ""))
    if title and any(title == str(quest.get("name", "")) for quest in state.get("active_quests", []) if isinstance(quest, dict)):
        return True
    location = str(state.get("meta", {}).get("current_location", ""))
    if location and location in " ".join(str(item) for item in event.get("related_locations", [])):
        return True
    return False


def advance_world_events(world: str, state: dict[str, Any], player_input: str, dry_run: bool = False) -> tuple[list[str], list[str], dict[str, Any]]:
    data = load_world_events(world)
    events = data.setdefault("events", [])
    history = data.setdefault("history", [])
    turn = int(state.get("meta", {}).get("turn", 0) or 0)
    messages: list[str] = []
    options: list[str] = []
    state_events = state.setdefault("world_events", [])

    for event in events:
        status = event.get("status", "scheduled")
        starts = int(event.get("starts_at_turn", 1))
        expires = int(event.get("expires_at_turn", starts + 5))
        if status == "scheduled" and turn >= starts:
            event["status"] = "active"
            status = "active"
            if event_relevant_to_context(event, state, player_input):
                event["surfaced"] = True
                messages.append(event_start_message(event))
        if status != "active":
            continue
        if event_matches(event, player_input):
            event["surfaced"] = True
            event["progress"] = int(event.get("progress", 0)) + 1
            event["status"] = "intervened" if int(event["progress"]) >= 1 else "active"
            messages.append(event_intervened_message(event))
            messages.extend(apply_effects(world, state, event.get("effects", {}).get("intervened", []), f"介入世界事件：{event.get('title')}", dry_run))
            existing_ids = {row.get("event_id") for row in events}
            for trigger in event.get("triggers", []):
                if trigger.get("when") != "intervened":
                    continue
                created = instantiate_trigger_event(event, trigger, turn)
                if created and created.get("event_id") not in existing_ids:
                    events.append(created)
                    existing_ids.add(created.get("event_id"))
                    messages.append(event_created_message(created, event))
            history.append({"turn": turn, "event_id": event.get("event_id"), "result": "intervened"})
            continue
        if turn >= expires:
            event["status"] = "expired"
            consequences = event.get("if_ignored", [])
            if not event.get("surfaced") and not event_relevant_to_context(event, state, player_input):
                history.append({"turn": turn, "event_id": event.get("event_id"), "result": "expired_unseen"})
                continue
            messages.append(event_expired_message(event, consequences))
            messages.extend(apply_effects(world, state, event.get("effects", {}).get("ignored", []), f"忽略世界事件：{event.get('title')}", dry_run))
            existing_ids = {row.get("event_id") for row in events}
            for trigger in event.get("triggers", []):
                if trigger.get("when") != "expired":
                    continue
                created = instantiate_trigger_event(event, trigger, turn)
                if created and created.get("event_id") not in existing_ids:
                    events.append(created)
                    existing_ids.add(created.get("event_id"))
                    messages.append(event_created_message(created, event))
            history.append({"turn": turn, "event_id": event.get("event_id"), "result": "expired", "consequences": consequences[:3]})
        else:
            remain = expires - turn
            if event.get("surfaced") or event_relevant_to_context(event, state, player_input):
                event["surfaced"] = True
                options.append(f"关注{event_source_line(event)}（约 {remain} 回合后过期）。")

    state_events[:] = [
        {
            "event_id": event.get("event_id"),
            "title": event.get("title"),
            "status": event.get("status"),
            "expires_at_turn": event.get("expires_at_turn"),
        }
        for event in events
        if event.get("status") in {"active", "scheduled"}
    ][:12]
    return messages, options[:4], data


def main() -> None:
    parser = argparse.ArgumentParser(description="Build or inspect long-running world events.")
    parser.add_argument("--world", required=True)
    parser.add_argument("--rebuild", action="store_true")
    parser.add_argument("--start-turn", type=int, default=1, help="When rebuilding for an existing save, schedule events from this turn.")
    args = parser.parse_args()
    data = build_world_events(args.world, max(1, args.start_turn)) if args.rebuild else load_world_events(args.world)
    print(json.dumps(data, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
