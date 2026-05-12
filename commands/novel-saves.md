---
description: List Novel Adventure save slots for a world.
argument-hint: "<world>"
---

# List Novel Adventure Saves

Arguments: `$ARGUMENTS`

Locate the installed `novel-adventure` skill directory. Check current working directory first, then `~/.codex/skills/novel-adventure`, `~/.claude/skills/novel-adventure`, `~/.agents/skills/novel-adventure`, `~/.hermes/skills/novel-adventure`, and `~/.openclaw/skills/novel-adventure`. Then run:

```bash
python novel.py saves $ARGUMENTS
```

Use `default` for the backward-compatible `player_state.json` save. Named slots live under `worlds/<world>/saves/`.
