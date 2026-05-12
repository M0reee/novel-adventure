---
description: Rebuild NPC motives, ability boundaries, foreshadowing, and event chains for a Novel Adventure world.
argument-hint: "<world>"
---

# Rebuild Novel Adventure Narrative Intelligence

Arguments: `$ARGUMENTS`

Locate the installed `novel-adventure` skill directory. Check current working directory first, then `~/.codex/skills/novel-adventure`, `~/.claude/skills/novel-adventure`, `~/.agents/skills/novel-adventure`, `~/.hermes/skills/novel-adventure`, and `~/.openclaw/skills/novel-adventure`. Then run:

```bash
python novel.py rebuild-narrative $ARGUMENTS
```

This regenerates:

- `npc_motives.json`
- `ability_boundaries.json`
- `foreshadowing.json`
- `event_chains.json`

Use it after editing NPCs, items, techniques, power systems, events, adventure hooks, or after importing LLM-assisted distillation responses.
