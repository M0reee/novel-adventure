#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sqlite3
from typing import Any

from common import load_world_profile, read_json, world_dir


PREFERRED_TYPES = {
    "canon_patch": 0,
    "evidence_card": 1,
    "power_realm": 2,
    "cultivation_rule": 3,
    "world_law": 4,
    "faction": 5,
    "location": 6,
    "npc": 7,
    "item": 8,
    "technique": 9,
    "event": 10,
    "story_arc": 11,
    "recurring_mission": 12,
    "playable_hook": 13,
    "playable_location": 14,
    "playable_npc": 15,
    "playable_faction": 16,
    "playable_item": 17,
    "playable_technique": 18,
    "playable_power_realm": 19,
    "playable_cultivation_rule": 20,
    "npc_motive": 21,
    "ability_boundary": 22,
    "event_chain": 23,
    "foreshadowing": 24,
    "game_rule": 25,
    "style_signal": 26,
}


ACTION_TERMS = [
    "修炼", "突破", "斗气", "斗技", "功法", "炼药", "丹药", "异火", "拍卖", "交易",
    "打听", "调查", "探索", "追杀", "试炼", "招生", "退婚", "三年之约", "赚钱", "筹钱", "委托",
]


def _direct_name_hit(row: dict[str, Any], query: str) -> bool:
    name = str(row.get("name") or "")
    if name and name in query:
        return True
    aliases = str(row.get("aliases") or "")
    return any(alias and alias in query for alias in aliases.split("|"))


def _diversify(rows: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    """Prevent broad terms like "斗气" from filling the whole context with one type."""
    if limit <= 0:
        return []
    per_type_limit = max(2, min(4, limit // 3 or 2))
    selected: list[dict[str, Any]] = []
    selected_ids: set[str] = set()
    type_counts: dict[str, int] = {}

    for row in rows:
        row_id = str(row.get("id") or "")
        row_type = str(row.get("type") or "")
        type_cap = limit if row_type == "canon_patch" else per_type_limit
        if row_id in selected_ids or type_counts.get(row_type, 0) >= type_cap:
            continue
        selected.append(row)
        selected_ids.add(row_id)
        type_counts[row_type] = type_counts.get(row_type, 0) + 1
        if len(selected) >= limit:
            return selected

    for row in rows:
        row_id = str(row.get("id") or "")
        if row_id in selected_ids:
            continue
        selected.append(row)
        selected_ids.add(row_id)
        if len(selected) >= limit:
            return selected

    return selected


def safe_terms(query: str, profile: dict[str, Any] | None = None) -> list[str]:
    terms: list[str] = []
    for token in re.findall(r"[A-Za-z0-9_\-\u4e00-\u9fff]{2,}", query):
        if len(token) <= 8:
            terms.append(token)
    if profile:
        for key in ("realm_terms", "known_npcs", "known_factions", "known_locations", "known_items", "known_techniques"):
            for term in profile.get(key, []):
                if term and term in query:
                    terms.append(term)
    for term in ACTION_TERMS:
        if term in query:
            terms.append(term)
    deduped: list[str] = []
    seen = set()
    for term in terms:
        if term not in seen:
            deduped.append(term)
            seen.add(term)
    return deduped[:20]


def retrieve(world: str, query: str, limit: int, ftype: str | None = None) -> list[dict[str, Any]]:
    wdir = world_dir(world)
    db_path = wdir / "retrieval.sqlite"
    if not db_path.exists():
        raise SystemExit("retrieval.sqlite not found. Run index.py first.")

    manifest = read_json(wdir / "manifest.json", {})
    profile = load_world_profile(wdir, manifest.get("profile", "generic"))
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows: list[sqlite3.Row] = []
    try:
        terms = safe_terms(query, profile)
        if terms:
            match_query = " OR ".join(terms)
            sql = """
                SELECT canon.*, bm25(canon_fts) AS rank_score
                FROM canon_fts
                JOIN canon ON canon_fts.id = canon.id
                WHERE canon_fts MATCH ?
            """
            params: list[Any] = [match_query]
            if ftype:
                sql += " AND canon.type LIKE ?"
                params.append(f"%{ftype}%")
            sql += " ORDER BY rank_score ASC, canon.score DESC, canon.quality DESC LIMIT ?"
            params.append(limit * 3)
            try:
                rows = conn.execute(sql, params).fetchall()
            except sqlite3.OperationalError:
                rows = []
        existing_ids = {row["id"] for row in rows}
        like_terms = safe_terms(query, profile) or [query]
        where = " OR ".join(["search_text LIKE ?"] * len(like_terms))
        sql = f"SELECT *, 0.0 AS rank_score FROM canon WHERE ({where})"
        params = [f"%{term}%" for term in like_terms]
        if ftype:
            sql += " AND type LIKE ?"
            params.append(f"%{ftype}%")
        sql += " ORDER BY score DESC, quality DESC LIMIT ?"
        params.append(limit * 5)
        fallback_rows = conn.execute(sql, params).fetchall()
        rows.extend(row for row in fallback_rows if row["id"] not in existing_ids)
    finally:
        conn.close()

    result = [dict(row) for row in rows]
    result.sort(
        key=lambda row: (
            0 if row.get("type") == "canon_patch" else 1,
            0 if _direct_name_hit(row, query) else 1,
            0 if row.get("type") == "evidence_card" else 1,
            0 if float(row.get("quality") or 0) >= 1.0 and float(row.get("score") or 0) >= 800 else 1,
            float(row.get("rank_score") or 0),
            -float(row.get("quality") or 0),
            -float(row.get("score") or 0),
            PREFERRED_TYPES.get(row.get("type", ""), 99),
        )
    )
    return _diversify(result, limit)


def main() -> None:
    parser = argparse.ArgumentParser(description="Retrieve scene-relevant canon facts.")
    parser.add_argument("--world", required=True)
    parser.add_argument("--query", required=True)
    parser.add_argument("--limit", type=int, default=30)
    parser.add_argument("--type")
    parser.add_argument("--format", choices=["json", "text"], default="json")
    args = parser.parse_args()
    rows = retrieve(args.world, args.query, args.limit, args.type)
    if args.format == "json":
        print(json.dumps(rows, ensure_ascii=False, indent=2))
    else:
        for row in rows:
            print(f"[{row['type']}] {row['name']}: {row['claim']} ({row['source_json']}; q={row.get('quality')}; s={row.get('score')})")


if __name__ == "__main__":
    main()
