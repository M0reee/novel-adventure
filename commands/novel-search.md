---
description: Search a Novel Adventure world's canon.
argument-hint: "<world> <query>"
---

# Search Novel Adventure Canon

Arguments: `$ARGUMENTS`

Locate the installed `novel-adventure` skill directory. Check current working directory first, then `~/.codex/skills/novel-adventure`, `~/.claude/skills/novel-adventure`, `~/.agents/skills/novel-adventure`, `~/.hermes/skills/novel-adventure`, and `~/.openclaw/skills/novel-adventure`. Parse the first argument as the world slug and the remaining text as the query, then run:

```bash
python novel.py search <world> "<query>"
```

Return concise matched canon facts. Do not load raw novel chunks unless the user explicitly asks for source inspection.
