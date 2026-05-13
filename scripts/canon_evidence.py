#!/usr/bin/env python3
from __future__ import annotations

from typing import Any


HIDDEN_TYPES = {"npc_motive", "foreshadowing"}


def confidence_label(row: dict[str, Any]) -> str:
    quality = float(row.get("quality") or row.get("confidence") or 0.0)
    score = float(row.get("score") or 0.0)
    if row.get("type") == "canon_patch":
        return "hard"
    if quality >= 0.9 or score >= 800:
        return "high"
    if quality >= 0.65:
        return "medium"
    return "low"


def compact(text: Any, limit: int = 88) -> str:
    value = " ".join(str(text or "").replace("\n", " ").split()).strip()
    value = value.strip(" ，。；：“”\"'")
    if len(value) <= limit:
        return value
    return value[: limit - 1].rstrip("，。；： ") + "…"


def looks_like_excerpt(text: str) -> bool:
    value = str(text or "").strip()
    if not value:
        return True
    if value.startswith(("，", "。", "；", "：", "“", "”", "\"", "'")):
        return True
    quote_count = value.count("“") + value.count("”") + value.count("\"")
    return len(value) > 120 and quote_count >= 2


def evidence_summary(row: dict[str, Any]) -> str:
    for key in ("summary", "rule", "claim"):
        value = str(row.get(key) or "")
        if value and not looks_like_excerpt(value):
            return compact(value)
    row_type = str(row.get("type") or "canon")
    name = str(row.get("name") or "该设定")
    return f"检索命中 {row_type}「{name}」，但摘要过长，已按证据来源保守裁定。"


def evidence_rows(canon_rows: list[dict[str, Any]], limit: int = 5) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in canon_rows:
        row_type = str(row.get("type") or "")
        if row_type in HIDDEN_TYPES:
            continue
        name = str(row.get("name") or "")
        key = f"{row_type}:{name}:{row.get('source_json')}"
        if key in seen:
            continue
        seen.add(key)
        rows.append(
            {
                "id": row.get("id"),
                "type": row_type,
                "name": name,
                "source": row.get("source_json") or row.get("source") or "unknown",
                "confidence": confidence_label(row),
                "summary": evidence_summary(row),
            }
        )
        if len(rows) >= limit:
            break
    return rows


def evidence_lines(canon_rows: list[dict[str, Any]], resolution: dict[str, Any] | None = None, limit: int = 5) -> list[str]:
    rows = evidence_rows(canon_rows, limit)
    lines = [
        f"- {row['confidence']}｜{row['type']}｜{row['name'] or '未命名'}｜{row['source']}：{row['summary']}"
        for row in rows
        if row.get("summary")
    ]
    if resolution:
        gate = resolution.get("canon_gate") or {}
        if gate:
            lines.append(
                f"- gate｜{gate.get('canon_status', 'unknown')}｜{gate.get('source_type', 'unknown')}：{compact(gate.get('ooc_policy'), 96)}"
            )
    return lines or ["- 本回合没有强证据命中；只能按低影响、可逆、保守裁定推进。"]
