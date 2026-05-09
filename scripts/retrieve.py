#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sqlite3
from typing import Any

from common import world_dir


def safe_terms(query: str) -> list[str]:
    terms = re.findall(r"[A-Za-z0-9_\-\u4e00-\u9fff]{2,}", query)
    return terms[:12]


def retrieve(world: str, query: str, limit: int, ftype: str | None = None) -> list[dict[str, Any]]:
    wdir = world_dir(world)
    db_path = wdir / "retrieval.sqlite"
    if not db_path.exists():
        raise SystemExit("retrieval.sqlite not found. Run index.py first.")

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows: list[sqlite3.Row] = []
    try:
        terms = safe_terms(query)
        if terms:
            match_query = " OR ".join(terms)
            sql = """
                SELECT canon.*, bm25(canon_fts) AS score
                FROM canon_fts
                JOIN canon ON canon_fts.id = canon.id
                WHERE canon_fts MATCH ?
            """
            params: list[Any] = [match_query]
            if ftype:
                sql += " AND canon.type LIKE ?"
                params.append(f"%{ftype}%")
            sql += " ORDER BY score LIMIT ?"
            params.append(limit)
            try:
                rows = conn.execute(sql, params).fetchall()
            except sqlite3.OperationalError:
                rows = []
        if len(rows) < limit:
            existing_ids = {row["id"] for row in rows}
            like_terms = safe_terms(query) or [query]
            where = " OR ".join(["search_text LIKE ?"] * len(like_terms))
            sql = f"SELECT *, 0.0 AS score FROM canon WHERE ({where})"
            params = [f"%{term}%" for term in like_terms]
            if ftype:
                sql += " AND type LIKE ?"
                params.append(f"%{ftype}%")
            sql += " LIMIT ?"
            params.append(limit * 2)
            fallback_rows = conn.execute(sql, params).fetchall()
            rows.extend(row for row in fallback_rows if row["id"] not in existing_ids)
    finally:
        conn.close()

    result = [dict(row) for row in rows]
    result.sort(key=lambda row: 0 if row.get("type") == "canon_patch" else 1)
    return result[:limit]


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
            print(f"[{row['type']}] {row['name']}: {row['claim']} ({row['source_json']})")


if __name__ == "__main__":
    main()
