---
description: Export LLM prompt-pack requests for host-model distillation.
argument-hint: "<world> [--llm-max-chunks N]"
---

# Export Novel Adventure LLM Prompt Pack

Arguments: `$ARGUMENTS`

Locate the installed `novel-adventure` skill directory. Check current working directory first, then `~/.codex/skills/novel-adventure`, `~/.claude/skills/novel-adventure`, `~/.agents/skills/novel-adventure`, `~/.hermes/skills/novel-adventure`, and `~/.openclaw/skills/novel-adventure`. Then run:

```bash
python novel.py llm-pack $ARGUMENTS
```

This creates `worlds/<world>/llm_requests.jsonl`. The host model should process each request and return JSONL responses, then import them with `/novel-llm-import`.
