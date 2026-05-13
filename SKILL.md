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

This also creates `opening.json`, `rpg_profile.json`, `item_market.json`, `economy_state.json`, `skill_tree.json`, `equipment_sets.json`, `acquisition_routes.json`, `director_plan.json`, `quest_lifecycle.json`, `npc_agency.json`, `reward_policy.json`, `evidence_cards.json`, `canon_eval.json`, `story_arcs.json`, `quest_templates.json`, `location_runtime.json`, `relationship_rules.json`, `scene_graph.json`, `encounter_state.json`, `world_events.json`, `ooc_report.json`, `distillation_score.md/json`, a readable `quality_report.md/json`, and a RPG-ready `player_state.json` schema for custom worlds.

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
7. Generate runtime economy, skill tree, and equipment sets:
   `python scripts/economy_runtime.py --world <slug> --rebuild`
   `python scripts/skill_tree.py --world <slug> --rebuild`
   `python scripts/equipment_sets.py --world <slug> --rebuild`
8. Generate quest templates:
   `python scripts/quest_runtime.py --world <slug> --rebuild`
9. Generate location runtime:
   `python scripts/location_runtime.py --world <slug> --rebuild`
10. Generate relationship rules:
   `python scripts/relationship_runtime.py --world <slug> --rebuild`
11. Generate cleaned scene graph:
   `python scripts/scene_graph.py --world <slug>`
12. Initialize encounter state:
   `python scripts/encounter_runtime.py --world <slug>`
13. Generate narrative intelligence:
   `python scripts/narrative_intelligence.py --world <slug> --rebuild`
14. Generate canon-first gameplay profile:
   `python scripts/gameplay_profile.py --world <slug> --rebuild`
15. Generate long-running world events:
   `python scripts/world_events.py --world <slug> --rebuild`
16. Generate acquisition routes:
   `python scripts/acquisition_routes.py --world <slug> --rebuild`
17. Run OOC availability QA:
   `python scripts/ooc_qa.py --world <slug>`
18. Generate long-form runtime projections:
   `python novel.py rebuild-runtime <slug>`
19. Generate opening:
   `python scripts/opening.py --world <slug> --rebuild`
20. Distill merged canon into game-ready rules:
   `python scripts/distill_playable.py --world <slug>`
21. Build retrieval index:
   `python scripts/index.py --world <slug>`
22. Score narrative distillation quality:
   `python scripts/distillation_qa.py --world <slug>`
23. Optional deterministic QA:
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

Scene rule: runtime scene generation must prefer `scene_graph.json` over raw `locations.json`, `npcs.json`, or `factions.json`. Raw entity files can contain extraction noise; `scene_graph.json` is the cleaned playable projection used to produce current location, visible NPCs, resources, hooks, and free-roam options.

Most important rule: the agent is a game master and rules judge, not a wish fulfiller. Player actions must be checked against canon, current state, resources, risk, time, location, relationships, and power limits before success is granted.

Runtime-memory rule: every turn should preserve what the player has actually learned or changed. `run_turn.py` writes scene visits, NPC interaction memory, investigated resources, opportunity progress, and long-arc attention into `player_state.json` under `runtime.scenes` and `runtime.story_arcs`. Do not re-offer task-step checklists as if they were free-roam options; use the runtime memory to make later options more specific and grounded.

RPG rule: numeric outcomes must come from structured state and scripts. Character stats live in `player_state.json` under `stats`, `equipment`, `skills`, `active_effects`, and `inventory`. World-facing names live in `rpg_profile.json`: do not assume every world has "MP", "法力", or generic equipment. Use `scripts/action_resolver.py` as the first stop for trade, cultivation, combat, quest, location, social, inventory, and info actions; it routes to `item_market.json`, `quest_templates.json`, `location_runtime.json`, `relationship_rules.json`, `encounter_state.json`, `scripts/game_math.py`, and `scripts/combat.py`. Do not invent HP, resource, damage, EXP, currency, equipment, skill, quest, relationship, location, encounter, or Buff changes in narration without writing them into state.

Progression rule: learnable skills live in `skill_tree.json`; equipment set bonuses live in `equipment_sets.json`; runtime supply and price pressure live in `economy_state.json`. `skill_tree.json` is a canon-gated availability graph, not permission to learn every named skill. A player must first obtain source, permission, inheritance, scroll, teacher access, faction qualification, or another canon-compatible route; only then may training progress from `source_known` to `training` to `usable` before writing to `player.skills`. `equipment_sets.json` entries must have `canon_gate.enabled=true` before bonuses can be written to `equipment_set_bonuses`; inferred or unsupported sets stay disabled. Market checks/purchases must update economy runtime state. These files are canon-derived playable projections, not genre templates.

OOC guardrail: never treat "appears in the novel" as "available to the player." Main-character-only skills, bloodline powers, faction secrets, one-off artifacts, sealed items, soul bones, cyberware modules, rituals, or equipment synergies require explicit acquisition and prerequisite checks. If evidence is weak, expose it as rumor, clue, or potential route, not as an immediately usable rule.

Acquisition-route rule: skills, rare items, equipment sets, and restricted locations should use `acquisition_routes.json` as their route map. Offer the player concrete next steps such as discover/source/train/verify or locate/verify/acquire/use, but do not present internal task-step checklists as free-roam options. If a route is weak or inferred, describe it as a rumor or lead until the player verifies it in-world.

