---
description: Check Novel Adventure world quality and runtime files.
argument-hint: "<world>"
---

# QA Novel Adventure World

Arguments: `$ARGUMENTS`

Locate the installed `novel-adventure` skill directory. Check current working directory first, then `~/.codex/skills/novel-adventure`, `~/.claude/skills/novel-adventure`, `~/.agents/skills/novel-adventure`, `~/.hermes/skills/novel-adventure`, and `~/.openclaw/skills/novel-adventure`. Then run:

```bash
python novel.py qa $ARGUMENTS
```

Summarize failed checks first. If all checks pass, state that the world is playable and mention remaining quality limits if obvious.
