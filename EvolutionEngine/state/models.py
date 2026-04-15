# -*- coding: utf-8 -*-
"""
L2 演变引擎核心数据模型

定义演变过程中的运行时状态、Tick 记录、Agent 动作等。
"""

import json
from dataclasses import dataclass, field, asdict
from typing import Optional
from datetime import datetime

from WorldEngine.state.models import Entity, Edge, WorldSnapshot


# ─────────────────────────────────────────────────────────
# 实体运行时状态
# ─────────────────────────────────────────────────────────

@dataclass
class EntityLiveState:
    """实体在 L2 演变中的运行时状态"""

    # --- 不可变信息（来自 L1）---
    id: str = ""
    name: str = ""
    type: str = ""                           # "human" | "nature"
    description: str = ""
    agent_prompt: Optional[str] = None       # 仅 human 类有值
    action_space: dict = field(default_factory=dict)  # 仅 human 类有值

    # --- 可变状态 ---
    status: str = ""                         # 当前状态的自然语言描述
    tags: dict = field(default_factory=dict)  # 结构化标签
    last_action: str = ""                    # 上一 tick 执行的动作
    last_action_reasoning: str = ""          # 动作理由
    tick_updated: int = 0                    # 最后更新的 tick

    @classmethod
    def from_entity(cls, entity: Entity) -> "EntityLiveState":
        """从 L1 Entity 构建运行时状态"""
        return cls(
            id=entity.id,
            name=entity.name,
            type=entity.type,
            description=entity.description,
            agent_prompt=entity.agent_prompt,
            action_space=entity.action_space or {},
            status=entity.initial_status,
            tags=dict(entity.initial_tags) if entity.initial_tags else {},
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type,
            "status": self.status,
            "tags": self.tags,
            "last_action": self.last_action,
            "last_action_reasoning": self.last_action_reasoning,
            "tick_updated": self.tick_updated,
        }

    def status_summary(self) -> str:
        """用于传递给 LLM 的简明状态摘要"""
        tags_str = ", ".join(f"{k}: {v}" for k, v in self.tags.items()) if self.tags else ""
        parts = [f"[{self.type}] {self.name} (id: {self.id})"]
        if self.status:
            parts.append(f"状态: {self.status}")
        if tags_str:
            parts.append(f"标签: {tags_str}")
        return " | ".join(parts)


# ─────────────────────────────────────────────────────────
# Agent 动作
# ─────────────────────────────────────────────────────────

@dataclass
class AgentAction:
    """一个人类类 Agent 在某个 tick 执行的动作"""

    agent_id: str = ""
    agent_name: str = ""
    action_type: str = ""                    # "do" | "decide" | "say" | "wait"
    action_description: str = ""
    reasoning: str = ""
    target_entities: list = field(default_factory=list)  # 目标实体名称
    visible_context: str = ""                # Agent 做决策时看到的信息

    def to_dict(self) -> dict:
        return {
            "agent_id": self.agent_id,
            "agent_name": self.agent_name,
            "action_type": self.action_type,
            "action_description": self.action_description,
            "reasoning": self.reasoning,
            "target_entities": self.target_entities,
        }


# ─────────────────────────────────────────────────────────
# 实体状态更新
# ─────────────────────────────────────────────────────────

@dataclass
class EntityUpdate:
    """一次实体状态变更记录"""

    entity_id: str = ""
    entity_name: str = ""
    old_status: str = ""
    new_status: str = ""
    old_tags: dict = field(default_factory=dict)
    new_tags: dict = field(default_factory=dict)
    change_reason: str = ""
    caused_by: list = field(default_factory=list)  # Agent/实体 ID

    def to_dict(self) -> dict:
        return {
            "entity_id": self.entity_id,
            "entity_name": self.entity_name,
            "old_status": self.old_status,
            "new_status": self.new_status,
            "old_tags": self.old_tags,
            "new_tags": self.new_tags,
            "change_reason": self.change_reason,
            "caused_by": self.caused_by,
        }


# ─────────────────────────────────────────────────────────
# Tick 记录
# ─────────────────────────────────────────────────────────

@dataclass
class TickRecord:
    """单个 tick 的完整记录"""

    tick: int = 0

    # --- WorldLLM 规划 ---
    world_assessment: str = ""
    active_agents: list = field(default_factory=list)
    execution_order: list = field(default_factory=list)
    visibility_plan: dict = field(default_factory=dict)

    # --- Agent 决策 ---
    agent_actions: list = field(default_factory=list)  # list[AgentAction]

    # --- WorldLLM 传播结果 ---
    propagation_summary: str = ""
    entity_updates: list = field(default_factory=list)  # list[EntityUpdate]
    world_narrative: str = ""

    timestamp: str = ""

    def to_dict(self) -> dict:
        return {
            "tick": self.tick,
            "world_assessment": self.world_assessment,
            "active_agents": self.active_agents,
            "execution_order": self.execution_order,
            "agent_actions": [a.to_dict() if isinstance(a, AgentAction) else a
                              for a in self.agent_actions],
            "propagation_summary": self.propagation_summary,
            "entity_updates": [u.to_dict() if isinstance(u, EntityUpdate) else u
                               for u in self.entity_updates],
            "world_narrative": self.world_narrative,
            "timestamp": self.timestamp,
        }


