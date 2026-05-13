#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from typing import Any

from action_intent import action_intent_lines, analyze_action
from action_resolver import resolve_action
from arc_runtime import advance_arc_attention, arc_state_lines
from canon_evidence import evidence_lines
from common import default_player_state, migrate_player_state, write_json, world_dir
from director import advance_director
from equipment_sets import refresh_player_set_bonuses
from foreshadow_runtime import advance_foreshadows
from game_math import computed_stats
from journal import journal_lines, update_journal, write_journal_markdown
from npc_agency import advance_npc_agency
from quest_lifecycle import advance_quest_lifecycle, quest_lifecycle_lines
from retrieve import retrieve
from reward_policy import record_reward_channel, reward_policy_lines
from rpg_profile import apply_rpg_profile_to_state, format_stat_block, load_rpg_profile
from runtime_layers import record_runtime_layers, runtime_layer_lines
from runtime_summary import runtime_summary_lines
from save_manager import load_save, save_path, write_save
from scene_engine import current_scene, scene_lines, scene_options
from scene_state import advance_scene_state, scene_state_lines
from world_events import advance_world_events


HIGH_RISK_WORDS = ("硬闯", "强闯", "击杀", "挑战", "突破", "偷袭", "抢夺", "潜入", "威胁", "追杀")
INFO_WORDS = ("打听", "询问", "调查", "观察", "探查", "侦查")
CULTIVATION_WORDS = ("修炼", "闭关", "突破", "炼化", "冲关")
TRADE_WORDS = ("购买", "交易", "出售", "买", "卖")
DECLARED_SUCCESS_WORDS = ("直接成功", "一定成功", "秒杀", "无敌", "立刻突破", "马上成仙", "随便拿走")
BLOCKING_MARKERS = ("不可", "不能", "禁止", "无法", "必须", "需要", "代价", "风险", "失败")
BAD_ENTITY_NAMES = {"不会", "没有理会", "这种等级", "听得药", "当前", "对方", "什么", "卷轴"}
BAD_OPTION_PHRASES = (
    "收集地点、人物和风险情报",
    "选择低风险入口或准备路线",
    "完成第一个可验证的小目标",
    "选择一个低风险行动入口",
)
OPTION_SELECTION_RE = re.compile(r"^\s*\d+(?:\s*[,，.。、\s]\s*\d+)*\s*$")


def looks_like_bad_name(name: str) -> bool:
    stripped = name.strip()
    if not stripped or stripped in BAD_ENTITY_NAMES:
        return True
    if len(stripped) > 18:
        return True
    return any(mark in stripped for mark in ("。", "，", "；", "：", "？", "！", "\n"))


def looks_like_raw_excerpt(claim: str) -> bool:
    stripped = claim.strip()
    if not stripped:
        return True
    if stripped.startswith(("，", "。", "；", "：", "“", "”", "\"", "'")):
        return True
    quote_count = stripped.count("“") + stripped.count("”") + stripped.count("\"")
    return len(stripped) > 120 and quote_count >= 2


def display_claim(claim: str) -> str:
    stripped = claim.strip()
    for marker in ("当玩家围绕", "失败会带来", "可执行动作", "前置条件"):
        idx = stripped.find(marker)
        if idx > 12:
            return stripped[idx:]
    return stripped


def humanize_option(option: str, state: dict[str, Any]) -> str:
    location = state.get("meta", {}).get("current_location", "当前位置")
    replacements = {
        "收集地点、人物和风险情报": f"在{location}找摊主、杂役或守卫问一条具体线索。",
        "选择低风险入口或准备路线": "先问清入口、报酬和撤退路线，再决定是否接活。",
        "完成第一个可验证的小目标": "带回一条能交差的消息、价格或人物行踪。",
        "选择一个低风险行动入口": "从问价、送信或带路这种低风险小事开始。",
    }
    cleaned = option.strip()
    for bad, replacement in replacements.items():
        cleaned = cleaned.replace(bad, replacement)
    while "。。" in cleaned:
        cleaned = cleaned.replace("。。", "。")
    return cleaned


