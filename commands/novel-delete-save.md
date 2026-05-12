---
description: Delete a named Novel Adventure save slot.
argument-hint: "<world> <slot>"
---

# Delete Novel Adventure Save

Arguments: `$ARGUMENTS`

Locate the installed `novel-adventure` skill directory, then run:

```bash
python novel.py delete-save $ARGUMENTS
```

The default `player_state.json` save is protected and cannot be deleted through this command.
