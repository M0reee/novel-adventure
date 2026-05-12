---
description: Import host-model prompt-pack responses and rebuild the Novel Adventure world.
argument-hint: "<world> <llm_responses.jsonl>"
---

# Import Host-Model Distillation Responses

Arguments: `$ARGUMENTS`

Locate the installed `novel-adventure` skill directory, then run:

```bash
python novel.py host-import $ARGUMENTS
```

This imports LLM facts, merges canon, rebuilds playable rules, rebuilds retrieval, and writes a fresh quality report.
