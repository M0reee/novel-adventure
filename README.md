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

# 1. 把小说切块入库（输入可以是单文件，也可以是目录）
python scripts/ingest.py --world fanren --input /path/to/novel.txt

# 2. 抽取世界设定
python scripts/extract.py --world fanren

# 3. 合并成结构化世界库
python scripts/merge.py --world fanren

# 4. 建检索索引
python scripts/index.py --world fanren

# 5. 开始玩
python scripts/run_turn.py --world fanren --input "我去坊市打听筑基丹的消息"
```

每个回合 AI 会按以下结构回应：

```
## 场景叙事
## 规则裁定
## 行动结果
## 状态变化
## 世界动态
## 可执行行动
## 自定义行动
```

## 安装为 Skill

把它接到你的 AI 编程助手里，可以在任何对话中触发：

```bash
# Claude Code
python scripts/install.py --target claude --force

# Codex
python scripts/install.py --target codex --force

# 通用 Agent Skills
python scripts/install.py --target agents --force

# 自定义目录（Hermes / OpenClaw 等）
python scripts/install.py --destination /path/to/skills --force
```

安装脚本默认**不会**复制 `worlds/`，避免把小说原文和私设带进公共 Skill 包。

## 目录结构

```text
novel-adventure/
├── SKILL.md                 # Agent Skill 入口
├── README.md
├── scripts/
│   ├── ingest.py            # TXT/MD → 切块
│   ├── extract.py           # 切块 → 设定事实
│   ├── merge.py             # 事实 → 结构化世界库
│   ├── index.py             # 建 SQLite FTS 索引
│   ├── retrieve.py          # 场景检索
│   ├── run_turn.py          # 跑一回合
│   ├── install.py           # 安装为 Skill
│   └── common.py
├── references/              # 抽取 schema、判罚规则、风格指南
└── worlds/                  # 每个 world_slug 一个目录（私有，不入库）
```

`worlds/<slug>/` 会保存：

```text
chunks.jsonl            # 切块文本
facts.jsonl             # 抽取出的设定事实
world_bible.json        # 世界观
power_system.json       # 修炼/能力体系
factions.json           # 势力
locations.json          # 地点
npcs.json               # NPC
timeline.json           # 时间线
adventure_hooks.json    # 冒险钩子
player_state.json       # 玩家存档
canon_patches.jsonl     # 用户校正的设定补丁
retrieval.sqlite        # 检索索引
```

由于可能含**版权文本**和**私设**，`worlds/` 在 `.gitignore` 里，不会被提交。

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
- V1 的 extractor 是**启发式**，质量不如 LLM 蒸馏；可在 `extract.py` 里接 LLM provider 提升
- 中文检索使用 SQLite FTS + LIKE 兜底，适合本地轻量使用
- `worlds/` 可能含版权文本，**不要**公开发布

## 路线图

- [ ] 把 `extract.py` 接入可插拔的 LLM provider
- [ ] EPUB / PDF 导入
- [ ] 多人合作模式（一桌跑团）
- [ ] Web UI（可选）

## 许可

MIT.

如果这个项目让你重新过了一遍《凡人修仙传》或者《诡秘之主》的瘾，欢迎来 issue 区说一声，我会更有动力继续做。
