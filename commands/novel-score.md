---
description: Score Novel Adventure narrative distillation quality.
argument-hint: "<world>"
---

# Score Novel Adventure Distillation

Arguments: `$ARGUMENTS`

Locate the installed `novel-adventure` skill directory. Check current working directory first, then `~/.codex/skills/novel-adventure`, `~/.claude/skills/novel-adventure`, `~/.agents/skills/novel-adventure`, `~/.hermes/skills/novel-adventure`, and `~/.openclaw/skills/novel-adventure`. Then run:

```bash
python novel.py score $ARGUMENTS
```

This writes:

- `worlds/<world>/distillation_score.json`
- `worlds/<world>/distillation_score.md`

Use this after building or importing a world to evaluate NPC motives, ability boundaries, foreshadowing, event chains, evidence quality, and template-pollution risk.
