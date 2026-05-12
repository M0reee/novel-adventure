# Novel Adventure

> 把你喜欢的长篇小说，变成一个能玩的文字冒险世界。

读完一本两百万字的修真小说还不过瘾？想以主角的视角，再走一遍那个世界？
**Novel Adventure** 帮你把整本小说蒸馏成结构化的世界设定，然后让 AI 充当**有规则、有判罚的游戏主持**，跟你打回合制冒险——而不是当一个"我说成功就成功"的愿望机。

## 它能做什么

- **吃下小说**：直接读 TXT/MD，按章切块入库
- **抽出设定**：自动提炼世界观、修炼体系、势力、地点、NPC、功法、物品、时间线、冒险钩子
- **本地检索**：用 SQLite FTS 建索引，运行时只取与当前场景相关的设定，不把原文塞给模型
- **玩文字冒险**：每回合输出场景叙事 / 规则裁定 / 行动结果 / 状态变化 / 世界动态 / 可选行动
- **裁判而非许愿机**：玩家行动会按原著 canon、当前境界、资源、风险与时机来判罚，不接受声明式成功
- **一键安装为 Skill**：支持 Claude Code、Codex、通用 Agent Skills 目录及自定义路径

## 为什么这样设计

直接把整本小说塞进 LLM 上下文窗口是典型的反模式：贵、慢、超限、还会让模型对剧情产生幻觉。
Novel Adventure 把"读小说"和"玩小说"分开 ——

- **离线**：把原文蒸馏成几个 JSON 文件 + 一个 SQLite 检索库
- **运行时**：只检索当前场景需要的几条设定和 NPC 状态喂给模型

这样的好处是：可以处理百万字级长篇，玩起来快，且模型不容易跑偏。

## 快速上手

```bash
git clone https://github.com/M0reee/novel-adventure.git
cd novel-adventure

# 方式 A：直接玩内置试玩预设
python novel.py start doupo_cangqiong --reset
python novel.py play doupo_cangqiong "观察萧家练武场，确认自己能接触哪些修炼机会"

# 方式 B：把自己的小说切块入库（输入可以是单文件，也可以是目录）
python novel.py build fanren /path/to/novel.txt

# 可选：用 LLM 辅助离线蒸馏，适合提升复杂设定抽取质量
export NOVEL_ADVENTURE_LLM_API_KEY="..."
python novel.py build fanren_llm /path/to/novel.txt \
  --llm-provider openai-compatible --llm-model gpt-4.1-mini --llm-max-chunks 120

# 然后开始玩
python novel.py start fanren --reset
python novel.py play fanren "我去坊市打听筑基丹的消息"
```

仓库内置的 `doupo_cangqiong` 是瘦身试玩预设，只包含结构化 canon、可玩规则、初始存档和检索索引；不包含原文切块、原始抽取 facts 或来源索引。

`--profile auto` 会先从样本章节生成 `world_profile.json`，再用它指导全书抽取。已有专门 profile 时也可以指定，例如 `--profile doupo`。

## 🚀 使用

在你装了 Novel Adventure 的宿主里启动它：

- Claude Code / 常见 Agent 宿主：输入 `/novel-adventure`。
- Codex 如果显示自定义 prompts 命名空间：输入 `/prompts:novel-adventure`。
- 如果宿主没有开放自定义 slash command，直接说：`启动 novel-adventure` 或 `使用 Novel Adventure 帮我玩小说文字冒险`。

第一次启动建议先玩内置预设：

```bash
/novel-start doupo_cangqiong --reset
```

启动后会显示主角身份、开场处境、当前困难和可选行动。然后复制任意行动继续：

```bash
/novel-play doupo_cangqiong 去乌坦城拍卖场打听筑基灵液价格
```

如果你要导入自己的小说：

```bash
/novel-build my_novel /path/to/novel.txt
/novel-start my_novel --reset
/novel-play my_novel 观察当前环境，确认我能做什么
```

