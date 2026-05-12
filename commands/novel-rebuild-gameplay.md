---
description: Rebuild canon-derived gameplay mechanisms for a Novel Adventure world.
argument-hint: "<world>"
---

# Rebuild Novel Adventure Gameplay Profile

Arguments: `$ARGUMENTS`

Locate the installed `novel-adventure` skill directory. Check current working directory first, then `~/.codex/skills/novel-adventure`, `~/.claude/skills/novel-adventure`, `~/.agents/skills/novel-adventure`, `~/.hermes/skills/novel-adventure`, and `~/.openclaw/skills/novel-adventure`. Then run:

```bash
python novel.py rebuild-gameplay $ARGUMENTS
```

This regenerates `worlds/<world>/gameplay_profile.json` from distilled canon. It should be used after editing `power_system.json`, `game_rules.json`, `items.json`, `locations.json`, `factions.json`, `playable_canon.json`, or `canon_patches.jsonl`.
