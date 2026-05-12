---
description: Export host-model prompt-pack requests for Novel Adventure distillation.
argument-hint: "<world> --input <txt_or_dir> [--llm-max-chunks N]"
---

# Export Host-Model Distillation Pack

Arguments: `$ARGUMENTS`

Locate the installed `novel-adventure` skill directory, then run:

```bash
python novel.py host-export $ARGUMENTS
```

This creates `worlds/<world>/llm_requests.jsonl`. Do not paste full novel text into chat; use a local TXT/MD path.