想要更强蒸馏质量，可以启用 LLM-assisted distillation：

```bash
export NOVEL_ADVENTURE_LLM_API_KEY="..."
/novel-build my_novel_llm /path/to/novel.txt --llm-provider openai-compatible --llm-model gpt-4.1-mini --llm-max-chunks 120
```

如果你希望由宿主平台模型来蒸馏，而不是配置 API：

```bash
/novel-llm-pack my_novel --llm-max-chunks 80
```

这会生成 `worlds/my_novel/llm_requests.jsonl`，让宿主模型按里面的提示返回 JSONL，再用 `--llm-responses` 导入。

也可以不记命令，直接对宿主 Agent 说：

- “启动 Novel Adventure，打开斗破预设。”
- “帮我把 `/path/to/novel.txt` 构建成世界，slug 叫 `my_novel`。”
- “用 LLM 辅助蒸馏 `my_novel`，最多处理 120 个 chunk。”
- “在 `my_novel` 里运行一回合：我去坊市打听筑基丹。”
- “列出我现在有哪些世界。”
- “检查 `my_novel` 的世界库质量。”

## 🎛️ 管理命令

下表以 Claude Code / 通用 commands 目录的写法展示。Codex 如果采用 prompt 命名空间，把 `/novel-start` 改成 `/prompts:novel-start` 即可。

| 命令 | 说明 |
|---|---|
| `启动 novel-adventure` | 在宿主 Agent 里触发这个 Skill |
| `/novel-adventure` | 统一主入口；无参数时列出世界并提示开局 |
| `/novel-worlds` | 列出可游玩世界 |
| `/novel-start <slug> --reset` | 初始化或重置某个世界的存档 |
| `/novel-play <slug> <行动>` | 运行一回合文字冒险 |
| `/novel-build <slug> <txt_or_dir>` | 从 TXT/MD 小说构建世界 |
| `/novel-build <slug> <txt_or_dir> --llm-provider openai-compatible --llm-max-chunks 120` | 使用 LLM 辅助蒸馏 |
| `/novel-llm-pack <slug> --llm-max-chunks 80` | 导出给宿主模型处理的蒸馏请求 |
| `/novel-llm-import <slug> worlds/<slug>/llm_responses.jsonl` | 导入宿主模型返回的蒸馏结果 |
| `/novel-qa <slug>` | 检查世界库质量和运行时文件 |
| `/novel-search <slug> <关键词>` | 检索当前世界 canon |

CLI fallback：

| 命令 | 说明 |
|---|---|
| `python novel.py install --target codex --force` | 安装到 Codex Skills 目录，并同步安装 slash/prompt commands |
| `python novel.py install --target claude --force` | 安装到 Claude Skills 目录，并同步安装 slash commands |
| `python novel.py install --target hermes --force` | 安装到 Hermes 风格目录，并同步安装 commands |
| `python novel.py install --target openclaw --force` | 安装到 OpenClaw 风格目录，并同步安装 commands |
| `python novel.py worlds` | 列出可游玩世界 |
| `python novel.py start <slug> --reset` | 初始化或重置某个世界的存档 |
| `python novel.py play <slug> "<行动>"` | 运行一回合文字冒险 |
| `python novel.py build <slug> <txt_or_dir>` | 从 TXT/MD 小说构建世界 |
| `python novel.py qa <slug>` | 检查世界库质量和运行时文件 |

如果要手动分步执行：

```bash
python scripts/ingest.py --world fanren --input /path/to/novel.txt
python scripts/bootstrap_profile.py --world fanren
python scripts/extract.py --world fanren
python scripts/merge.py --world fanren
python scripts/opening.py --world fanren --rebuild
python scripts/distill_playable.py --world fanren
python scripts/index.py --world fanren
python scripts/qa_world.py --world fanren
```

## LLM 辅助蒸馏

