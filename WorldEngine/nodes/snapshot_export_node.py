# -*- coding: utf-8 -*-
"""
Phase 8: 快照导出节点

将 WorldBuildState 转化为 WorldSnapshot 并持久化。
输出 JSON 快照 + Markdown 可读报告。
"""

import os
from datetime import datetime
from typing import Any
from WorldEngine.nodes.base_node import BaseNode
from WorldEngine.state.models import WorldBuildState, WorldSnapshot


class SnapshotExportNode(BaseNode):
    """快照导出节点 — 纯数据组装"""

    def __init__(self):
        super().__init__(node_name="SnapshotExportNode")

    def run(self, input_data: Any, **kwargs) -> Any:
        raise NotImplementedError("请使用 export()")

    def export(self, state: WorldBuildState, network_analysis: dict = None) -> WorldSnapshot:
        """将 WorldBuildState 转化为 WorldSnapshot"""
        snapshot = WorldSnapshot(
            world_id=f"world_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            background=state.background,
            focus=state.focus,
            world_description=state.world_description,
            tick_unit=state.tick_unit,
            created_at=datetime.now().isoformat(),
            build_iterations=state.iteration,
            total_searches=sum(sr.result_count for sr in state.search_rounds),
            convergence_report=state.convergence_report,
            entities=list(state.entities.values()),
            edges=state.edges,
            human_entity_count=sum(1 for e in state.entities.values() if e.type == "human"),
            nature_entity_count=sum(1 for e in state.entities.values() if e.type == "nature"),
            edge_count=len(state.edges),
            network_analysis=network_analysis or {},
        )
        return snapshot

    def export_markdown_report(self, snapshot: WorldSnapshot) -> str:
        """生成人类可读的世界构建报告 Markdown"""
        lines = []

        lines.append(f"# 闭合小世界构建报告: {snapshot.background} × {snapshot.focus}")
        lines.append("")
        lines.append(f"> 世界ID: {snapshot.world_id}  ")
        lines.append(f"> 构建时间: {snapshot.created_at}  ")
        lines.append(f"> 构建轮次: {snapshot.build_iterations} 轮  ")
        lines.append(f"> 收敛状态: {snapshot.convergence_report}")
        lines.append("")

        lines.append("## 世界概述")
        lines.append("")
        lines.append(snapshot.world_description)
        lines.append("")
        lines.append(f"**Tick 时间单位**: {snapshot.tick_unit}")
        lines.append("")

        lines.append("## 实体总览")
        lines.append("")
        lines.append("| 类型 | 数量 |")
        lines.append("|------|------|")
        lines.append(f"| 人类类实体 | {snapshot.human_entity_count} |")
        lines.append(f"| 自然类实体 | {snapshot.nature_entity_count} |")
        lines.append(f"| 关系边 | {snapshot.edge_count} |")
        lines.append("")

        # 人类类实体
        human_entities = [e for e in snapshot.entities if e.type == "human"]
        if human_entities:
            lines.append("## 人类类实体")
            lines.append("")
            for entity in human_entities:
                lines.append(f"### {entity.name}")
                lines.append(f"- **描述**: {entity.description}")
                lines.append(f"- **初始状态**: {entity.initial_status}")
                if entity.action_space:
                    lines.append("- **动作空间**:")
                    for action_type, label in [("do", "做"), ("decide", "定"), ("say", "说")]:
                        cap = entity.action_space.get(action_type)
                        if isinstance(cap, list):
                            # v1 格式兼容
                            for action in cap:
                                lines.append(f"  - {label}: {action}")
                        elif isinstance(cap, dict) and cap.get("enabled", False):
                            scope = cap.get("scope", "")
                            targets = cap.get("influence_targets", [])
                            constraints = cap.get("constraints", "")
                            line = f"  - {label}: {scope}"
                            if targets:
                                line += f" → 可影响: {', '.join(targets)}"
                            if constraints:
                                line += f" （{constraints}）"
                            lines.append(line)
                if entity.evidence:
                    lines.append(f"- **关键证据**: {entity.evidence[0][:200]}...")
                if entity.source_urls:
                    lines.append(f"- **来源**: {', '.join(entity.source_urls[:3])}")
                lines.append("")

        # 自然类实体
        nature_entities = [e for e in snapshot.entities if e.type == "nature"]
        if nature_entities:
            lines.append("## 自然类实体")
            lines.append("")
            for entity in nature_entities:
                lines.append(f"### {entity.name}")
                lines.append(f"- **描述**: {entity.description}")
                lines.append(f"- **初始状态**: {entity.initial_status}")
                if entity.initial_tags:
                    tags_str = ", ".join(f"{k}: {v}" for k, v in entity.initial_tags.items())
                    lines.append(f"- **标签**: {tags_str}")
                if entity.evidence:
                    lines.append(f"- **关键证据**: {entity.evidence[0][:200]}...")
                lines.append("")

        # 关系网络
        lines.append("## 关系网络")
        lines.append("")
        lines.append("| 源实体 | → 关系 | 目标实体 | 方向 |")
        lines.append("|--------|--------|----------|------|")

        # 构建 ID → 名称映射
        id_to_name = {e.id: e.name for e in snapshot.entities}
        for edge in snapshot.edges:
            source_name = id_to_name.get(edge.source, edge.source)
            target_name = id_to_name.get(edge.target, edge.target)
            lines.append(f"| {source_name} | {edge.relation} | {target_name} | {edge.direction} |")
        lines.append("")

        return "\n".join(lines)
