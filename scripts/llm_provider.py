#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from common import FACT_TYPES, read_jsonl, sha1_text, write_jsonl


LLM_FACT_TYPES = sorted(FACT_TYPES)
DEFAULT_BASE_URL = "https://api.openai.com/v1"
DEFAULT_MODEL = "gpt-4.1-mini"


def chunk_cache_key(chunk: dict[str, Any]) -> str:
    return f"{chunk.get('chunk_id')}:{chunk.get('text_hash') or sha1_text(chunk.get('text', ''), 16)}"


def system_prompt() -> str:
    return (
        "You are a canon distillation engine for a novel text-adventure skill. "
        "Extract compact, evidence-linked facts only from the provided chunk. "
        "Do not invent facts. Prefer playable, rule-relevant facts over prose summary. "
        "Return strict JSON with a top-level key `facts`."
    )


def user_prompt(chunk: dict[str, Any], profile: dict[str, Any]) -> str:
    schema = {
        "facts": [
            {
                "type": "world_law | power_realm | cultivation_rule | faction | location | npc | item | technique | event | relationship | style_signal | playable_hook",
                "name": "short canonical name",
                "claim": "atomic claim useful for gameplay and retrieval",
                "aliases": ["optional alias"],
                "confidence": 0.0,
                "playable_tags": ["optional: trade, combat, cultivation, quest, location, social, item"],
            }
        ]
    }
    profile_hint = {
        "genre": profile.get("genre", "unknown"),
        "power_axis": profile.get("schema", {}).get("power_axis", ""),
        "core_actions": profile.get("schema", {}).get("core_actions", []),
        "risk_axes": profile.get("schema", {}).get("risk_axes", []),
        "known_terms": {
            "realms": profile.get("realm_terms", [])[:40],
            "npcs": profile.get("known_npcs", [])[:40],
            "factions": profile.get("known_factions", [])[:40],
            "locations": profile.get("known_locations", [])[:40],
            "items": profile.get("known_items", [])[:40],
            "techniques": profile.get("known_techniques", [])[:40],
        },
    }
    return (
        "Extract up to 14 facts from this chunk.\n"
        "Rules:\n"
        f"- Allowed types: {', '.join(LLM_FACT_TYPES)}.\n"
        "- Keep every claim under 220 Chinese characters or 120 English words.\n"
        "- Every fact must be grounded in the chunk; no outside knowledge.\n"
        "- Prefer facts that can become rules: costs, risks, limits, resources, locations, factions, NPC motives, item effects, techniques, quest hooks.\n"
        "- For NPCs, capture motivations, fears, leverage, secrets, loyalties, boundaries, and what would make them help or refuse.\n"
        "- For items/techniques/powers, capture can-do, cannot-do, costs, risks, requirements, failure modes, and scaling limits.\n"
        "- For foreshadowing, capture the player-visible clue as a fact without spoiling hidden truth unless the chunk explicitly states it.\n"
        "- For events, capture cause/effect, deadlines, ignored consequences, intervention outcomes, and follow-up hooks.\n"
        "- If the chunk has no useful canon, return an empty facts array.\n"
        "- Return JSON only.\n\n"
        f"Expected JSON shape:\n{json.dumps(schema, ensure_ascii=False)}\n\n"
        f"World profile hints:\n{json.dumps(profile_hint, ensure_ascii=False)}\n\n"
        f"Chunk id: {chunk.get('chunk_id')}\n"
        f"Chapter: {chunk.get('chapter_title', '')}\n"
        "Chunk text:\n"
        f"{chunk.get('text', '')}"
    )


def request_row(chunk: dict[str, Any], profile: dict[str, Any], model: str) -> dict[str, Any]:
    return {
        "request_id": "llm_req_" + sha1_text(chunk_cache_key(chunk), 16),
        "chunk_id": chunk.get("chunk_id"),
        "text_hash": chunk.get("text_hash") or sha1_text(chunk.get("text", ""), 16),
        "model": model,
        "system": system_prompt(),
        "user": user_prompt(chunk, profile),
        "expected_response": {"facts": []},
    }


def normalize_json_text(text: str) -> str:
    text = text.strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, flags=re.S)
    if fenced:
        text = fenced.group(1).strip()
    return text