默认构建仍是无 LLM、本地启发式抽取。需要更深的设定、人物动机、隐藏代价、特殊能力边界时，可以在**离线抽取阶段**启用 LLM-assisted distillation。运行时游玩不会加载整本小说，也不会每回合重跑 LLM 蒸馏。

API 模式：

```bash
export NOVEL_ADVENTURE_LLM_API_KEY="..."
export NOVEL_ADVENTURE_LLM_MODEL="gpt-4.1-mini"
python novel.py build fanren /path/to/novel.txt \
  --llm-provider openai-compatible --llm-max-chunks 120
```

宿主平台模式：

```bash
python novel.py llm-pack fanren --llm-max-chunks 80
```

这会生成 `worlds/fanren/llm_requests.jsonl`。让安装了 Skill 的模型平台按其中的 `system/user` 字段返回 JSONL，再导入：

```bash
python novel.py llm-import fanren worlds/fanren/llm_responses.jsonl
```

更多细节见 `references/llm_distillation.md`。

每个回合 AI 会按以下结构回应：

```
## 场景叙事
## 规则裁定
## 行动结果
## 状态变化
## 人物属性
## 世界动态
## 可执行行动
## 自定义行动
```

## 世界选择与开场

```bash
python novel.py worlds
python novel.py start <slug> --reset
```

`python novel.py start` 会初始化 `player_state.json`，并展示主角背景、开场场景、动机、当前困难和开局行动。`python novel.py build <slug> <txt_or_dir>` 会为用户自己蒸馏的新世界自动生成 `opening.json`、`rpg_profile.json`、`item_market.json`、`quest_templates.json`、`location_runtime.json`、`relationship_rules.json` 和 `encounter_state.json`，不需要手写。

## RPG 数值核心

角色状态现在包含 `stats`、`currencies`、`inventory`、`equipment`、`skills`、`active_effects`。内部计算字段保持稳定，但玩家看到的名称由 `rpg_profile.json` 映射到世界观：

- 通用内部字段是 `hp/mp/attack/defense/speed/hit_rate/dodge_rate/crit_rate/crit_damage/damage_bonus/damage_reduction`。
- 展示层会按小说蒸馏结果改名，例如 `mp` 可显示为斗气、魂力、灵力、内力、能源或理智。
- 装备系统也会按世界观改名，例如普通装备、法宝、魂骨、机甲模块、封印物。
- 装备的 `stats` 会进入最终属性。
- Buff/Debuff 放在 `active_effects`，通过 `modifiers` 修改属性，并按 `duration_turns` 递减。
- 技能包含 `mp_cost`、`power`、命中/暴击修正和效果；`mp_cost` 的展示名称由世界资源决定。
- 战斗用 `scripts/combat.py` 结算，奖励包含历练/经验、世界货币和物品掉落。
- 缺失数值可以由系统补成低影响可玩参数，但必须写入结构化文件，并且可被 `canon_patches.jsonl` 覆盖。

公式示例：

```text
命中率 = clamp(攻击方 hit_rate + 技能命中修正 - 防守方 dodge_rate, 0.05, 0.98)
基础伤害 = max(1, 攻击方 attack * 技能 power - 防守方 defense)
最终伤害 = 基础伤害 * (1 + damage_bonus) * (1 - damage_reduction)
暴击时最终伤害再乘 crit_damage
```

调试命令：

```bash
python scripts/game_math.py --world doupo_cangqiong
python scripts/combat.py --world doupo_cangqiong --enemy training_dummy --skill starter_attack --dry-run
python scripts/rpg_profile.py --world doupo_cangqiong
python scripts/economy.py --world doupo_cangqiong
python scripts/quest_runtime.py --world doupo_cangqiong
python scripts/location_runtime.py --world doupo_cangqiong
python scripts/relationship_runtime.py --world doupo_cangqiong
python scripts/encounter_runtime.py --world doupo_cangqiong
```

## 行动结算

`scripts/action_resolver.py` 会把自然语言行动分成交易、修炼、战斗、任务、地点、社交、物品、情报和高风险行动，并调用对应规则：

