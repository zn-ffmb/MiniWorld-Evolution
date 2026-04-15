# -*- coding: utf-8 -*-
"""
Phase 5: 闭合收敛检测节点

三级收敛检测:
  Level 1: 结构完整性 (算法 — NetworkX)
  Level 2: 功能完整性 (算法)
  Level 3: 语义完整性 (LLM 反思)
"""

import json
from typing import Any, Dict, Tuple
import networkx as nx
from loguru import logger

from WorldEngine.nodes.base_node import BaseNode
from WorldEngine.state.models import WorldBuildState, Entity, Edge
from WorldEngine.prompts.prompts import SEMANTIC_CHECK_SYSTEM_PROMPT
from WorldEngine.utils.text_processing import extract_clean_response


class ConvergenceCheckNode(BaseNode):
    """闭合收敛检测节点"""

    def run(self, input_data: Any, **kwargs) -> Any:
        raise NotImplementedError("请使用 check()")

    def check(self, state: WorldBuildState) -> Tuple[bool, str]:
        """
        执行三级收敛检测。

        返回: (是否收敛, 完整报告)
        """
        entities = state.entities
        edges = state.edges

        # 基本检查: 至少需要一些实体
        if len(entities) < 3:
            report = "实体数量不足 (< 3)，需要继续搜索"
            self.log_info(f"收敛检测: {report}")
            return False, report

        # Level 1 — 结构完整性
        l1_pass, l1_report = self._check_structural_integrity(entities, edges)
        self.log_info(f"L1 结构完整性: {'✓' if l1_pass else '✗'} - {l1_report}")

        # Level 2 — 功能完整性
        l2_pass, l2_report = self._check_functional_integrity(entities, edges, state.focus)
        self.log_info(f"L2 功能完整性: {'✓' if l2_pass else '✗'} - {l2_report}")

        # Level 3 — 语义完整性 (LLM)，仅在 L1+L2 都通过后才执行
        if l1_pass and l2_pass:
            l3_pass, l3_report = self._check_semantic_integrity(state)
            self.log_info(f"L3 语义完整性: {'✓' if l3_pass else '✗'} - {l3_report}")
        else:
            l3_pass = False
            l3_report = "L1/L2 未通过，跳过语义检测"
            self.log_info(f"L3 语义完整性: 跳过（L1/L2 未通过）")

        converged = l1_pass and l2_pass and l3_pass
        full_report = f"L1[{l1_report}] L2[{l2_report}] L3[{l3_report}]"

        return converged, full_report

    def _check_structural_integrity(
        self, entities: Dict[str, Entity], edges: list[Edge]
    ) -> Tuple[bool, str]:
        """Level 1 — 结构完整性 (纯算法)"""
        G = nx.Graph()
        G.add_nodes_from(entities.keys())
        for edge in edges:
            G.add_edge(edge.source, edge.target)

        # 条件 1: 弱连通图
        is_connected = nx.is_connected(G) if len(G.nodes) > 0 else False

        # 条件 2: 无孤立节点
        isolated = [n for n in G.nodes() if G.degree(n) == 0]
        no_isolated = len(isolated) == 0

        passed = is_connected and no_isolated
        report = (
            f"连通性: {'✓' if is_connected else '✗'}, "
            f"孤立节点: {isolated if isolated else '无'}"
        )
        return passed, report

    def _check_functional_integrity(
        self, entities: Dict[str, Entity], edges: list[Edge], focus: str
    ) -> Tuple[bool, str]:
        """Level 2 — 功能完整性 (纯算法)"""
        human_entities = {eid for eid, e in entities.items() if e.type == "human"}
        nature_entities = {eid for eid, e in entities.items() if e.type == "nature"}

        # 条件 1: 每个人类类实体至少有 1 条出边
        human_with_out_edge = set()
        for edge in edges:
            if edge.source in human_entities:
                human_with_out_edge.add(edge.source)
        humans_without_influence = human_entities - human_with_out_edge
        cond1 = len(humans_without_influence) == 0

        # 识别外生核心事件: 出度 >= 3 且入度 == 0 的自然类实体视为外生驱动源
        out_degree: Dict[str, int] = {}
        in_degree: Dict[str, int] = {}
        for edge in edges:
            out_degree[edge.source] = out_degree.get(edge.source, 0) + 1
            in_degree[edge.target] = in_degree.get(edge.target, 0) + 1
            if edge.direction == "bidirectional":
                in_degree[edge.source] = in_degree.get(edge.source, 0) + 1
                out_degree[edge.target] = out_degree.get(edge.target, 0) + 1

        exogenous_sources = {
            eid for eid in nature_entities
            if out_degree.get(eid, 0) >= 3 and in_degree.get(eid, 0) == 0
        }

        # 条件 2: 每个自然类实体至少有 1 条入边（外生驱动源豁免）
        nature_with_in_edge = set()
        for edge in edges:
            if edge.target in nature_entities:
                nature_with_in_edge.add(edge.target)
            if edge.direction == "bidirectional" and edge.source in nature_entities:
                nature_with_in_edge.add(edge.source)
        natures_unreachable = nature_entities - nature_with_in_edge - exogenous_sources
        cond2 = len(natures_unreachable) == 0

        # 条件 3: 关注点相关实体至少被 2 个人类类实体的路径覆盖
        focus_lower = focus.lower()
        focus_entities = {
            eid for eid, e in entities.items()
            if focus_lower in e.name.lower() or focus_lower in e.description.lower()
        }
        focus_covered = True
        for fe in focus_entities:
            human_sources = {
                edge.source for edge in edges
                if edge.target == fe and edge.source in human_entities
            }
            if len(human_sources) < 2:
                focus_covered = False
        cond3 = focus_covered

        passed = cond1 and cond2 and cond3
        exo_note = f", 外生驱动源(豁免入边): {exogenous_sources}" if exogenous_sources else ""
        report = (
            f"人类实体出边: {'✓' if cond1 else '✗ 缺失: ' + str(humans_without_influence)}, "
            f"自然实体入边: {'✓' if cond2 else '✗ 缺失: ' + str(natures_unreachable)}, "
            f"关注点覆盖: {'✓' if cond3 else '✗'}"
            f"{exo_note}"
        )
        return passed, report

    def _check_semantic_integrity(self, state: WorldBuildState) -> Tuple[bool, str]:
        """Level 3 — 语义完整性 (LLM 反思)"""
        if self.llm_client is None:
            return True, "LLM 客户端未配置，跳过语义检测"

        # 构建实体摘要
        entities_summary = "\n".join(
            f"- [{e.type}] {e.name}: {e.description[:100]}"
            for e in state.entities.values()
        )
        edges_summary = "\n".join(
            f"- {e.source} --[{e.relation}]--> {e.target}: {e.description[:80]}"
            for e in state.edges
        )

        system_prompt = SEMANTIC_CHECK_SYSTEM_PROMPT.format(
            background=state.background,
            focus=state.focus,
            entities_summary=entities_summary,
            edges_summary=edges_summary,
        )

        user_prompt = "请判断这个闭合小世界的语义完整性。"

        try:
            response = self.llm_client.invoke(system_prompt, user_prompt, temperature=0.3)
            result = extract_clean_response(response)

            if "error" in result:
                return False, "LLM 语义检测响应解析失败"

            is_complete = result.get("complete", False)
            if is_complete:
                assessment = result.get("assessment", "")
                return True, f"完整: {assessment[:100]}"
            else:
                missing = result.get("missing", [])
                suggestions = result.get("search_suggestions", [])
                report = f"不完整: 缺少 {missing}; 建议搜索: {suggestions}"
                return False, report

        except Exception as e:
            logger.warning(f"语义完整性检测出错: {e}")
            return False, f"语义检测出错: {str(e)[:100]}"
