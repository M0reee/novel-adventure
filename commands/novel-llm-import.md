---
description: Import host-model LLM distillation responses.
argument-hint: "<world> <llm_responses.jsonl>"
---

# Import Novel Adventure LLM Responses

Arguments: `$ARGUMENTS`

Locate the installed `novel-adventure` skill directory. Check current working directory first, then `~/.codex/skills/novel-adventure`, `~/.claude/skills/novel-adventure`, `~/.agents/skills/novel-adventure`, `~/.hermes/skills/novel-adventure`, and `~/.openclaw/skills/novel-adventure`. Then run:

```bash
python novel.py llm-import $ARGUMENTS
```

After import, run:

```bash
python novel.py qa <world>
```
