# -*- coding: utf-8 -*-
"""
Phase 5.5: 网络结构分析节点 — L1 v3 升级 C

利用 NetworkX 分析闭合小世界图谱的拓扑结构属性，
输出结构化的网络分析报告供 L2 参考。

理论基础:
  - 网络科学 (Barabási 2003): 度中心性、中介中心性、接近中心性
  - 模块度 (Newman & Girvan 2004): 社区结构检测
  - 网络韧性: 关键节点识别
"""

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Tuple
import networkx as nx
from loguru import logger

from WorldEngine.nodes.base_node import BaseNode
from WorldEngine.state.models import WorldBuildState, Entity, Edge


@dataclass
class NetworkAnalysisReport:
    """网络结构分析报告"""

    # --- 节点中心性 ---
    degree_centrality: dict = field(default_factory=dict)
        # {entity_id: centrality_score}
    betweenness_centrality: dict = field(default_factory=dict)
    closeness_centrality: dict = field(default_factory=dict)

    # --- 关键识别 ---
    hub_nodes: list = field(default_factory=list)
        # 前 N 高度中心性节点 [{id, name, centrality}]
    bridge_edges: list = field(default_factory=list)
        # 高中介中心性的边 [{source, target, betweenness}]
    vulnerable_nodes: list = field(default_factory=list)
        # 移除后对连通性影响最大的节点

    # --- 社区结构 ---
    communities: list = field(default_factory=list)
        # [[entity_id, ...], [entity_id, ...]]
    community_labels: dict = field(default_factory=dict)
        # {entity_id: community_index}

    # --- 全局特征 ---
    density: float = 0.0
    average_clustering: float = 0.0
    diameter: int = -1
    num_components: int = 1

    def to_dict(self) -> dict:
        return asdict(self)

    def summary_for_llm(self, entities: dict) -> str:
        """生成供 LLM 阅读的文本摘要"""
        lines = ["=== 网络结构分析 ==="]
        lines.append(f"网络密度: {self.density:.2f} | 平均聚类系数: {self.average_clustering:.2f} | 直径: {self.diameter}")

        if self.hub_nodes:
            lines.append("\n枢纽节点（连接最多）:")
            for h in self.hub_nodes[:5]:
                name = entities.get(h["id"], type("", (), {"name": h["id"]})).name if isinstance(entities, dict) else h["id"]
                lines.append(f"  - {name} (度中心性: {h['centrality']:.2f})")

        if self.bridge_edges:
            lines.append("\n桥梁关系（跨阵营关键通道）:")
            for b in self.bridge_edges[:5]:
                src_name = entities.get(b["source"], type("", (), {"name": b["source"]})).name if isinstance(entities, dict) else b["source"]
                tgt_name = entities.get(b["target"], type("", (), {"name": b["target"]})).name if isinstance(entities, dict) else b["target"]
                lines.append(f"  - {src_name} → {tgt_name} (中介中心性: {b['betweenness']:.2f})")

        if self.communities and len(self.communities) > 1:
            lines.append(f"\n社区结构（{len(self.communities)} 个阵营）:")
            for i, comm in enumerate(self.communities):
                names = []
                for eid in comm:
                    if isinstance(entities, dict) and eid in entities:
                        names.append(entities[eid].name)
                    else:
                        names.append(eid)
                lines.append(f"  阵营 {i+1}: {', '.join(names)}")

        return "\n".join(lines)


class NetworkAnalysisNode(BaseNode):
    """
    Phase 5.5: 网络结构分析。

    纯算法节点，不调用 LLM，不存在先验知识泄漏风险。
    """

    def __init__(self):
        super().__init__(node_name="NetworkAnalysisNode")

    def run(self, input_data: Any, **kwargs) -> Any:
        raise NotImplementedError("请使用 analyze()")

    def analyze(self, state: WorldBuildState) -> NetworkAnalysisReport:
        """
        分析闭合小世界的网络结构。

        Args:
            state: 收敛后的世界构建状态

        Returns:
            NetworkAnalysisReport
        """
        G = self._build_graph(state)

        if len(G.nodes) == 0:
            self.log_warning("图谱为空，跳过网络分析")
            return NetworkAnalysisReport()

        report = NetworkAnalysisReport()

        # 1. 中心性计算
        report.degree_centrality = dict(nx.degree_centrality(G))
        report.betweenness_centrality = dict(nx.betweenness_centrality(G))
        if nx.is_connected(G):
            report.closeness_centrality = dict(nx.closeness_centrality(G))

        # 2. 枢纽节点（度中心性 top-5）
        sorted_by_degree = sorted(
            report.degree_centrality.items(), key=lambda x: x[1], reverse=True
        )
        report.hub_nodes = [
            {"id": eid, "name": state.entities[eid].name if eid in state.entities else eid,
             "centrality": round(score, 3)}
            for eid, score in sorted_by_degree[:5]
        ]

        # 3. 桥梁边（中介中心性）
        edge_betweenness = nx.edge_betweenness_centrality(G)
        sorted_edges = sorted(edge_betweenness.items(), key=lambda x: x[1], reverse=True)
        report.bridge_edges = [
            {"source": e[0], "target": e[1], "betweenness": round(score, 3)}
            for e, score in sorted_edges[:5]
        ]

        # 4. 脆弱节点（移除后连通分量数增加最多的）
        report.vulnerable_nodes = self._find_vulnerable_nodes(G, state, top_n=3)

        # 5. 社区结构（贪心模块度优化）
        try:
            communities_gen = nx.community.greedy_modularity_communities(G)
            report.communities = [sorted(list(c)) for c in communities_gen]
            for i, comm in enumerate(report.communities):
                for eid in comm:
                    report.community_labels[eid] = i
        except Exception as e:
            self.log_warning(f"社区检测失败: {e}")

        # 6. 全局特征
        report.density = round(nx.density(G), 3)
        try:
            report.average_clustering = round(nx.average_clustering(G), 3)
        except Exception:
            report.average_clustering = 0.0
        report.num_components = nx.number_connected_components(G)
        if nx.is_connected(G):
            report.diameter = nx.diameter(G)

        self.log_info(
            f"网络分析完成: {len(G.nodes)} 节点, {len(G.edges)} 边, "
            f"密度={report.density}, 阵营={len(report.communities)}"
        )

        return report

    def _build_graph(self, state: WorldBuildState) -> nx.Graph:
        """从世界状态构建 NetworkX 无向图"""
        G = nx.Graph()
        G.add_nodes_from(state.entities.keys())
        for edge in state.edges:
            G.add_edge(edge.source, edge.target)
        return G

    def _find_vulnerable_nodes(self, G: nx.Graph, state: WorldBuildState, top_n: int = 3) -> list:
        """找出移除后对网络连通性影响最大的节点"""
        if len(G.nodes) <= 2:
            return []

        original_components = nx.number_connected_components(G)
        vulnerability = []

        for node in G.nodes():
            H = G.copy()
            H.remove_node(node)
            new_components = nx.number_connected_components(H)
            delta = new_components - original_components
            if delta > 0:
                vulnerability.append({
                    "id": node,
                    "name": state.entities[node].name if node in state.entities else node,
                    "component_increase": delta,
                })

        vulnerability.sort(key=lambda x: x["component_increase"], reverse=True)
        return vulnerability[:top_n]
