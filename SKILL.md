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

The installer also copies portable slash-command prompt files from `commands/*.md` into the host command directory unless `--no-commands` is passed.

Supported install targets:

- `codex`: `~/.codex/skills/novel-adventure`
- `claude`: `~/.claude/skills/novel-adventure`
- `agents`: `~/.agents/skills/novel-adventure`
- `hermes`: `~/.hermes/skills/novel-adventure`
- `openclaw`: `~/.openclaw/skills/novel-adventure`
- `project-claude`: `.claude/skills/novel-adventure`
- `project-codex`: `.codex/skills/novel-adventure`
- `project-agents`: `.agents/skills/novel-adventure`
- `project-hermes`: `.hermes/skills/novel-adventure`
- `project-openclaw`: `.openclaw/skills/novel-adventure`

Command prompt destinations:

- Claude Code: `~/.claude/commands`, invoked as `/novel-adventure`, `/novel-start`, `/novel-play`, etc.
- Codex: `~/.codex/prompts`, invoked as `/novel-adventure` or `/prompts:novel-adventure` depending on Codex version.
- Generic Agents, Hermes, OpenClaw: `~/.agents/commands`, `~/.hermes/commands`, `~/.openclaw/commands` respectively.

### Build World

Preferred one-command build:

`python novel.py build <slug> <file_or_dir>`

Optional LLM-assisted offline distillation:

`python novel.py build <slug> <file_or_dir> --llm-provider openai-compatible --llm-model gpt-4.1-mini --llm-max-chunks 120`

Use `--llm-provider prompt-pack` when the host platform model should perform extraction without an API call. See `references/llm_distillation.md`.

This also creates `opening.json`, `rpg_profile.json`, `item_market.json`, `quest_templates.json`, `location_runtime.json`, `relationship_rules.json`, `encounter_state.json`, `world_events.json`, a readable `quality_report.md/json`, and a RPG-ready `player_state.json` schema for custom worlds.

### First-Run Use

If the user asks how to start after installation:

1. Tell them to use `/novel-adventure`; in Codex versions that namespace prompts, use `/prompts:novel-adventure`.
2. The first response should ask whether they want to `1. 游玩已有世界 / 读取存档` or `2. 蒸馏新的小说世界`.
3. If they choose play, show worlds and save status with `python novel.py launch` or `python novel.py worlds`, then start with `/novel-start <slug>`, `/novel-start <slug> --slot <slot>`, or `/novel-start <slug> --slot <slot> --reset`.
4. If they choose distill, ask for distillation mode, world slug, and TXT/MD path. Modes are local heuristic, API LLM-assisted, and host-model prompt-pack.
5. For immediate play without the wizard, use `/novel-start doupo_cangqiong --reset`, then `/novel-play doupo_cangqiong <player action>`.

Prefer slash commands when explaining usage. Use `python novel.py ...` as the CLI fallback. Keep `scripts/*.py` commands for advanced/manual pipeline work.

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
11. Generate long-running world events:
   `python scripts/world_events.py --world <slug> --rebuild`
12. Generate opening:
   `python scripts/opening.py --world <slug> --rebuild`
13. Distill merged canon into game-ready rules:
   `python scripts/distill_playable.py --world <slug>`
14. Build retrieval index:
   `python scripts/index.py --world <slug>`
15. Optional deterministic QA:
   `python scripts/qa_world.py --world <slug>`

### Update World

1. Re-run `ingest.py` for new or changed TXT/MD files.
2. Re-run `extract.py`, `merge.py`, and `index.py`.
3. For a different novel or major new volume, re-run `bootstrap_profile.py` before extraction.
4. Put user corrections in `worlds/<slug>/canon_patches.jsonl`; patches override merged canon.

### Play Turn

List or choose a world:

`/novel-worlds`

`/novel-start <slug> --reset`

Run:

`/novel-play <slug> <player action>`

Named save slots:

- `/novel-saves <slug>` lists saves.
- `/novel-start <slug> --slot <slot> --reset` starts or resets a branch.
- `/novel-play <slug> <player action> --slot <slot>` writes that turn to the branch.
- Default saves remain backward compatible at `worlds/<slug>/player_state.json`; named saves live in `worlds/<slug>/saves/<slot>.json`.

For immediate testing, use the included redacted preset:

`/novel-play doupo_cangqiong 我在乌坦城找药老打听异火和修炼斗气的方法`

Each turn must use retrieved canon, update `player_state.json`, and return scene narration, action result, state changes, world dynamics, 3-5 action options, and a custom action prompt.

Most important rule: the agent is a game master and rules judge, not a wish fulfiller. Player actions must be checked against canon, current state, resources, risk, time, location, relationships, and power limits before success is granted.

RPG rule: numeric outcomes must come from structured state and scripts. Character stats live in `player_state.json` under `stats`, `equipment`, `skills`, `active_effects`, and `inventory`. World-facing names live in `rpg_profile.json`: do not assume every world has "MP", "法力", or generic equipment. Use `scripts/action_resolver.py` as the first stop for trade, cultivation, combat, quest, location, social, inventory, and info actions; it routes to `item_market.json`, `quest_templates.json`, `location_runtime.json`, `relationship_rules.json`, `encounter_state.json`, `scripts/game_math.py`, and `scripts/combat.py`. Do not invent HP, resource, damage, EXP, currency, equipment, skill, quest, relationship, location, encounter, or Buff changes in narration without writing them into state.

World-event rule: long-running events live in `world_events.json` and are advanced by `run_turn.py`. Mention active or expired events when relevant; ignored events may expire and change the world, while intervened events may create quests, access, resources, relationships, or risk reduction. Event effects must be applied through `runtime_effects.py` so market, location, relationship, state flags, and follow-up events are structured.

Canon-first gameplay rule: base math remains in `game_math.py`, but `combat.py` and `world_events.py` must load `gameplay_profile.json` through `gameplay_profile.py` before applying any special combat or event logic. `gameplay_profile.json` may enable realm pressure, ammo/charge, contamination, alert tracking, market windows, faction reaction, location access, crafting, or backlash only when distilled canon contains supporting evidence. Broad genre labels are low-confidence fallback only; they must never override canon or introduce unsupported mechanics.

Generality rule: do not hard-code a novel's genre assumptions. `bootstrap_profile.py` should infer broad genre and schema from text, then `rpg_profile.py` maps internal stats to world-specific terms such as spiritual energy, inner force, magic, stamina, sanity, credits, cyberware, artifacts, sealed items, mecha modules, or ordinary equipment. If the genre is unclear, use conservative generic defaults and rely on retrieved canon.

## References

- Extraction schema: `references/extraction_schema.md`
- LLM-assisted distillation: `references/llm_distillation.md`
- Game master rules: `references/game_master_rules.md`
- Canon conflict policy: `references/canon_conflict_policy.md`
- Narration style guide: `references/narration_style_guide.md`
