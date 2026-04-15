# -*- coding: utf-8 -*-
"""
时间线导出器

将 EvolutionState 转为 EvolutionTimeline，
支持 JSON 和 Markdown 两种格式导出。
"""

import os
from collections import Counter
from datetime import datetime
from loguru import logger

from EvolutionEngine.state.models import (
    EvolutionState,
    EvolutionTimeline,
    AgentAction,
    EntityUpdate,
)


class TimelineExporter:
    """演变时间线导出器"""

    def build_timeline(self, state: EvolutionState) -> EvolutionTimeline:
        """从 EvolutionState 构建 EvolutionTimeline"""
        total_actions = 0
        total_updates = 0
        agent_action_count = Counter()
        entity_update_count = Counter()

        for record in state.timeline:
            for action in record.agent_actions:
                if isinstance(action, AgentAction) and action.action_type != "wait":
                    total_actions += 1
                    agent_action_count[action.agent_name] += 1
            for update in record.entity_updates:
                if isinstance(update, EntityUpdate):
                    total_updates += 1
                    entity_update_count[update.entity_name] += 1

        most_active = agent_action_count.most_common(1)
        most_changed = entity_update_count.most_common(1)

        return EvolutionTimeline(
            world_id=state.world_id,
            background=state.background,
            focus=state.focus,
            perturbation=state.perturbation,
            tick_unit=state.tick_unit,
            ticks=list(state.timeline),
            total_ticks=len(state.timeline),
            total_agent_actions=total_actions,
            total_entity_updates=total_updates,
            most_active_agent=most_active[0][0] if most_active else "",
            most_changed_entity=most_changed[0][0] if most_changed else "",
            started_at=state.started_at,
            finished_at=datetime.now().isoformat(),
        )

    def export_markdown(self, timeline: EvolutionTimeline, state: EvolutionState) -> str:
        """将时间线导出为 Markdown 报告"""
        lines = []

        lines.append(f"# 闭合小世界演变报告\n")
        lines.append(f"> 世界: {timeline.world_id} ({timeline.background} × {timeline.focus})")
        lines.append(f"> 扰动: {timeline.perturbation}")
        lines.append(f"> 时间单位: {timeline.tick_unit}")
        lines.append(f"> 总轮次: {timeline.total_ticks}")
        lines.append(f"> Agent 动作数: {timeline.total_agent_actions}")
        lines.append(f"> 实体变更数: {timeline.total_entity_updates}")
        lines.append(f"> 最活跃 Agent: {timeline.most_active_agent}")
        lines.append(f"> 变化最多的实体: {timeline.most_changed_entity}")
        lines.append("")

        # 演变时间线
        lines.append("## 演变时间线\n")

        for record in timeline.ticks:
            tick = record.tick
            if tick == 0:
                lines.append(f"### Tick 0 — 扰动注入\n")
            else:
                lines.append(f"### Tick {tick}\n")

            # 叙事总结
            if record.world_narrative:
                lines.append(f"{record.world_narrative}\n")

            # Agent 动作
            if record.agent_actions:
                active_actions = [
                    a for a in record.agent_actions
                    if isinstance(a, AgentAction) and a.action_type != "wait"
                ]
                if active_actions:
                    lines.append("**Agent 动作:**\n")
                    for action in active_actions:
                        lines.append(
                            f"- **{action.agent_name}** [{action.action_type}]: "
                            f"{action.action_description}"
                        )
                        if action.reasoning:
                            lines.append(f"  - 理由: {action.reasoning}")
                    lines.append("")

            # 实体状态变更
            if record.entity_updates:
                real_updates = [
                    u for u in record.entity_updates
                    if isinstance(u, EntityUpdate)
                ]
                if real_updates:
                    lines.append("**实体状态变更:**\n")
                    for update in real_updates:
                        lines.append(f"- **{update.entity_name}**:")
                        lines.append(f"  - 旧: {update.old_status[:100]}")
                        lines.append(f"  - 新: {update.new_status[:100]}")
                        if update.change_reason:
                            lines.append(f"  - 原因: {update.change_reason}")
                    lines.append("")

            lines.append("---\n")

        # 最终状态汇总
        lines.append("## 最终实体状态\n")
        lines.append("| 实体 | 类型 | 最终状态 |")
        lines.append("|------|------|----------|")
        for entity in state.entities.values():
            status_short = entity.status[:80] if entity.status else "—"
            lines.append(f"| {entity.name} | {entity.type} | {status_short} |")

        return "\n".join(lines)

    def save(
        self,
        timeline: EvolutionTimeline,
        state: EvolutionState,
        directory: str,
    ) -> tuple:
        """
        保存时间线为 JSON + Markdown。

        Returns:
            (json_path, md_path)
        """
        os.makedirs(directory, exist_ok=True)

        # JSON
        json_path = timeline.save(directory)
        logger.info(f"时间线 JSON 已保存: {json_path}")

        # Markdown
        md_content = self.export_markdown(timeline, state)
        md_path = json_path.replace(".json", ".md")
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(md_content)
        logger.info(f"时间线 Markdown 已保存: {md_path}")

        return json_path, md_path
