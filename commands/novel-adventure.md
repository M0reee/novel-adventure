---
description: Start Novel Adventure or show the main command guide.
argument-hint: "[world] [optional action]"
---

# Novel Adventure

Use the installed `novel-adventure` skill as a strict text-adventure game master.

Arguments: `$ARGUMENTS`

Find the skill directory in this order:

1. Current working directory if it contains `novel.py` and `SKILL.md`.
2. `~/.codex/skills/novel-adventure`
3. `~/.claude/skills/novel-adventure`
4. `~/.agents/skills/novel-adventure`
5. `~/.hermes/skills/novel-adventure`
6. `~/.openclaw/skills/novel-adventure`

If no arguments are supplied, run `python novel.py worlds`, then recommend starting the bundled preset with:

```bash
python novel.py start doupo_cangqiong --reset
```

If the user supplies a world slug only, run:

```bash
python novel.py start <world> --reset
```

If the user supplies a world slug plus an action, run:

```bash
python novel.py play <world> "<action>"
```

Rules:

- Never load a whole novel into context.
- During play, use retrieved canon and structured state; do not grant declared success without rule checks.
- If arguments are ambiguous, ask one short clarifying question.
