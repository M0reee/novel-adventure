---
description: Run one Novel Adventure text-adventure turn.
argument-hint: "<world> <player action>"
---

# Play One Novel Adventure Turn

Arguments: `$ARGUMENTS`

Locate the installed `novel-adventure` skill directory. Check current working directory first, then `~/.codex/skills/novel-adventure`, `~/.claude/skills/novel-adventure`, `~/.agents/skills/novel-adventure`, `~/.hermes/skills/novel-adventure`, and `~/.openclaw/skills/novel-adventure`. Parse the first argument as the world slug and the remaining text as the player action, then run:

```bash
python novel.py play <world> "<player action>"
```

Rules:

- The agent is a game master and rules judge, not a wish fulfiller.
- Check canon, current state, resources, location, relationships, risk, time, and power limits before success.
- Do not invent HP, resource, EXP, currency, item, skill, Buff, quest, relationship, or combat changes unless the command output writes them into state.
