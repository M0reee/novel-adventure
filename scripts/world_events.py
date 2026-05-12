#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from typing import Any

from common import load_manifest, read_json, save_manifest, world_dir, write_json


EVENT_KEYWORDS = {
    "auction": ("拍卖", "交易", "市场", "黑市", "商会"),
    "faction": ("势力", "宗门", "家族", "公司", "军团", "教会", "公会"),
    "exploration": ("秘境", "遗迹", "洞府", "星域", "副本", "禁地", "探索"),
    "threat": ("追杀", "灾变", "尸潮", "战争", "封锁", "污染", "失控"),
    "training": ("修炼", "训练", "突破", "学习", "试炼", "考核"),
}


def event_id(name: str) -> str:
    return "event_" + hashlib.sha1(name.encode("utf-8")).hexdigest()[:10]


def classify_event(name: str, summary: str) -> str:
    text = f"{name} {summary}"
    for kind, words in EVENT_KEYWORDS.items():
        if any(word in text for word in words):
            return kind
    return "opportunity"


def event_from_hook(hook: dict[str, Any], index: int) -> dict[str, Any]:
    name = str(hook.get("name") or f"世界事件{index + 1}")
    summary = str(hook.get("summary") or hook.get("claim") or "")
    kind = classify_event(name, summary)
    start = 1 + index * 2
    expires = start + (4 if kind in {"auction", "threat"} else 6)
    return {
        "event_id": event_id(name),
        "title": name,
        "summary": summary,
        "type": kind,
        "status": "scheduled" if index > 0 else "active",
        "visibility": "known",
        "starts_at_turn": start,
        "expires_at_turn": expires,
        "related_locations": [],
        "related_npcs": [],
        "related_factions": [],
        "progress": 0,
        "if_ignored": ignored_consequences(kind),
        "if_intervened": intervened_outcomes(kind),
        "source": "adventure_hooks.json",
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


def build_world_events(world: str) -> dict[str, Any]:
    wdir = world_dir(world)
    hooks = read_json(wdir / "adventure_hooks.json", {}).get("hooks", [])
    events = [event_from_hook(hook, idx) for idx, hook in enumerate(hooks[:12]) if hook.get("name")]
    output = {
        "world": world,
        "policy": "World events create time pressure. Ignored active events can expire and change state; intervened events can become quests, relationships, resources, or location access.",
        "events": events,
        "history": [],
    }
    write_json(wdir / "world_events.json", output)
    manifest = load_manifest(wdir, world)
    manifest["world_events"] = "world_events.json"
    save_manifest(wdir, manifest)
    print(f"Built world_events.json events={len(events)}")
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


def advance_world_events(world: str, state: dict[str, Any], player_input: str) -> tuple[list[str], list[str], dict[str, Any]]:
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
            messages.append(f"世界事件出现：{event.get('title')}。")
        if status != "active":
            continue
        if event_matches(event, player_input):
            event["progress"] = int(event.get("progress", 0)) + 1
            event["status"] = "intervened" if int(event["progress"]) >= 1 else "active"
            messages.append(f"你介入了世界事件「{event.get('title')}」：{'；'.join(event.get('if_intervened', [])[:2])}。")
            history.append({"turn": turn, "event_id": event.get("event_id"), "result": "intervened"})
            continue
        if turn >= expires:
            event["status"] = "expired"
            consequences = event.get("if_ignored", [])
            messages.append(f"世界事件过期：{event.get('title')}。后果：{'；'.join(consequences[:2])}。")
            history.append({"turn": turn, "event_id": event.get("event_id"), "result": "expired", "consequences": consequences[:3]})
        else:
            remain = expires - turn
            options.append(f"关注世界事件「{event.get('title')}」（约 {remain} 回合后过期）。")

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
    args = parser.parse_args()
    data = build_world_events(args.world) if args.rebuild else load_world_events(args.world)
    print(json.dumps(data, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
