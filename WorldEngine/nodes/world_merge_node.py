# -*- coding: utf-8 -*-
"""
Phase 4: 世界网络合并节点

将新提取的实体/边合并到当前世界图中。
纯算法操作，不调用 LLM。
"""

from typing import Any, Dict
from WorldEngine.nodes.base_node import StateMutationNode
from WorldEngine.state.models import WorldBuildState, Entity, Edge


class WorldMergeNode(StateMutationNode):
    """世界网络合并节点 — 纯算法，不调用 LLM"""

    def __init__(self):
        super().__init__(node_name="WorldMergeNode")

    def run(self, input_data: Any, **kwargs) -> Any:
        raise NotImplementedError("请使用 mutate_state()")

    def mutate_state(self, input_data: Dict[str, Any], state: WorldBuildState, **kwargs) -> WorldBuildState:
        """
        将 Phase 3 的提取结果合并到 state 中。

        input_data: {"new_entities": [...], "updated_entities": [...], "new_edges": [...]}
        """
        new_entities = input_data.get("new_entities", [])
        updated_entities = input_data.get("updated_entities", [])
        new_edges = input_data.get("new_edges", [])

        # 1. 新实体: 直接加入 state.entities
        for edata in new_entities:
            entity = Entity(
                id=edata["id"],
                name=edata.get("name", ""),
                type=edata.get("type", "human"),
                description=edata.get("description", ""),
                evidence=edata.get("evidence", []),
                source_urls=edata.get("source_urls", []),
            )
            if entity.id not in state.entities:
                state.entities[entity.id] = entity
                self.log_info(f"新增实体: {entity.name} ({entity.type})")
            else:
                # 如果已存在，合并 evidence
                existing = state.entities[entity.id]
                existing.evidence.extend(edata.get("evidence", []))
                existing.source_urls.extend(edata.get("source_urls", []))
                existing.evidence = list(dict.fromkeys(existing.evidence))
                existing.source_urls = list(dict.fromkeys(existing.source_urls))

        # 2. 已有实体: 合并 evidence
        for update in updated_entities:
            eid = update.get("id", "")
            if eid in state.entities:
                existing = state.entities[eid]
                existing.evidence.extend(update.get("additional_evidence", []))
                existing.source_urls.extend(update.get("additional_source_urls", []))
                existing.evidence = list(dict.fromkeys(existing.evidence))
                existing.source_urls = list(dict.fromkeys(existing.source_urls))

        # 3. 新边: 检查是否重复 (同 source+target+relation 视为重复)
        for edata in new_edges:
            edge = Edge(
                source=edata.get("source", ""),
                target=edata.get("target", ""),
                relation=edata.get("relation", ""),
                direction=edata.get("direction", "directed"),
                description=edata.get("description", ""),
                evidence=edata.get("evidence", []),
                source_urls=edata.get("source_urls", []),
            )
            existing_edge = self._find_edge(state.edges, edge)
            if existing_edge is None:
                state.edges.append(edge)
                self.log_info(f"新增关系: {edge.source} --[{edge.relation}]--> {edge.target}")
            else:
                # 合并 evidence
                existing_edge.evidence.extend(edge.evidence)
                existing_edge.source_urls.extend(edge.source_urls)
                existing_edge.evidence = list(dict.fromkeys(existing_edge.evidence))
                existing_edge.source_urls = list(dict.fromkeys(existing_edge.source_urls))

        # 4. 清理: 移除引用了不存在实体的边
        valid_ids = set(state.entities.keys())
        before_count = len(state.edges)
        state.edges = [e for e in state.edges if e.source in valid_ids and e.target in valid_ids]
        removed = before_count - len(state.edges)
        if removed > 0:
            self.log_warning(f"移除 {removed} 条引用不存在实体的边")

        return state

    @staticmethod
    def _find_edge(edges: list, new_edge: Edge):
        """查找是否已存在相同的边 (source + target + relation)"""
        for e in edges:
            if e.source == new_edge.source and e.target == new_edge.target and e.relation == new_edge.relation:
                return e
        return None