Canon-evidence rule: each turn should expose concise `Canon 证据` when a ruling depends on retrieved canon, a `canon_gate`, an acquisition route, or a conservative block. Show enough evidence for the player to understand why an action succeeded, failed, or became conditional, but never dump long raw source text into the response.

Runtime-layer rule: use `player_state.json.runtime.layers` to keep canon evidence, derived playable rules, confirmed facts, rumors, and rulings separate. Do not promote rumors or route leads into confirmed world state until the player verifies them through action.

Director rule: `director_plan.json` controls pacing only. It may surface canon-derived opportunity windows, cooldown, consequences, or pressure, but it must not force a quest, teleport the player, grant rewards, or override free-form actions.

Quest-lifecycle rule: `quest_lifecycle.json` tracks lead/contact/prepare/execute/settle/aftermath. Do not present internal objectives as a checklist to be auto-completed; use phases to explain progress, required proof, and why rewards are or are not ready.

NPC-agency rule: `npc_agency.json` lets NPCs act according to motives and boundaries. NPCs can refuse, ask for terms, offer limited clues, or follow up on promises, but cannot betray canon motives or hand out unsupported resources.

Reward rule: `reward_policy.json` defines valid reward channels. Combat rewards come from `combat.py`; quest rewards require completed objectives; social/info/location actions may grant relationship, clues, access, or risk reduction, but not direct unearned items or skills.

Journal rule: `runtime.journal` and `journal.md` preserve player-visible memory: recent actions, open threads, promises, and risks. Use it to maintain continuity, not to create new canon.

Canon-eval rule: `canon_eval.json` contains generated anti-OOC regression cases for the current novel. Use it after major pipeline changes or when testing a new book to catch direct skill grants, instant rewards, and ability-boundary violations.

World-event rule: long-running events live in `world_events.json` and are advanced by `run_turn.py`. Mention active or expired events when relevant; ignored events may expire and change the world, while intervened events may create quests, access, resources, relationships, or risk reduction. Event effects must be applied through `runtime_effects.py` so market, location, relationship, state flags, and follow-up events are structured.

Narrative intelligence rule: `npc_motives.json`, `ability_boundaries.json`, `foreshadowing.json`, `event_chains.json`, and `story_arcs.json` are host-facing canon-derived guidance. Use NPC motives for social offers/refusals, ability boundaries for special powers and item/technique use, foreshadowing to avoid premature spoilers, event chains for cause-and-effect pressure, and story arcs for original-novel long-running goals or recurring mission loops. These files guide rulings but cannot override canon patches, retrieved canon, or player state.

Story-arc rule: important recurring novel goals live in `story_arcs.json` and may seed `quest_templates.json`, `world_events.json`, retrieval, and long-term player goals. Treat them as staged arcs, not instant objectives: players must satisfy entry conditions, progress loops, risks, and canon rewards before payoff.

Ability-boundary rule: when the player uses, attacks with, consumes, equips, activates, breaks through with, or overstates a special ability/item/technique, check `ability_boundaries.json` through `scripts/action_resolver.py` or `scripts/inventory_runtime.py`. Overreach such as automatic victory, no-cost use, forced breakthrough, or realm-defying "I just win" claims must be blocked or downgraded into preparation, probing, retreat, or prerequisite gathering.

Foreshadowing rule: investigation, questioning, secret, or truth-seeking actions may reveal surface clues from `foreshadowing.json`, but hidden truth cannot be disclosed until trust, evidence, location, or event conditions are met. Track discovered clues in `player_state.json` under `discovered_foreshadows`.

Distillation-quality rule: after building, importing host responses, or rebuilding narrative intelligence, run `/novel-score <slug>` or `python novel.py score <slug>`. Treat low scores as a build problem, not a runtime narration problem; improve extraction, LLM-assisted chunks, or canon patches before expecting stable long-form play.

OOC QA rule: after building or rebuilding gameplay projections, run `python scripts/ooc_qa.py --world <slug>` or `/novel-qa <slug>`. If `ooc_report.json` fails, fix gates/routes before playtesting; runtime narration should not compensate for missing canon availability data.

Canon-first gameplay rule: base math remains in `game_math.py`, but `combat.py` and `world_events.py` must load `gameplay_profile.json` through `gameplay_profile.py` before applying any special combat or event logic. `gameplay_profile.json` may enable realm pressure, ammo/charge, contamination, alert tracking, market windows, faction reaction, location access, crafting, or backlash only when distilled canon contains supporting evidence. Broad genre labels are low-confidence fallback only; they must never override canon or introduce unsupported mechanics.

Generality rule: do not hard-code a novel's genre assumptions. `bootstrap_profile.py` should infer broad genre and schema from text, then `rpg_profile.py` maps internal stats to world-specific terms such as spiritual energy, inner force, magic, stamina, sanity, credits, cyberware, artifacts, sealed items, mecha modules, or ordinary equipment. If the genre is unclear, use conservative generic defaults and rely on retrieved canon.

## References

- Extraction schema: `references/extraction_schema.md`
- LLM-assisted distillation: `references/llm_distillation.md`
- Game master rules: `references/game_master_rules.md`
- Canon conflict policy: `references/canon_conflict_policy.md`
- Narration style guide: `references/narration_style_guide.md`