def option_selection_indexes(player_input: str) -> list[int]:
    if not OPTION_SELECTION_RE.fullmatch(player_input or ""):
        return []
    compact = str(player_input or "").strip()
    if compact.isdigit() and len(compact) > 1:
        return [int(char) for char in compact]
    indexes: list[int] = []
    for token in re.split(r"[,，.。、\s]+", player_input.strip()):
        if not token:
            continue
        try:
            indexes.append(int(token.strip()))
        except ValueError:
            return []
    return indexes


def resolve_numbered_option(player_input: str, state: dict[str, Any]) -> tuple[str, list[dict[str, Any]], str]:
    indexes = option_selection_indexes(player_input)
    if not indexes:
        return player_input, [], ""
    last_options = state.get("meta", {}).get("last_options", [])
    if not isinstance(last_options, list) or not last_options:
        return player_input, [], "没有可用的上一回合选项；按原始输入处理。"
    selected: list[dict[str, Any]] = []
    for index in indexes:
        if index < 1 or index > len(last_options):
            continue
        option = last_options[index - 1]
        if isinstance(option, dict) and option.get("text"):
            selected.append(option)
    if not selected:
        return player_input, [], "选择编号无效；按原始输入处理。"
    resolved = "；".join(str(option.get("text")) for option in selected)
    return resolved, selected, ""


def is_multi_numbered_selection(player_input: str) -> list[int]:
    indexes = option_selection_indexes(player_input)
    return indexes if len(indexes) > 1 else []


def format_existing_options(state: dict[str, Any]) -> list[str]:
    rows = state.get("meta", {}).get("last_options", [])
    if not isinstance(rows, list):
        return []
    return [str(row.get("text")) for row in rows if isinstance(row, dict) and row.get("text")]


def infer_option_intent(option: str) -> str:
    text = str(option)
    if "推进当前任务" in text:
        return "quest"
    if any(word in text for word in ("整理背包", "查看行囊", "清点资源", "状态")):
        return "inventory"
    if any(word in text for word in ("辅助资源", "资源来源", "提高效率", "低阶药材", "药液价格")):
        return "info"
    if any(word in text for word in ("复盘", "练习", "吐纳", "运转斗气", "低风险练习")):
        return "cultivation"
    if any(word in text for word in ("搬运", "沙袋", "清扫", "器械", "杂务", "旁听名额", "旁听资格", "旁听")):
        return "quest"
    if "追问" in text:
        return "info"
    if any(word in text for word in ("支付", "金币", "筹码", "承诺", "指点", "护法", "指导", "NPC", "炼药师", "对方", "搭话", "规矩", "代价")):
        return "social"
    if any(word in text for word in ("任务", "委托", "跑腿", "核价", "送信", "传话", "报酬", "追踪", "交差")):
        return "quest"
    if any(word in text for word in ("购买", "交易", "价格", "卖家", "拍卖")):
        return "trade"
    if any(word in text for word in ("前往", "进入", "转向", "地点", "路线", "撤退路线", "探索", "安全修炼地点")):
        return "location"
    if any(word in text for word in ("使用", "服用", "装备", "行囊", "背包", "整理")):
        return "inventory"
    if any(word in text for word in ("修炼", "突破", "闭关", "稳步")):
        return "cultivation"
    if any(word in text for word in ("追问", "打听", "询问", "确认", "观察", "情报", "线索", "问清")):
        return "info"
    return "general"


def selected_option_intent(selected_options: list[dict[str, Any]]) -> str | None:
    intents = [str(option.get("intent", "")) for option in selected_options if option.get("intent")]
    concrete = [intent for intent in intents if intent and intent != "general"]
    if not concrete:
        return None
    return concrete[0]


