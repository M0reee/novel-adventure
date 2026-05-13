---
description: Rebuild canon-gated acquisition routes and OOC availability checks.
argument-hint: <world>
---

Rebuild the selected Novel Adventure world's acquisition route map and OOC availability report.

Use this after updating `skill_tree.json`, `equipment_sets.json`, `item_market.json`, `locations.json`, or canon patches.

```bash
python novel.py rebuild-routes $ARGUMENTS
```

Then run a full world QA if you want the combined score:

```bash
python novel.py qa $ARGUMENTS
```