- 交易读取 `item_market.json`，会判断价格、货币、是否买得起、替代获取路径。
- 修炼会检查突破资源、护法和安全地点；不能一句话直接突破。
- 战斗调用 `combat.py`，并用 `encounter_state.json` 保存连续遭遇。
- 任务读取 `quest_templates.json`，玩家明确接取后才写入 `active_quests`，后续目标由 `quest_progress.py` 推进。
- 地点行动读取 `location_runtime.json`，会更新当前位置、风险和可用行动。
- 社交行动读取 `relationship_rules.json`，会把 NPC/势力关系写入 `relationships`。
- 物品行动通过 `inventory_runtime.py`，使用、装备、Buff 必须进入结构化状态。
- 情报行动只给信息和路线，不直接赠送物品、境界或胜利。

## 安装为 Skill

把它接到你的 AI 编程助手里，可以在任何对话中触发：

```bash
# Claude Code
python novel.py install --target claude --force

# Codex
python novel.py install --target codex --force

# 通用 Agent Skills
python novel.py install --target agents --force

# Hermes / OpenClaw 风格目录
python novel.py install --target hermes --force
python novel.py install --target openclaw --force

# 自定义目录
python novel.py install --destination /path/to/skills --command-destination /path/to/commands --force
```

安装脚本会复制 Skill，并把 `commands/*.md` 安装到宿主命令目录。Claude Code 使用 `~/.claude/commands`，Codex 兼容 prompt-command 目录 `~/.codex/prompts`，通用 Agent/Hermes/OpenClaw 使用各自 `commands` 目录。它只复制公开瘦身预设 `worlds/doupo_cangqiong/`，不会复制其他私有世界，也会排除 `chunks.jsonl`、`facts.jsonl`、`source_index.jsonl` 等原文/原始抽取文件。

## 目录结构

```text
novel-adventure/
├── SKILL.md                 # Agent Skill 入口
├── README.md
├── novel.py                 # 统一 CLI fallback
├── commands/                # 可安装为 slash command / prompt command 的入口
│   ├── novel-adventure.md
│   ├── novel-start.md
│   ├── novel-play.md
│   └── ...
├── scripts/
│   ├── ingest.py            # TXT/MD → 切块
│   ├── bootstrap_profile.py # 样本章节 → 自动 profile
│   ├── extract.py           # 切块 → 设定事实
│   ├── merge.py             # 事实 → 结构化世界库
│   ├── distill_playable.py  # 结构化设定 → 可玩规则
│   ├── index.py             # 建 SQLite FTS 索引
│   ├── retrieve.py          # 场景检索
│   ├── list_worlds.py       # 列出可游玩世界
│   ├── start_game.py        # 选择世界并初始化开场
│   ├── opening.py           # 生成 opening.json
│   ├── rpg_profile.py       # 世界观 RPG 术语与系统映射
│   ├── economy.py           # 物品价格、购买条件和替代获取路径
│   ├── quest_runtime.py     # 冒险钩子 → 任务模板
│   ├── quest_progress.py    # 推进任务目标与奖励
│   ├── location_runtime.py  # 地点入口、风险、资源、行动
│   ├── relationship_runtime.py # NPC/势力关系规则
│   ├── inventory_runtime.py # 物品使用、装备、Buff
│   ├── encounter_runtime.py # 连续战斗遭遇状态
│   ├── action_resolver.py   # 自然语言行动 → 规则结算
│   ├── game_math.py         # RPG 属性与公式
│   ├── combat.py            # 战斗与奖励结算
│   ├── run_turn.py          # 跑一回合
│   ├── build_world.py       # 一键完整构建
│   ├── qa_world.py          # 蒸馏质量检查
│   ├── install.py           # 安装为 Skill
│   └── common.py
├── references/              # 抽取 schema、判罚规则、风格指南
└── worlds/                  # 私有世界默认不入库；doupo_cangqiong 是公开瘦身试玩预设
```

`worlds/<slug>/` 会保存：

