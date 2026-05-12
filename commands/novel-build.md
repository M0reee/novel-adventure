---
description: Build a playable Novel Adventure world from TXT/MD.
argument-hint: "<world> <txt_or_dir> [--llm-provider openai-compatible|prompt-pack] [--llm-max-chunks N]"
---

# Build Novel Adventure World

Arguments: `$ARGUMENTS`

Locate the installed `novel-adventure` skill directory. Check current working directory first, then `~/.codex/skills/novel-adventure`, `~/.claude/skills/novel-adventure`, `~/.agents/skills/novel-adventure`, `~/.hermes/skills/novel-adventure`, and `~/.openclaw/skills/novel-adventure`. Then run:

```bash
python novel.py build $ARGUMENTS
```

Input must be TXT/MD file or directory. Do not paste large novel text into chat. If the user has not provided a local path, ask for the path.

For higher quality offline distillation, accept optional arguments such as:

```bash
--llm-provider openai-compatible --llm-max-chunks 120
```

For host-model distillation without an API key, tell the user to use `/novel-llm-pack` after the basic build has produced chunks.
