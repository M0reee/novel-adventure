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

`python scripts/install.py --target codex`

Supported install targets:

- `codex`: `~/.codex/skills/novel-adventure`
- `claude`: `~/.claude/skills/novel-adventure`
- `agents`: `~/.agents/skills/novel-adventure`
- `project-claude`: `.claude/skills/novel-adventure`
- `project-codex`: `.codex/skills/novel-adventure`
- `project-agents`: `.agents/skills/novel-adventure`

### Build World

Preferred one-command build:

`python scripts/build_world.py --world <slug> --input <file_or_dir> --profile auto`

Manual build:

1. Import TXT/MD:
   `python scripts/ingest.py --world <slug> --input <file_or_dir>`
2. Bootstrap a generated profile for new novels:
   `python scripts/bootstrap_profile.py --world <slug>`
3. Extract facts:
   `python scripts/extract.py --world <slug>`
4. Merge canon:
   `python scripts/merge.py --world <slug>`
5. Distill merged canon into game-ready rules:
   `python scripts/distill_playable.py --world <slug>`
6. Build retrieval index:
   `python scripts/index.py --world <slug>`
7. Optional deterministic QA:
   `python scripts/qa_world.py --world <slug>`

### Update World

1. Re-run `ingest.py` for new or changed TXT/MD files.
2. Re-run `extract.py`, `merge.py`, and `index.py`.
3. For a different novel or major new volume, re-run `bootstrap_profile.py` before extraction.
4. Put user corrections in `worlds/<slug>/canon_patches.jsonl`; patches override merged canon.

### Play Turn

Run:

`python scripts/run_turn.py --world <slug> --input "<player action>"`

Each turn must use retrieved canon, update `player_state.json`, and return scene narration, action result, state changes, world dynamics, 3-5 action options, and a custom action prompt.

Most important rule: the agent is a game master and rules judge, not a wish fulfiller. Player actions must be checked against canon, current state, resources, risk, time, location, relationships, and power limits before success is granted.

## References

- Extraction schema: `references/extraction_schema.md`
- Game master rules: `references/game_master_rules.md`
- Canon conflict policy: `references/canon_conflict_policy.md`
- Narration style guide: `references/narration_style_guide.md`