def parse_llm_facts(raw: str | dict[str, Any] | list[Any], chunk: dict[str, Any]) -> list[dict[str, Any]]:
    if isinstance(raw, str):
        data = json.loads(normalize_json_text(raw))
    else:
        data = raw
    rows = data.get("facts", data) if isinstance(data, dict) else data
    if not isinstance(rows, list):
        return []
    out: list[dict[str, Any]] = []
    for row in rows[:20]:
        if not isinstance(row, dict):
            continue
        ftype = str(row.get("type", "")).strip()
        name = str(row.get("name", "")).strip()
        claim = str(row.get("claim", "")).strip()
        if ftype not in FACT_TYPES or not name or not claim:
            continue
        confidence = float(row.get("confidence", 0.72) or 0.72)
        normalized = {
            "type": ftype,
            "name": name[:40],
            "claim": claim[:360],
            "aliases": [str(alias).strip() for alias in row.get("aliases", []) if str(alias).strip()][:6],
            "evidence_chunk_ids": [chunk.get("chunk_id")],
            "confidence": round(max(0.0, min(1.0, confidence)), 2),
            "quality": round(max(0.0, min(1.0, float(row.get("quality", confidence) or confidence))), 2),
            "source": "llm_assisted",
            "playable_tags": [str(tag).strip() for tag in row.get("playable_tags", []) if str(tag).strip()][:8],
        }
        basis = f"{normalized['type']}|{normalized['name']}|{normalized['claim']}|{chunk.get('chunk_id')}"
        normalized["fact_id"] = "fact_llm_" + sha1_text(basis, 16)
        out.append(normalized)
    return out


class OpenAICompatibleProvider:
    def __init__(
        self,
        model: str | None = None,
        base_url: str | None = None,
        api_key: str | None = None,
        timeout: int = 120,
        temperature: float = 0.1,
        retries: int = 2,
    ) -> None:
        self.model = model or os.getenv("NOVEL_ADVENTURE_LLM_MODEL") or os.getenv("OPENAI_MODEL") or DEFAULT_MODEL
        self.base_url = (base_url or os.getenv("NOVEL_ADVENTURE_LLM_BASE_URL") or os.getenv("OPENAI_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")
        self.api_key = api_key or os.getenv("NOVEL_ADVENTURE_LLM_API_KEY") or os.getenv("OPENAI_API_KEY")
        self.timeout = timeout
        self.temperature = temperature
        self.retries = retries
        if not self.api_key:
            raise SystemExit("Missing API key. Set NOVEL_ADVENTURE_LLM_API_KEY or OPENAI_API_KEY.")

    def complete(self, chunk: dict[str, Any], profile: dict[str, Any]) -> str:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt()},
                {"role": "user", "content": user_prompt(chunk, profile)},
            ],
            "temperature": self.temperature,
            "response_format": {"type": "json_object"},
        }
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=body,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        last_error: Exception | None = None
        for attempt in range(self.retries + 1):
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as response:
                    data = json.loads(response.read().decode("utf-8"))
                return data["choices"][0]["message"]["content"]
            except (urllib.error.URLError, urllib.error.HTTPError, KeyError, json.JSONDecodeError) as exc:
                last_error = exc
                if attempt < self.retries:
                    time.sleep(1.5 * (attempt + 1))
        raise RuntimeError(f"LLM request failed after retries: {last_error}")

    def extract_facts(self, chunk: dict[str, Any], profile: dict[str, Any]) -> list[dict[str, Any]]:
        return parse_llm_facts(self.complete(chunk, profile), chunk)


def load_cached_facts(cache_path: Path) -> dict[str, list[dict[str, Any]]]:
    cache: dict[str, list[dict[str, Any]]] = {}
    for row in read_jsonl(cache_path):
        key = row.get("cache_key")
        facts = row.get("facts")
        if key and isinstance(facts, list):
            cache[str(key)] = facts
    return cache


def save_cached_facts(cache_path: Path, cache: dict[str, list[dict[str, Any]]]) -> None:
    write_jsonl(cache_path, [{"cache_key": key, "facts": facts} for key, facts in sorted(cache.items())])


def write_prompt_pack(path: Path, chunks: list[dict[str, Any]], profile: dict[str, Any], model: str) -> None:
    write_jsonl(path, [request_row(chunk, profile, model) for chunk in chunks])


def load_response_facts(path: Path, chunks_by_id: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    facts: list[dict[str, Any]] = []
    for row in read_jsonl(path):
        chunk_id = row.get("chunk_id")
        chunk = chunks_by_id.get(str(chunk_id))
        if not chunk:
            continue
        payload = row.get("facts") if "facts" in row else row.get("response", row.get("output", row))
        facts.extend(parse_llm_facts(payload, chunk))
    return facts
