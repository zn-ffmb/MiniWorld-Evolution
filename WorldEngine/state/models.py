# -*- coding: utf-8 -*-
"""
MiniWorld L1 核心数据模型

定义闭合小世界中的实体、关系边、构建状态和世界快照。
"""

import json
from dataclasses import dataclass, field, asdict
from typing import Optional
from datetime import datetime


@dataclass
class Entity:
    """闭合小世界中的一个实体节点"""
    id: str                              # 唯一标识, 如 "entity_opec"
    name: str                            # 显示名, 如 "OPEC (石油输出国组织)"
    type: str                            # "human" | "nature"
    description: str                     # 实体描述 (来自搜索资料)
    evidence: list[str] = field(default_factory=list)
    source_urls: list[str] = field(default_factory=list)

    # --- L1 Phase 6 后填充 (仅人类类) ---
    agent_prompt: Optional[str] = None
    action_space: dict[str, list[str]] = field(default_factory=dict)

    # --- L1 Phase 7 后填充 ---
    initial_status: str = ""
    initial_tags: dict[str, str] = field(default_factory=dict)

    # --- L1 v3: 证据时效性 ---
    evidence_freshness: str = ""
        # 证据时效性评估: "mostly_fresh" | "mixed" | "mostly_stale" | ""
    evidence_date_range: str = ""
        # 证据时间跨度, 如 "2026-01 ~ 2026-04"
    status_trend: str = ""
        # 状态变化趋势（从时间序列证据中推断）

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Entity":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class Edge:
    """实体间的一条有向关系"""
    source: str                          # 源实体 ID
    target: str                          # 目标实体 ID
    relation: str                        # 关系类型, 如 "控制产能"
    direction: str                       # "directed" | "bidirectional"
    description: str                     # 关系的自然语言描述
    evidence: list[str] = field(default_factory=list)
    source_urls: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Edge":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class SearchRound:
    """一轮搜索的完整记录"""
    iteration: int
    search_queries: list[str] = field(default_factory=list)
    search_tools: list[str] = field(default_factory=list)
    result_count: int = 0
    entities_extracted: list[str] = field(default_factory=list)
    edges_extracted: int = 0
    reasoning: str = ""
    timestamp: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "SearchRound":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class WorldBuildState:
    """L1 构建过程中的全局状态 (贯穿整个迭代)"""

    # --- 输入 ---
    background: str = ""
    focus: str = ""

    # --- 世界图谱 (持续累积) ---
    entities: dict[str, Entity] = field(default_factory=dict)
    edges: list[Edge] = field(default_factory=list)

    # --- 搜索历史 (持续累积) ---
    search_rounds: list[SearchRound] = field(default_factory=list)

    # --- 迭代控制 ---
    iteration: int = 0
    max_iterations: int = 5
    is_converged: bool = False
    convergence_report: str = ""

    # --- 世界元信息 (Phase 7 填充) ---
    world_description: str = ""
    tick_unit: str = ""

    # --- 时间戳 ---
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> dict:
        return {
            "background": self.background,
            "focus": self.focus,
            "entities": {eid: e.to_dict() for eid, e in self.entities.items()},
            "edges": [e.to_dict() for e in self.edges],
            "search_rounds": [sr.to_dict() for sr in self.search_rounds],
            "iteration": self.iteration,
            "max_iterations": self.max_iterations,
            "is_converged": self.is_converged,
            "convergence_report": self.convergence_report,
            "world_description": self.world_description,
            "tick_unit": self.tick_unit,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "WorldBuildState":
        state = cls(
            background=data.get("background", ""),
            focus=data.get("focus", ""),
            iteration=data.get("iteration", 0),
            max_iterations=data.get("max_iterations", 5),
            is_converged=data.get("is_converged", False),
            convergence_report=data.get("convergence_report", ""),
            world_description=data.get("world_description", ""),
            tick_unit=data.get("tick_unit", ""),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
        )
        for eid, edata in data.get("entities", {}).items():
            state.entities[eid] = Entity.from_dict(edata)
        for edata in data.get("edges", []):
            state.edges.append(Edge.from_dict(edata))
        for sr_data in data.get("search_rounds", []):
            state.search_rounds.append(SearchRound.from_dict(sr_data))
        return state

    def save_to_file(self, path: str):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)

    @classmethod
    def load_from_file(cls, path: str) -> "WorldBuildState":
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls.from_dict(data)


@dataclass
class WorldSnapshot:
    """L1 的最终输出: 可持久化的闭合小世界, 供 L2 fork 使用"""

    # --- 元信息 ---
    world_id: str = ""
    background: str = ""
    focus: str = ""
    world_description: str = ""
    tick_unit: str = ""
    created_at: str = ""

    # --- 构建过程摘要 ---
    build_iterations: int = 0
    total_searches: int = 0
    convergence_report: str = ""

    # --- 世界内容 ---
    entities: list[Entity] = field(default_factory=list)
    edges: list[Edge] = field(default_factory=list)

    # --- 统计 ---
    human_entity_count: int = 0
    nature_entity_count: int = 0
    edge_count: int = 0

    # --- v3: 网络结构分析 ---
    network_analysis: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "world_id": self.world_id,
            "background": self.background,
            "focus": self.focus,
            "world_description": self.world_description,
            "tick_unit": self.tick_unit,
            "created_at": self.created_at,
            "build_iterations": self.build_iterations,
            "total_searches": self.total_searches,
            "convergence_report": self.convergence_report,
            "entities": [e.to_dict() for e in self.entities],
            "edges": [e.to_dict() for e in self.edges],
            "human_entity_count": self.human_entity_count,
            "nature_entity_count": self.nature_entity_count,
            "edge_count": self.edge_count,
            "network_analysis": self.network_analysis,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> "WorldSnapshot":
        data = json.loads(json_str)
        return cls.from_dict(data)

    @classmethod
    def from_dict(cls, data: dict) -> "WorldSnapshot":
        snapshot = cls(
            world_id=data.get("world_id", ""),
            background=data.get("background", ""),
            focus=data.get("focus", ""),
            world_description=data.get("world_description", ""),
            tick_unit=data.get("tick_unit", ""),
            created_at=data.get("created_at", ""),
            build_iterations=data.get("build_iterations", 0),
            total_searches=data.get("total_searches", 0),
            convergence_report=data.get("convergence_report", ""),
            human_entity_count=data.get("human_entity_count", 0),
            nature_entity_count=data.get("nature_entity_count", 0),
            edge_count=data.get("edge_count", 0),
            network_analysis=data.get("network_analysis", {}),
        )
        for edata in data.get("entities", []):
            snapshot.entities.append(Entity.from_dict(edata))
        for edata in data.get("edges", []):
            snapshot.edges.append(Edge.from_dict(edata))
        return snapshot

    def save(self, directory: str) -> str:
        import os
        os.makedirs(directory, exist_ok=True)
        filename = f"{self.world_id}.json"
        path = os.path.join(directory, filename)
        with open(path, "w", encoding="utf-8") as f:
            f.write(self.to_json())
        return path

    @classmethod
    def load(cls, path: str) -> "WorldSnapshot":
        with open(path, "r", encoding="utf-8") as f:
            return cls.from_json(f.read())