# ─────────────────────────────────────────────────────────
# 演变状态 (贯穿整个 L2 过程)
# ─────────────────────────────────────────────────────────

@dataclass
class EvolutionState:
    """L2 演变过程中的可变世界状态"""

    # --- 来源 ---
    world_id: str = ""
    background: str = ""
    focus: str = ""
    world_description: str = ""
    tick_unit: str = ""

    # --- 网络结构（L2 期间不可变）---
    entities: dict = field(default_factory=dict)  # {entity_id: EntityLiveState}
    edges: list = field(default_factory=list)     # list[Edge]

    # --- 演变控制 ---
    current_tick: int = 0
    max_ticks: int = 10
    perturbation: str = ""
    is_terminated: bool = False
    termination_reason: str = ""

    # --- 时间线 ---
    timeline: list = field(default_factory=list)  # list[TickRecord]

    # --- 时间戳 ---
    started_at: str = ""

    @classmethod
    def from_snapshot(
        cls,
        snapshot: WorldSnapshot,
        perturbation: str,
        max_ticks: int = 10,
    ) -> "EvolutionState":
        """从 L1 WorldSnapshot 初始化演变状态"""
        entities = {}
        for entity in snapshot.entities:
            entities[entity.id] = EntityLiveState.from_entity(entity)

        return cls(
            world_id=snapshot.world_id,
            background=snapshot.background,
            focus=snapshot.focus,
            world_description=snapshot.world_description,
            tick_unit=snapshot.tick_unit,
            entities=entities,
            edges=list(snapshot.edges),
            max_ticks=max_ticks,
            perturbation=perturbation,
            started_at=datetime.now().isoformat(),
        )

    def get_human_entities(self) -> dict:
        """返回所有人类类实体"""
        return {eid: e for eid, e in self.entities.items() if e.type == "human"}

    def get_nature_entities(self) -> dict:
        """返回所有自然类实体"""
        return {eid: e for eid, e in self.entities.items() if e.type == "nature"}

    def get_all_status_summary(self) -> str:
        """所有实体的状态摘要（用于传递给 WorldLLM）"""
        lines = []
        for e in self.entities.values():
            lines.append(e.status_summary())
        return "\n".join(lines)

    def get_edges_summary(self) -> str:
        """关系网络摘要"""
        lines = []
        for edge in self.edges:
            src = self.entities.get(edge.source)
            tgt = self.entities.get(edge.target)
            src_name = src.name if src else edge.source
            tgt_name = tgt.name if tgt else edge.target
            lines.append(f"{src_name}({edge.source}) --[{edge.relation}]--> {tgt_name}({edge.target})")
        return "\n".join(lines)

    def apply_updates(self, updates: list, tick: int):
        """应用实体状态变更"""
        for update in updates:
            if not isinstance(update, EntityUpdate):
                continue
            entity = self.entities.get(update.entity_id)
            if entity is None:
                continue
            entity.status = update.new_status
            if update.new_tags:
                entity.tags = update.new_tags
            entity.tick_updated = tick

    def to_dict(self) -> dict:
        return {
            "world_id": self.world_id,
            "background": self.background,
            "focus": self.focus,
            "perturbation": self.perturbation,
            "tick_unit": self.tick_unit,
            "max_ticks": self.max_ticks,
            "current_tick": self.current_tick,
            "is_terminated": self.is_terminated,
            "termination_reason": self.termination_reason,
            "entities": {eid: e.to_dict() for eid, e in self.entities.items()},
            "edges": [e.to_dict() for e in self.edges],
            "timeline": [t.to_dict() for t in self.timeline],
            "started_at": self.started_at,
        }


# ─────────────────────────────────────────────────────────
# 最终输出: 演变时间线
# ─────────────────────────────────────────────────────────

@dataclass
class EvolutionTimeline:
    """L2 最终输出: 完整的演变时间线"""

    world_id: str = ""
    background: str = ""
    focus: str = ""
    perturbation: str = ""
    tick_unit: str = ""

    ticks: list = field(default_factory=list)  # list[TickRecord]
    total_ticks: int = 0

    total_agent_actions: int = 0
    total_entity_updates: int = 0
    most_active_agent: str = ""
    most_changed_entity: str = ""

    started_at: str = ""
    finished_at: str = ""

    def to_dict(self) -> dict:
        return {
            "world_id": self.world_id,
            "background": self.background,
            "focus": self.focus,
            "perturbation": self.perturbation,
            "tick_unit": self.tick_unit,
            "ticks": [t.to_dict() for t in self.ticks],
            "total_ticks": self.total_ticks,
            "total_agent_actions": self.total_agent_actions,
            "total_entity_updates": self.total_entity_updates,
            "most_active_agent": self.most_active_agent,
            "most_changed_entity": self.most_changed_entity,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    def save(self, directory: str) -> str:
        import os
        os.makedirs(directory, exist_ok=True)
        filename = f"evolution_{self.world_id}_{self.perturbation[:20].replace(' ', '_')}.json"
        # 清理文件名中的非法字符
        filename = "".join(c for c in filename if c.isalnum() or c in "._-")
        if not filename.endswith(".json"):
            filename += ".json"
        path = os.path.join(directory, filename)
        with open(path, "w", encoding="utf-8") as f:
            f.write(self.to_json())
        return path
