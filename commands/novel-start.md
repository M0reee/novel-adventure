---
description: Start or reset a Novel Adventure world or save slot.
argument-hint: "<world> [--slot slot] [--reset]"
---

# Start Novel Adventure World

Arguments: `$ARGUMENTS`

Locate the installed `novel-adventure` skill directory. Check current working directory first, then `~/.codex/skills/novel-adventure`, `~/.claude/skills/novel-adventure`, `~/.agents/skills/novel-adventure`, `~/.hermes/skills/novel-adventure`, and `~/.openclaw/skills/novel-adventure`. Then run:

```bash
python novel.py start $ARGUMENTS
```

If the user does not provide a world slug, first run `python novel.py worlds` and ask which world to start.

Use `--slot <name>` for named saves. If omitted, the default `player_state.json` save is used.
