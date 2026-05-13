#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from typing import Any

from common import read_json, world_dir, write_json


def compact(value: Any, limit: int = 120) -> str:
    text = " ".join(str(value or "").replace("\n", " ").split()).strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip("，。；： ") + "…"


def update_journal(
    state: dict[str, Any],
    player_input: str,
    resolution: dict[str, Any],
    state_changes: list[str],
    turn: int,
) -> list[str]:
    runtime = state.setdefault("runtime", {})
    journal = runtime.setdefault(
        "journal",
        {
            "policy": "Journal records what the player actually did, learned, promised, and risked. It is memory, not canon expansion.",
            "entries": [],
            "open_threads": [],
            "promises": [],
            "risks": [],
        },
    )
    entry = {
        "turn": turn,
        "action": compact(player_input, 100),
        "kind": resolution.get("kind"),
        "status": resolution.get("status"),
        "result": compact(resolution.get("consequence"), 140),
        "state_changes": [compact(line, 90) for line in state_changes[:6]],
    }
    journal.setdefault("entries", []).append(entry)
    journal["entries"] = journal["entries"][-80:]
    if resolution.get("status") in {"conditional", "partial_or_blocked", "blocked"}:
        journal.setdefault("risks", []).append({"turn": turn, "note": compact(resolution.get("verdict"), 100)})
        journal["risks"] = journal["risks"][-30:]
    if any(word in player_input for word in ("承诺", "人情", "交换", "答应", "以后")):
        journal.setdefault("promises", []).append({"turn": turn, "text": compact(player_input, 100), "status": "open"})
        journal["promises"] = journal["promises"][-30:]
    active_ids = {
        quest.get("quest_id")
        for quest in state.get("active_quests", [])
        if isinstance(quest, dict) and quest.get("status") == "active" and quest.get("quest_id")
    }
    journal["open_threads"] = [
        row
        for row in journal.get("open_threads", [])
        if row.get("quest_id") in active_ids
    ]
    for quest in state.get("active_quests", []):
        if isinstance(quest, dict) and quest.get("status") == "active":
            thread = {"quest_id": quest.get("quest_id"), "name": quest.get("name"), "phase": quest.get("phase_label", "进行中")}
            rows = journal.setdefault("open_threads", [])
            rows = [row for row in rows if row.get("quest_id") != thread["quest_id"]]
            rows.append(thread)
            journal["open_threads"] = rows[-20:]
    return ["冒险日志已更新。"]


def journal_lines(state: dict[str, Any]) -> list[str]:
    journal = state.get("runtime", {}).get("journal", {})
    entries = journal.get("entries", [])
    lines: list[str] = []
    if entries:
        last = entries[-1]
        lines.append(f"- 最近：T{last.get('turn')} {last.get('action')} -> {last.get('status')}")
    if journal.get("open_threads"):
        names = "、".join(str(row.get("name")) for row in journal.get("open_threads", [])[-3:] if row.get("name"))
        if names:
            lines.append(f"- 未结线索：{names}")
    if journal.get("promises"):
        lines.append(f"- 未清承诺/交换：{len(journal.get('promises', []))} 条")
    if journal.get("risks"):
        lines.append(f"- 近期风险：{compact(journal.get('risks', [])[-1].get('note'), 80)}")
    return lines or ["- 暂无日志。"]


def write_journal_markdown(world: str, state: dict[str, Any], slot: str | None = None) -> None:
    journal = state.get("runtime", {}).get("journal", {})
    lines = [f"# Journal: {world}", "", f"- Slot: {slot or 'default'}", ""]
    lines.append("## Recent Entries")
    for entry in journal.get("entries", [])[-20:]:
        lines.append(f"- T{entry.get('turn')} [{entry.get('kind')}/{entry.get('status')}] {entry.get('action')} -> {entry.get('result')}")
    lines.append("")
    lines.append("## Open Threads")
    for row in journal.get("open_threads", []):
        lines.append(f"- {row.get('name')} ({row.get('phase')})")
    lines.append("")
    lines.append("## Promises")
    for row in journal.get("promises", []):
        lines.append(f"- T{row.get('turn')} {row.get('text')} ({row.get('status')})")
    filename = f"journal_{slot}.md" if slot else "journal.md"
    (world_dir(world) / filename).write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect a world's player journal.")
    parser.add_argument("--world", required=True)
    args = parser.parse_args()
    state = read_json(world_dir(args.world) / "player_state.json", {})
    print(json.dumps(state.get("runtime", {}).get("journal", {}), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