def summarize_canon(rows: list[dict[str, Any]]) -> list[str]:
    lines = []
    seen: set[tuple[str, str]] = set()
    hidden_runtime_types = {
        "story_arc",
        "event_chain",
        "npc_motive",
        "ability_boundary",
        "foreshadowing",
        "evidence_card",
    }
    hidden_sources = {
        "story_arcs.json",
        "event_chains.json",
        "npc_motives.json",
        "ability_boundaries.json",
        "foreshadowing.json",
        "evidence_cards.json",
    }
    for row in rows:
        row_type = str(row.get("type", ""))
        if row_type.startswith("playable_"):
            continue
        if row_type in hidden_runtime_types or str(row.get("source_json", "")) in hidden_sources:
            continue
        name = str(row.get("name", ""))
        if looks_like_bad_name(name):
            continue
        key = (row_type, name)
        if key in seen:
            continue
        seen.add(key)
        claim = display_claim(row.get("claim", "").strip())
        if looks_like_raw_excerpt(claim):
            continue
        if claim:
            lines.append(f"- [{row_type}] {name}: {claim[:100]}")
        if len(lines) >= 3:
            break
    return lines


def compact_message(message: str, limit: int = 120) -> str:
    text = str(message or "").replace("\n", " ").strip()
    text = re.sub(r"\s+", " ", text)
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip("，。；： ") + "…"


def summarize_world_dynamics(
    canon_rows: list[dict[str, Any]],
    foreshadow_messages: list[str],
    event_messages: list[str],
) -> list[str]:
    lines: list[str] = []
    for message in event_messages[:2]:
        text = compact_message(message)
        if text:
            lines.append(f"- {text}")
    for message in foreshadow_messages[:2]:
        text = compact_message(message)
        if text and text not in lines:
            lines.append(f"- {text}")
    if lines:
        return lines[:4]
    canon_lines = summarize_canon(canon_rows)
    if canon_lines:
        return canon_lines[:2]
    return ["- 本回合没有新的外部世界事件；局势按当前地点和行动后果小幅推进。"]


def summarize_playable(rows: list[dict[str, Any]]) -> list[str]:
    lines = []
    seen_names: set[str] = set()
    for row in rows:
        row_type = str(row.get("type", ""))
        if not row_type.startswith("playable_"):
            continue
        name = str(row.get("name", ""))
        if looks_like_bad_name(name):
            continue
        if name in seen_names:
            continue
        seen_names.add(name)
        claim = display_claim(row.get("claim", "").strip())
        if looks_like_raw_excerpt(claim):
            continue
        if claim:
            lines.append(f"- [{row_type}] {name}: {claim[:180]}")
        if len(lines) >= 4:
            break
    return lines


def adjudicate_action(player_input: str, state: dict[str, Any], canon_rows: list[dict[str, Any]]) -> dict[str, str]:
    hard_claims = " ".join(row.get("claim", "") for row in canon_rows if row.get("type") == "canon_patch")
    all_claims = hard_claims + " " + " ".join(row.get("claim", "") for row in canon_rows[:10])
    player = state.get("player", {})
    realm = str(player.get("realm_or_level", player.get("realm", "")))
    status = "allowed"
    verdict = "可执行"
    consequence = "行动被纳入当前场景推进，世界会根据已检索到的设定给出相应反馈。"

    if any(word in player_input for word in DECLARED_SUCCESS_WORDS):
        status = "blocked"
        verdict = "声明式成功无效"
        consequence = "你不能直接声明结果；本回合只裁定你的尝试，并根据 canon、状态和风险决定后果。"
    elif any(word in player_input for word in HIGH_RISK_WORDS) and any(word in all_claims for word in BLOCKING_MARKERS):
        status = "partial_or_blocked"
        verdict = "高风险行动需要前置条件"
        consequence = "你的行动触碰了当前世界硬规则或高风险边界，不能直接成功；本回合转为试探、准备或寻找替代路径。"
    elif any(word in player_input for word in INFO_WORDS):
        status = "allowed"
        verdict = "信息行动可执行但消耗时间"
        consequence = "你放慢节奏收集信息，获得了更清晰的局势判断，但也消耗了一段时间。"
    elif any(word in player_input for word in TRADE_WORDS):
        status = "conditional"
        verdict = "交易行动受价格、稀缺度和势力关系影响"
        consequence = "交易行动展开；价格、真假和旁人觊觎会根据当地势力与物品稀缺度变化。"
    elif any(word in player_input for word in CULTIVATION_WORDS):
        status = "conditional"
        verdict = "修炼行动受境界、资源和地点限制"
        consequence = "你尝试运转力量体系内的修炼路径，进展取决于资源、地点安全和当前境界限制。"

    if "凡人" in realm and any(word in player_input for word in ("御剑", "飞行", "天劫", "元婴", "金丹")):
        status = "blocked"
        verdict = "当前实力不支持该行动"
        consequence = "以你当前层级无法直接完成这个行动；你需要先获得外物、导师、情报或更低风险的路径。"

    return {"status": status, "verdict": verdict, "consequence": consequence}


