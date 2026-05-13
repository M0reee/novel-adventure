# LLM-Assisted Distillation

LLM assistance is optional and only runs during offline extraction. Runtime play still uses retrieval and structured state, not the full novel.

## Providers

### `none`

Default. Uses deterministic heuristic extraction only.

```bash
python scripts/extract.py --world <slug>
```

### `openai-compatible`

Calls an OpenAI-compatible `/chat/completions` endpoint per selected chunk.

Environment:

```bash
export NOVEL_ADVENTURE_LLM_API_KEY="..."
export NOVEL_ADVENTURE_LLM_MODEL="gpt-4.1-mini"
export NOVEL_ADVENTURE_LLM_BASE_URL="https://api.openai.com/v1"
```

Command:

```bash
python scripts/build_world.py \
  --world <slug> \
  --input /path/to/novel.txt \
  --profile auto \
  --llm-provider openai-compatible \
  --llm-model gpt-4.1-mini \
  --llm-max-chunks 120
```

Use `--llm-max-chunks` for cost control. Omit it only when you intentionally want to process all chunks.

### `prompt-pack`

Exports `worlds/<slug>/llm_requests.jsonl` and does not call any API. Use this when the host platform model should perform extraction.

```bash
python scripts/extract.py --world <slug> --profile auto --llm-provider prompt-pack --llm-max-chunks 80
```

Each JSONL row contains `system`, `user`, and expected response shape. Have the host model return JSONL rows like:

```json
{"chunk_id":"chunk_000001","facts":[{"type":"item","name":"筑基灵液","claim":"早期辅助修炼资源，需要可靠购买渠道。","aliases":[],"confidence":0.86}]}
```

Then import:

```bash
python scripts/extract.py --world <slug> --profile auto --llm-responses worlds/<slug>/llm_responses.jsonl
```

## What LLM Assistance Should Improve

The LLM extractor should prioritize facts that improve the narrative intelligence layer:

- NPC motives: public goal, private goal, fear, leverage, loyalty, secret, refusal boundary.
- Ability boundaries: can-do, cannot-do, cost, risk, requirement, failure mode, scaling limit.
- Foreshadowing: player-visible clue, hidden truth if explicit, reveal condition, payoff.
- Event chains: cause, deadline, intervention outcome, ignored consequence, follow-up hook.
- Story arcs / recurring missions: goals that appear across multiple scenes, why they matter, entry conditions, progression loop, risk, reward, and staged payoff.

These are still returned as normal `facts`; `scripts/narrative_intelligence.py` turns them into:

```text
npc_motives.json
ability_boundaries.json
foreshadowing.json
event_chains.json
story_arcs.json
```

Do not invent hidden truth or future payoffs that are not in the chunk. If a clue is only suggestive, record the surface clue and keep hidden truth host-only/unknown.

## Cache

`openai-compatible` writes `llm_facts_cache.jsonl`. Re-running extraction reuses cached chunk results by `chunk_id:text_hash`.

## Safety

- Do not put full novels in `SKILL.md`.
- Do not publish raw `chunks.jsonl`, `facts.jsonl`, `source_index.jsonl`, `llm_requests.jsonl`, `llm_responses.jsonl`, or `llm_facts_cache.jsonl` without checking copyright/privacy.
- Treat LLM output as candidate facts. `merge.py`, `canon_patches.jsonl`, and QA still decide what becomes playable canon.
