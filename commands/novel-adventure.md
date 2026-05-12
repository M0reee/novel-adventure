---
description: Start the Novel Adventure guided launcher.
argument-hint: "[optional world/action]"
---

# Novel Adventure

Use the installed `novel-adventure` skill as a guided launcher and strict text-adventure game master.

Arguments: `$ARGUMENTS`

Find the skill directory in this order:

1. Current working directory if it contains `novel.py` and `SKILL.md`.
2. `~/.codex/skills/novel-adventure`
3. `~/.claude/skills/novel-adventure`
4. `~/.agents/skills/novel-adventure`
5. `~/.hermes/skills/novel-adventure`
6. `~/.openclaw/skills/novel-adventure`

If no arguments are supplied, run:

```bash
python novel.py launch
```

Present its menu to the user. If command execution is unavailable, ask this exact guided choice instead:

```text
请选择你要做什么：
1. 游玩已有世界 / 读取存档
2. 蒸馏新的小说世界
```

If the user chooses `1`, show available worlds from `python novel.py worlds`, then ask them to choose:

```text
请选择世界或存档：
- 输入世界 slug 或编号继续已有存档
- 可输入存档 slot；如果要重开，在选择后说明“重置”
```

After the user chooses, run one of:

```bash
python novel.py start <world>
python novel.py start <world> --slot <slot>
python novel.py start <world> --slot <slot> --reset
```

If the user chooses `2`, ask:

```text
请选择蒸馏方式：
1. 本地启发式蒸馏（无需 API，最快，质量基础）
2. API LLM-assisted 蒸馏（质量更好，需要 NOVEL_ADVENTURE_LLM_API_KEY）
3. 宿主模型 prompt-pack（不需要 API，先导出请求再让宿主模型处理）

请提供：
- 世界 slug
- 小说 TXT/MD 文件或目录路径
```

Then run the matching command:

```bash
python novel.py build <world> <txt_or_dir>
python novel.py build <world> <txt_or_dir> --llm-provider openai-compatible --llm-max-chunks 120
python novel.py host-export <world> --input <txt_or_dir> --llm-max-chunks 80
```

For host-model prompt-pack mode, after responses are written, run `python novel.py host-import <world> worlds/<world>/llm_responses.jsonl`.

If arguments are supplied:

- World slug only: run `python novel.py start <world>`.
- World slug plus action: run:

```bash
python novel.py play <world> "<action>"
```

Rules:

- Never load a whole novel into context.
- During play, use retrieved canon and structured state; do not grant declared success without rule checks.
- During distillation, require a local TXT/MD path; do not ask the user to paste the full novel into chat.
- If arguments are ambiguous, ask one short clarifying question.