def build_options(
    player_input: str,
    state: dict[str, Any],
    canon_rows: list[dict[str, Any]],
    resolution: dict[str, Any],
    scene: dict[str, Any],
) -> list[str]:
    blocked_background_objectives = background_objective_texts(state)
    raw_options = [option for option in resolution.get("options", []) if str(option) not in blocked_background_objectives]
    resolved_options = collapse_task_objective_options(state, list(raw_options))
    scene_generated_options = scene_options(scene, state)
    if should_prioritize_resolution_options(resolution, state, resolved_options):
        options = [*resolved_options, *scene_generated_options]
    else:
        options = [*scene_generated_options, *resolved_options]
    for row in canon_rows:
        if "hook" in row.get("type", "") or row.get("source_json") == "adventure_hooks.json":
            options.append(f"追踪冒险钩子：{row.get('name')}。")
            break
    deduped: list[str] = []
    for option in options:
        option = humanize_option(str(option), state)
        if option and option not in deduped:
            deduped.append(option)
        if len(deduped) >= 5:
            break
    return deduped


def should_prioritize_resolution_options(resolution: dict[str, Any], state: dict[str, Any], options: list[str]) -> bool:
    kind = str(resolution.get("kind", ""))
    status = str(resolution.get("status", ""))
    if status in {"blocked", "partial_or_blocked"}:
        return True
    if kind in {"combat", "inventory", "trade"}:
        return True
    if kind in {"social", "location"} and status in {"resolved", "allowed"} and options:
        return True
    if kind == "quest" and options:
        return True
    return bool(active_objective_texts(state))


def free_roam_options(state: dict[str, Any], canon_rows: list[dict[str, Any]]) -> list[str]:
    location = state.get("meta", {}).get("current_location", "当前位置")
    options = [
        f"观察{location}当前局势，确认可互动人物、风险和机会。",
        "找一个具体 NPC 搭话，询问规矩、资源、委托或传闻。",
        "进行一次低风险训练或休整，检查当前状态能否承受修炼。",
        "清点背包、金币和关系，决定要买、卖、修炼还是换情报。",
    ]
    for row in canon_rows:
        row_type = str(row.get("type", ""))
        name = str(row.get("name", ""))
        if name and not looks_like_bad_name(name) and (row_type == "location" or "location" in row_type):
            options.append(f"转向与「{name}」相关的地点线索。")
            break
    return options


def is_background_quest(quest: dict[str, Any]) -> bool:
    return quest.get("source") == "story_arcs.json" or bool(quest.get("story_arc_id"))


def active_objective_texts(state: dict[str, Any]) -> set[str]:
    texts: set[str] = set()
    for quest in state.get("active_quests", []):
        if not isinstance(quest, dict) or quest.get("status") != "active":
            continue
        if is_background_quest(quest):
            continue
        for objective in quest.get("objectives", []):
            if isinstance(objective, dict) and objective.get("text"):
                texts.add(str(objective.get("text")))
    return texts


def background_objective_texts(state: dict[str, Any]) -> set[str]:
    texts: set[str] = set()
    for quest in state.get("active_quests", []):
        if not isinstance(quest, dict) or quest.get("status") != "active":
            continue
        if not is_background_quest(quest):
            continue
        for objective in quest.get("objectives", []):
            if isinstance(objective, dict) and objective.get("text"):
                texts.add(str(objective.get("text")))
    return texts


