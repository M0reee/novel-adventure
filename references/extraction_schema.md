# Extraction Schema

The extractor distills source chunks into JSONL facts. Each fact should be short, evidence-linked, and useful for retrieval or gameplay.

Required fields:

```json
{
  "fact_id": "fact_<hash>",
  "type": "world_law",
  "name": "灵气",
  "claim": "天地灵气会在秘境开启前三日异常潮汐化。",
  "aliases": ["灵潮"],
  "evidence_chunk_ids": ["chunk_000001"],
  "confidence": 0.78
}
```

Allowed fact types:

- `world_law`: hard setting, cosmology, taboo, metaphysics, world constraints.
- `power_realm`: cultivation realms, ranks, stage names, power boundaries.
- `cultivation_rule`: breakthrough conditions, resources, risks, costs, failure effects.
- `faction`: sects, clans, dynasties, guilds, cults, alliances.
- `location`: towns, regions, secret realms, caves, forbidden zones.
- `npc`: named characters and important titles.
- `item`: pills, talismans, treasures, herbs, artifacts, resources.
- `technique`: arts, spells, methods, formations, weapon skills.
- `event`: timeline events, competitions, wars, auctions, hunts, openings.
- `relationship`: master-disciple, ally, enemy, debt, kinship, hidden identity.
- `style_signal`: narration rhythm, dialogue tone, conflict pattern, genre flavor.
- `playable_hook`: concrete opportunity for player action, risk, reward, or quest.

Good facts are atomic. Prefer several small claims over one long summary.