```text
chunks.jsonl            # 切块文本
world_profile.json      # 自动生成的小说题材/profile
rpg_profile.json        # 世界观 RPG 术语、资源、装备槽、技能名和战斗公式映射
item_market.json        # 物品价格、稀有度、购买条件、替代获取路径
quest_templates.json    # 可接取任务模板、目标、奖励、失败后果
location_runtime.json   # 地点风险、入口条件、资源和默认行动
relationship_rules.json # NPC/势力关系分数和影响规则
encounter_state.json    # 当前遭遇和历史战斗记录
opening.json            # 开场身份、场景、动机和开局选项
facts.jsonl             # 抽取出的设定事实
world_bible.json        # 世界观
power_system.json       # 修炼/能力体系
factions.json           # 势力
locations.json          # 地点
npcs.json               # NPC
items.json              # 物品
techniques.json         # 功法/技法
timeline.json           # 时间线
adventure_hooks.json    # 冒险钩子
playable_canon.json     # 二次蒸馏后的可玩规则
player_state.json       # 玩家存档
canon_patches.jsonl     # 用户校正的设定补丁
retrieval.sqlite        # 检索索引
```

由于可能含**版权文本**和**私设**，`worlds/` 默认在 `.gitignore` 里，不会被提交。唯一例外是公开瘦身预设 `worlds/doupo_cangqiong/`，它不包含 `chunks.jsonl`、`facts.jsonl` 或 `source_index.jsonl`。

## 规则裁定原则

这个 Skill 的智能体是**游戏主持 + 规则裁判**，不是愿望满足器。
玩家可以自由输入任何行动，但每个行动都要经过：

- 是否符合原著 canon
- 是否符合当前境界、资源、地点、时间
- 是否触发风险、代价、敌意或世界事件
- 是否只是"声明式成功"

举个反例：

```text
玩家：我直接成功突破筑基并秒杀所有敌人
```

不会被通过，会被裁定为声明式成功无效，要求拆解为可执行的子行动（备药、找静室、应对走火入魔风险……）。

## 设定纠错

如果运行中发现 AI 把原著设定弄错了，**不要**改原文。把修正写到：

```
worlds/<slug>/canon_patches.jsonl
```

每条 patch 一行 JSON：

```json
{"patch_id":"patch_0001","target":"power_system.realm.foundation","rule":"筑基期可以短距离御器飞行，但长途需要飞行法器或大量灵力。","reason":"修正违反原著","priority":"hard","created_at":"2026-05-09"}
```

然后重建索引：

```bash
python scripts/index.py --world fanren
```

`canon_patches` 优先级高于自动抽取的设定，会立刻生效。

## 容量与性能

| 字数级别 | 状态 | 说明 |
|---|---|---|
| 100 万字以下 | 推荐 | V1 流畅 |
| 100–500 万字 | 可用 | 抽取耗时 + 索引体积线性增长 |
| 500 万字以上 | 建议分卷 | 按卷或大节切批导入与抽取 |

## 已知限制

- V1 只支持 TXT / MD，**不支持** EPUB / PDF（可以先转 TXT）
- LLM-assisted distillation 需要 API key，或使用 `prompt-pack` 交给宿主平台模型离线处理
- 中文检索使用 SQLite FTS + LIKE 兜底，适合本地轻量使用
- `worlds/` 可能含版权文本，**不要**公开发布未瘦身的私有世界目录

## 路线图

- [x] 自动生成 `world_profile.json`
- [x] 二次蒸馏 `playable_canon.json`
- [x] 一键构建与 QA 脚本
- [x] 把 `extract.py` 接入可插拔的 LLM provider
- [ ] EPUB / PDF 导入
- [ ] 多人合作模式（一桌跑团）
- [ ] Web UI（可选）

## 许可

MIT.

如果这个项目让你重新过了一遍《凡人修仙传》或者《诡秘之主》的瘾，欢迎来 issue 区说一声，我会更有动力继续做。