def next_active_objective(state: dict[str, Any]) -> str:
    for quest in state.get("active_quests", []):
        if not isinstance(quest, dict) or quest.get("status") != "active":
            continue
        if is_background_quest(quest):
            continue
        for objective in quest.get("objectives", []):
            if isinstance(objective, dict) and not objective.get("done") and objective.get("text"):
                return str(objective.get("text"))
    return ""


def collapse_task_objective_options(state: dict[str, Any], options: list[str]) -> list[str]:
    objective_texts = active_objective_texts(state)
    if not objective_texts:
        return options
    collapsed: list[str] = []
    inserted = False
    for option in options:
        text = str(option)
        if text in objective_texts:
            if not inserted:
                current = next_active_objective(state)
                collapsed.append(f"推进当前任务（下一目标：{current}）。" if current else "推进当前任务。")
                inserted = True
            continue
        collapsed.append(text)
    return collapsed


def summarize_active_tasks(state: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    for quest in state.get("active_quests", []):
        if not isinstance(quest, dict) or quest.get("status") != "active":
            continue
        if is_background_quest(quest):
            continue
        name = str(quest.get("name") or "当前任务")
        done = []
        pending = []
        for objective in quest.get("objectives", []):
            if not isinstance(objective, dict) or not objective.get("text"):
                continue
            (done if objective.get("done") else pending).append(str(objective.get("text")))
        if pending:
            lines.append(f"- {name}：下一目标：{pending[0]}")
        elif done:
            lines.append(f"- {name}：等待结算或交付。")
        if len(lines) >= 4:
            break
    return lines


def summarize_long_term_threads(state: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    for quest in state.get("active_quests", []):
        if not isinstance(quest, dict) or quest.get("status") != "active":
            continue
        if not is_background_quest(quest):
            continue
        name = str(quest.get("name") or "长期线索")
        pending = []
        for objective in quest.get("objectives", []):
            if isinstance(objective, dict) and not objective.get("done") and objective.get("text"):
                pending.append(str(objective.get("text")))
        if pending:
            lines.append(f"- {name}：可继续关注「{pending[0]}」，但不会自动绑架当前行动。")
        else:
            lines.append(f"- {name}：已阶段性完成，可等待新线索。")
        if len(lines) >= 3:
            break
    return lines


def run_turn(
    world: str,
    player_input: str,
    limit: int,
    dry_run: bool,
    slot: str | None = None,
    _forced_kind: str | None = None,
) -> str:
    multi_indexes = is_multi_numbered_selection(player_input)
    if multi_indexes:
        snapshot_state = migrate_player_state(load_save(world, slot, default_player_state(world)), world)
        snapshot_options = snapshot_state.get("meta", {}).get("last_options", [])
        if not isinstance(snapshot_options, list) or not snapshot_options:
            return "没有可用的上一回合选项；多编号输入未执行，也没有消耗回合。"

        outputs: list[str] = []
        for idx, option_index in enumerate(multi_indexes, 1):
            if option_index < 1 or option_index > len(snapshot_options):
                outputs.append(
                    f"## 连续行动中止\n\n编号 {option_index} 超出当前可选范围 1-{len(snapshot_options)}；"
                    "该编号及后续编号未执行，也没有额外消耗回合。"
                )
                break
            option = snapshot_options[option_index - 1]
            if not isinstance(option, dict) or not option.get("text"):
                outputs.append(f"## 连续行动中止\n\n编号 {option_index} 没有可执行文本；后续编号未执行。")
                break
            selected_text = str(option["text"])
            selected_intent = str(option.get("intent") or "") or None
            result = run_turn(world, selected_text, limit, dry_run, slot, _forced_kind=selected_intent)
            outputs.append(f"## 连续行动 {idx}/{len(multi_indexes)}：选择 {option_index}\n\n{result}")
            if "状态：blocked" in result:
                outputs.append("## 连续行动中止\n\n上一行动被阻止，后续编号没有继续执行。")
                break
        return "\n\n---\n\n".join(outputs)

    wdir = world_dir(world)
    state_path = save_path(world, slot)
    state = migrate_player_state(load_save(world, slot, default_player_state(world)), world)
    rpg_profile = load_rpg_profile(world)
    state = apply_rpg_profile_to_state(state, rpg_profile)
    refresh_player_set_bonuses(world, state)
    meta = state.setdefault("meta", {})
    player = state.setdefault("player", {})
    raw_player_input = player_input
    selected_options: list[dict[str, Any]]
    option_warning: str
    player_input, selected_options, option_warning = resolve_numbered_option(player_input, state)
    forced_kind = _forced_kind or selected_option_intent(selected_options)
    query = " ".join(
        [
            player_input,
            str(meta.get("current_location", "")),
            str(meta.get("current_stage", "")),
            str(player.get("realm_or_level", "")),
        ]
    )
    canon_rows = retrieve(world, query, limit)
    scene = current_scene(world, state, canon_rows)
    intent = analyze_action(player_input, forced_kind, scene)
    resolution = resolve_action(world, player_input, state, canon_rows, forced_kind=forced_kind)
    resolution_kind = str(resolution.get("kind") or "")
    if resolution_kind and resolution_kind != "general" and intent.get("kind") != resolution_kind:
        intent = analyze_action(player_input, resolution_kind, scene)
    result = resolution["consequence"]
    before_turn = int(meta.get("turn", 0))
    turn = before_turn + 1
    meta["turn"] = turn
    foreshadow_messages, foreshadow_options = advance_foreshadows(world, state, player_input, canon_rows)
    event_messages, event_options, event_data = advance_world_events(world, state, player_input, dry_run)
    scene_messages = advance_scene_state(state, scene, player_input, resolution, intent)
    arc_messages = advance_arc_attention(state, player_input, resolution)
    layer_messages = record_runtime_layers(state, canon_rows, resolution, turn, player_input)
    lifecycle_messages = advance_quest_lifecycle(state)
    director_lines, director_options = advance_director(world, state, scene, resolution, turn)
    npc_agency_lines, npc_agency_options = advance_npc_agency(world, state, scene, turn, resolution)
    reward_messages = record_reward_channel(world, state, resolution, turn)

    state_changes = [
        f"回合数：{before_turn} -> {turn}",
        *([f"编号选择：{raw_player_input} -> {player_input}"] if selected_options else []),
        *([f"选项意图：{forced_kind}"] if forced_kind else []),
        *([option_warning] if option_warning else []),
        *resolution.get("state_changes", []),
        *scene_messages,
        *arc_messages,
        *lifecycle_messages,
        *layer_messages,
        *reward_messages,
        *foreshadow_messages,
        *event_messages,
    ]
    journal_messages = update_journal(state, player_input, resolution, state_changes, turn)
    state_changes = [
        *state_changes,
        *journal_messages,
        "行动记录已追加。" if not dry_run else "dry-run 未写入行动记录。",
    ]
    meta["current_stage"] = "自由冒险推进中"
    state.setdefault("action_log", []).append(
        {
            "turn": turn,
            "raw_action": raw_player_input,
            "action": player_input,
            "selected_options": selected_options,
            "forced_kind": forced_kind,
            "result": result,
            "resolution": {
                "kind": resolution.get("kind"),
                "status": resolution.get("status"),
                "verdict": resolution.get("verdict"),
            },
            "canon_used": [row.get("id") for row in canon_rows[:8]],
        }
    )
    state["action_log"] = state["action_log"][-30:]

    dynamic_lines = summarize_world_dynamics(canon_rows, foreshadow_messages, event_messages)
    playable_lines = summarize_playable(canon_rows)
    scene_summary_lines = scene_lines(scene)
    persistent_scene_lines = scene_state_lines(state, scene)
    stats = computed_stats(state)
    options = []
    for option in foreshadow_options:
        if option not in options:
            options.append(option)
    for option in build_options(player_input, state, canon_rows, resolution, scene):
        if option not in options:
            options.append(option)
    for option in director_options:
        if option not in options:
            options.append(option)
    for option in npc_agency_options:
        if option not in options:
            options.append(option)
    for option in event_options:
        if option not in options:
            options.append(option)
    options = options[:5]
    task_lines = summarize_active_tasks(state)
    thread_lines = summarize_long_term_threads(state)
    arc_runtime_lines = arc_state_lines(state)
    evidence_summary_lines = evidence_lines(canon_rows, resolution)
    layer_summary_lines = runtime_layer_lines(state)
    lifecycle_summary_lines = quest_lifecycle_lines(state)
    reward_summary_lines = reward_policy_lines(state)
    journal_summary_lines = journal_lines(state)
    meta["last_options"] = [
        {
            "index": idx,
            "id": f"turn_{turn}_option_{idx}",
            "text": option,
            "intent": infer_option_intent(option),
        }
        for idx, option in enumerate(options, 1)
    ]
    if not dry_run:
        write_save(world, slot, state)
        for filename, data in resolution.get("runtime_files", {}).items():
            write_json(wdir / filename, data)
        write_json(wdir / "world_events.json", event_data)
        write_journal_markdown(world, state, slot)
    output = [
        "## 场景叙事",
        f"你选择：{player_input}" if raw_player_input == player_input else f"你选择：{raw_player_input}（{player_input}）",
        "当前世界以检索到的设定为边界推进。相关规则和线索在暗处收束，场景不会脱离既有 canon。",
        "",
        "## 规则裁定",
        f"- 行动类型：{resolution.get('kind', 'general')}",
        f"- 裁定：{resolution['verdict']}",
        f"- 状态：{resolution['status']}",
        "",
        "## Canon 证据",
        *evidence_summary_lines,
        "",
        "## 行动拆解",
        *action_intent_lines(intent),
        "",
        "## 行动结果",
        result,
        "",
        "## 当前场景",
        *scene_summary_lines,
        "",
        "## 场景状态",
        *persistent_scene_lines,
        "",
        "## 状态变化",
        *[f"- {line}" for line in state_changes],
        f"- 存档：{state_path}",
        "",
        "## 人物属性",
        *format_stat_block(stats, rpg_profile),
        "",
        "## RPG运行态",
        *runtime_summary_lines(state),
        "",
        "## 潜在收益",
        *reward_summary_lines,
        "",
        "## 运行时分层",
        *layer_summary_lines,
        "",
        "## 任务阶段",
        *lifecycle_summary_lines,
        "",
        "## 节奏与机会",
        *director_lines,
        "",
        "## 人物动向",
        *(npc_agency_lines or ["- 暂无人物主动插手；当前不打断你的自由行动。"]),
        "",
        "## 冒险日志",
        *journal_summary_lines,
        "",
        "## 世界动态",
        *dynamic_lines,
        "",
        "## 主持约束",
        *(playable_lines or ["- 未检索到额外可玩规则；按基础 canon、状态和风险裁定。"]),
        "",
        "## 当前任务",
        *(task_lines or ["- 暂无进行中的任务。"]),
        "",
        "## 长期线索",
        *(thread_lines or ["- 暂无被追踪的长期线索。"]),
        *arc_runtime_lines,
        "",
        "## 可执行行动",
        *[f"{idx}. {option}" for idx, option in enumerate(options, 1)],
        "",
        "## 自定义行动",
        "你也可以输入任意自定义行动；下一回合会先检索相关 canon，再判断结果。",
    ]
    return "\n".join(output)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run one text adventure turn using retrieved canon.")
    parser.add_argument("--world", required=True)
    parser.add_argument("--input", required=True)
    parser.add_argument("--slot", help="Named save slot. Default uses player_state.json.")
    parser.add_argument("--limit", type=int, default=30)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    print(run_turn(args.world, args.input, args.limit, args.dry_run, args.slot))


if __name__ == "__main__":
    main()
