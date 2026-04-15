# -*- coding: utf-8 -*-
"""
Phase 2: 搜索执行节点

接收 SearchTask 列表 → 通过 SearchCoordinator 路由执行 → 维度化聚类采样
→ 格式化为 LLM 可读的字符串供 Phase 3 消费。

搜索层架构与 PerceptionEngine 一致:
  SearchCoordinator → BaseSearchTool 路由 (news/social/report)
  → ThreadPoolExecutor 并行 → 维度聚合 → ClusterSampler (KMeans++)
"""

import json
from typing import Any, Dict, List

from loguru import logger

from WorldEngine.nodes.base_node import BaseNode
from WorldEngine.search.models import SearchTask, SearchResult, SearchResultBundle
from WorldEngine.search.coordinator import SearchCoordinator


class SearchExecutionNode(BaseNode):
    """
    搜索执行节点 — 委托 SearchCoordinator 执行搜索。

    接收 Phase 1 输出的 List[SearchTask]，返回格式化字符串供 Phase 3 使用。
    """

    def __init__(self, coordinator: SearchCoordinator):
        super().__init__(node_name="SearchExecutionNode")
        self.coordinator = coordinator

    def run(self, input_data: Any, **kwargs) -> str:
        """
        执行搜索并返回格式化的搜索结果字符串。

        input_data: List[SearchTask]
        返回: 格式化的搜索结果字符串，按维度分组，供 Phase 3 LLM 消费
        """
        tasks: List[SearchTask] = input_data
        if not tasks:
            self.log_warning("无搜索任务")
            return "[]"

        self.log_info(f"开始执行 {len(tasks)} 个搜索任务（路由模式）")

        # 委托 SearchCoordinator 执行
        bundle: SearchResultBundle = self.coordinator.execute(tasks)

        self.log_info(
            f"搜索完成: 原始 {bundle.total_raw_count} 条 → "
            f"采样 {bundle.total_sampled_count} 条, "
            f"耗时 {bundle.search_duration_seconds}s"
        )

        # 格式化为 LLM 可读字符串
        formatted = self._format_bundle_for_llm(bundle)
        return formatted

    def _format_bundle_for_llm(self, bundle: SearchResultBundle) -> str:
        """
        将 SearchResultBundle 格式化为按维度分组的文本。

        Phase 3 (EntityExtractionNode) 接收此文本提取实体和关系。
        """
        sections = []

        # 影响因素维度
        if bundle.sampled_impact:
            sections.append(self._format_dimension(
                "影响因素维度搜索结果", bundle.sampled_impact
            ))

        # 参与者维度
        if bundle.sampled_participant:
            sections.append(self._format_dimension(
                "参与者维度搜索结果", bundle.sampled_participant
            ))

        # 关键问题维度
        if bundle.sampled_question:
            sections.append(self._format_dimension(
                "关键问题维度搜索结果", bundle.sampled_question
            ))

        if not sections:
            return "[]"

        # 搜索统计
        stats = (
            f"\n--- 搜索统计 ---\n"
            f"总原始结果: {bundle.total_raw_count} 条\n"
            f"聚类采样后: {bundle.total_sampled_count} 条\n"
            f"搜索耗时: {bundle.search_duration_seconds}s"
        )
        if bundle.failed_tasks:
            stats += f"\n失败任务: {', '.join(bundle.failed_tasks)}"

        return "\n\n".join(sections) + stats

    @staticmethod
    def _format_dimension(title: str, results: List[SearchResult]) -> str:
        """格式化单个维度的搜索结果"""
        lines = [f"=== {title} (共 {len(results)} 条) ===\n"]
        for i, r in enumerate(results, 1):
            lines.append(
                f"[{i}] 标题: {r.title}\n"
                f"    来源: {r.source_type} | {r.source_tool}\n"
                f"    链接: {r.url}\n"
                f"    内容: {r.content[:500]}\n"
            )
            if r.published_date:
                lines[-1] = lines[-1].rstrip() + f"\n    发布时间: {r.published_date}\n"
        return "\n".join(lines)
