---
name: novel-adventure
description: Build and run text adventure games from long-form TXT/MD novels by extracting world canon, power systems, factions, locations, NPCs, timelines, playable rules, and scene-relevant retrieval context.
---

# Novel Adventure

Use this skill when the user wants to import a long novel, distill its world setting, or play a text adventure grounded in that novel's canon.

Core rule: never load a whole novel into context. Source text is processed offline into structured files and `retrieval.sqlite`; during play, retrieve only scene-relevant canon with `scripts/retrieve.py`.

## Workflows

### Install

This skill follows the Agent Skills folder format. Copy this directory into the target application skill directory, or use:

`python novel.py install --target codex --force`

Supported install targets:

- `codex`: `~/.codex/skills/novel-adventure`
- `claude`: `~/.claude/skills/novel-adventure`
- `agents`: `~/.agents/skills/novel-adventure`
- `project-claude`: `.claude/skills/novel-adventure`
- `project-codex`: `.codex/skills/novel-adventure`
- `project-agents`: `.agents/skills/novel-adventure`

### Build World

Preferred one-command build:

`python novel.py build <slug> <file_or_dir>`

Optional LLM-assisted offline distillation:

`python novel.py build <slug> <file_or_dir> --llm-provider openai-compatible --llm-model gpt-4.1-mini --llm-max-chunks 120`

Use `--llm-provider prompt-pack` when the host platform model should perform extraction without an API call. See `references/llm_distillation.md`.

This also creates `opening.json`, `rpg_profile.json`, `item_market.json`, `quest_templates.json`, `location_runtime.json`, `relationship_rules.json`, `encounter_state.json`, and a RPG-ready `player_state.json` schema for custom worlds.

### First-Run Use

If the user asks how to start after installation:

1. Tell them to say `启动 novel-adventure` in the host Agent, or use `/novel-adventure` only if that host supports slash commands.
2. For immediate play, run `python novel.py start doupo_cangqiong --reset`.
3. Continue with `python novel.py play doupo_cangqiong "<player action>"`.
4. For a custom novel, run `python novel.py build <slug> <txt_or_dir>`.
5. For deeper extraction, add `--llm-provider openai-compatible --llm-max-chunks 120`, or use `--llm-provider prompt-pack` and import `--llm-responses`.

Prefer friendly commands through `novel.py` when explaining usage. Keep `scripts/*.py` commands for advanced/manual pipeline work.

Manual build:

1. Import TXT/MD:
   `python scripts/ingest.py --world <slug> --input <file_or_dir>`
2. Bootstrap a generated profile for new novels:
   `python scripts/bootstrap_profile.py --world <slug>`
3. Extract facts:
   `python scripts/extract.py --world <slug>`
   Optional LLM API: `python scripts/extract.py --world <slug> --llm-provider openai-compatible --llm-max-chunks 120`
   Optional host-agent prompt pack: `python scripts/extract.py --world <slug> --llm-provider prompt-pack --llm-max-chunks 80`
4. Merge canon:
   `python scripts/merge.py --world <slug>`
5. Generate world-facing RPG profile:
   `python scripts/rpg_profile.py --world <slug> --rebuild`
6. Generate item economy:
   `python scripts/economy.py --world <slug> --rebuild`
7. Generate quest templates:
   `python scripts/quest_runtime.py --world <slug> --rebuild`
8. Generate location runtime:
   `python scripts/location_runtime.py --world <slug> --rebuild`
9. Generate relationship rules:
   `python scripts/relationship_runtime.py --world <slug> --rebuild`
10. Initialize encounter state:
   `python scripts/encounter_runtime.py --world <slug>`
11. Generate opening:
   `python scripts/opening.py --world <slug> --rebuild`
12. Distill merged canon into game-ready rules:
   `python scripts/distill_playable.py --world <slug>`
13. Build retrieval index:
   `python scripts/index.py --world <slug>`
14. Optional deterministic QA:
   `python scripts/qa_world.py --world <slug>`

### Update World

1. Re-run `ingest.py` for new or changed TXT/MD files.
2. Re-run `extract.py`, `merge.py`, and `index.py`.
3. For a different novel or major new volume, re-run `bootstrap_profile.py` before extraction.
4. Put user corrections in `worlds/<slug>/canon_patches.jsonl`; patches override merged canon.

### Play Turn

List or choose a world:

`python novel.py worlds`

`python novel.py start <slug> --reset`

Run:

`python novel.py play <slug> "<player action>"`

For immediate testing, use the included redacted preset:

`python novel.py play doupo_cangqiong "我在乌坦城找药老打听异火和修炼斗气的方法"`

Each turn must use retrieved canon, update `player_state.json`, and return scene narration, action result, state changes, world dynamics, 3-5 action options, and a custom action prompt.

Most important rule: the agent is a game master and rules judge, not a wish fulfiller. Player actions must be checked against canon, current state, resources, risk, time, location, relationships, and power limits before success is granted.

RPG rule: numeric outcomes must come from structured state and scripts. Character stats live in `player_state.json` under `stats`, `equipment`, `skills`, `active_effects`, and `inventory`. World-facing names live in `rpg_profile.json`: do not assume every world has "MP", "法力", or generic equipment. Use `scripts/action_resolver.py` as the first stop for trade, cultivation, combat, quest, location, social, inventory, and info actions; it routes to `item_market.json`, `quest_templates.json`, `location_runtime.json`, `relationship_rules.json`, `encounter_state.json`, `scripts/game_math.py`, and `scripts/combat.py`. Do not invent HP, resource, damage, EXP, currency, equipment, skill, quest, relationship, location, encounter, or Buff changes in narration without writing them into state.

## References

- Extraction schema: `references/extraction_schema.md`
- LLM-assisted distillation: `references/llm_distillation.md`
- Game master rules: `references/game_master_rules.md`
- Canon conflict policy: `references/canon_conflict_policy.md`
- Narration style guide: `references/narration_style_guide.md`
