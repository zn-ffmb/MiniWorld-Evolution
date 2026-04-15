# -*- coding: utf-8 -*-
"""
搜索协调器 — 搜索执行核心

接收 SearchTask 列表，按 target_source 路由到对应搜索工具，
使用线程池并行执行，按维度聚合 + 聚类采样，返回 SearchResultBundle。

与 PerceptionEngine SearchCoordinator 架构一致。
"""

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional

from loguru import logger

from WorldEngine.search.models import SearchTask, SearchResult, SearchResultBundle
from WorldEngine.search.base_tool import BaseSearchTool
from WorldEngine.search.news_search import NewsSearchTool
from WorldEngine.search.social_search import SocialSearchTool
from WorldEngine.search.report_search import ReportSearchTool
from WorldEngine.search.cluster_sampler import ClusterSampler


class SearchCoordinator:
    """
    搜索协调器

    职责：
    1. 根据 API Key 初始化搜索工具
    2. 按 target_source 将 SearchTask 路由到对应工具
    3. 线程池并行执行搜索（含 query_variants 展开）
    4. 按维度 (dimension) 聚合结果
    5. 对每组维度结果执行聚类采样
    6. 返回完整的 SearchResultBundle
    """

    def __init__(
        self,
        tavily_api_key: Optional[str] = None,
        bocha_api_key: Optional[str] = None,
        bocha_base_url: Optional[str] = None,
        max_search_tasks: int = 15,
        search_concurrency: int = 5,
        search_timeout: int = 30,
        max_sampled_per_dimension: int = 15,
    ):
        self.max_search_tasks = max_search_tasks
        self.search_concurrency = search_concurrency
        self.search_timeout = search_timeout

        self.sampler = ClusterSampler(max_sampled=max_sampled_per_dimension)

        # 初始化搜索工具
        self.tool_map: Dict[str, BaseSearchTool] = {}
        if tavily_api_key:
            self.tool_map["news"] = NewsSearchTool(api_key=tavily_api_key)
        if bocha_api_key:
            self.tool_map["social"] = SocialSearchTool(
                api_key=bocha_api_key, base_url=bocha_base_url
            )
        if tavily_api_key and bocha_api_key:
            self.tool_map["report"] = ReportSearchTool(
                tavily_api_key=tavily_api_key,
                bocha_api_key=bocha_api_key,
                bocha_base_url=bocha_base_url,
            )

        if not self.tool_map:
            logger.warning("SearchCoordinator: 未配置任何搜索 API Key，搜索将无法执行")

    def execute(self, tasks: List[SearchTask]) -> SearchResultBundle:
        """执行全部搜索任务，返回聚合后的 SearchResultBundle。"""
        start_time = time.time()

        # 按优先级排序，截断至上限
        sorted_tasks = sorted(tasks, key=lambda t: t.priority)
        active_tasks = sorted_tasks[: self.max_search_tasks]

        # 跨任务 query 去重：将 (target_source, query) 相同的查询合并，只搜一次
        deduped_queries, task_query_map = self._dedup_queries(active_tasks)

        logger.info(
            f"SearchCoordinator: {len(active_tasks)} 个任务, "
            f"去重后 {len(deduped_queries)} 个独立查询 "
            f"(并行度={self.search_concurrency})"
        )

        # 并行执行去重后的独立查询
        query_results: Dict[str, List[SearchResult]] = {}
        failed_tasks: List[str] = []

        with ThreadPoolExecutor(max_workers=self.search_concurrency) as executor:
            future_to_key = {}
            for key, (source, query, max_results) in deduped_queries.items():
                tool = self._resolve_tool(source)
                if tool is None:
                    continue
                future = executor.submit(
                    self._search_one, tool, query, max_results, key,
                )
                future_to_key[future] = key

            for future in as_completed(
                future_to_key,
                timeout=self.search_timeout * len(deduped_queries),
            ):
                key = future_to_key[future]
                try:
                    query_results[key] = future.result(timeout=self.search_timeout)
                except Exception as exc:
                    logger.warning(f"查询 {key} 失败: {exc}")
                    query_results[key] = []

        # 将查询结果按任务映射回各维度
        all_results: List[SearchResult] = []
        for task in active_tasks:
            task_keys = task_query_map.get(task.task_id, [])
            for key in task_keys:
                for r in query_results.get(key, []):
                    # 赋予正确的 task_id 和 dimension
                    tagged = SearchResult(
                        task_id=task.task_id,
                        dimension=task.dimension,
                        source_type=r.source_type,
                        source_tool=r.source_tool,
                        title=r.title,
                        content=r.content,
                        url=r.url,
                        published_date=r.published_date,
                        relevance_score=r.relevance_score,
                        cluster_id=r.cluster_id,
                    )
                    all_results.append(tagged)

        # 按维度聚合（兼容补充搜索的自定义维度名）
        impact_dims = {"impact_factors", "evidence_补充", "relation_补充"}
        participant_dims = {"participants", "voice_补充"}
        question_dims = {"key_questions"}

        impact_results = [r for r in all_results if r.dimension in impact_dims]
        participant_results = [r for r in all_results if r.dimension in participant_dims]
        question_results = [r for r in all_results if r.dimension in question_dims]

        # 兜底：未匹配任何标准维度的结果归入 impact
        matched_ids = {id(r) for r in impact_results + participant_results + question_results}
        for r in all_results:
            if id(r) not in matched_ids:
                impact_results.append(r)

        # 每个维度分别聚类采样
        sampled_impact = self.sampler.sample(impact_results)
        sampled_participant = self.sampler.sample(participant_results)
        sampled_question = self.sampler.sample(question_results)

        duration = time.time() - start_time

        bundle = SearchResultBundle(
            impact_results=impact_results,
            participant_results=participant_results,
            question_results=question_results,
            sampled_impact=sampled_impact,
            sampled_participant=sampled_participant,
            sampled_question=sampled_question,
            total_raw_count=len(all_results),
            total_sampled_count=(
                len(sampled_impact) + len(sampled_participant) + len(sampled_question)
            ),
            search_duration_seconds=round(duration, 2),
            failed_tasks=failed_tasks,
        )

        logger.info(
            f"SearchCoordinator 完成: "
            f"原始 {bundle.total_raw_count} 条 → 采样 {bundle.total_sampled_count} 条, "
            f"失败 {len(failed_tasks)} 个, "
            f"耗时 {bundle.search_duration_seconds}s"
        )
        return bundle

    def _dedup_queries(
        self, tasks: List[SearchTask]
    ) -> tuple:
        """
        跨任务 query 去重。

        返回:
            deduped_queries: {key: (target_source, query, max_results)}
            task_query_map: {task_id: [key1, key2, ...]}
        """
        deduped: Dict[str, tuple] = {}  # key → (source, query, max_results)
        task_map: Dict[str, List[str]] = {}  # task_id → [keys]

        for task in tasks:
            keys = []
            # 主查询
            main_key = f"{task.target_source}::{task.query}"
            if main_key not in deduped:
                deduped[main_key] = (task.target_source, task.query, task.max_results)
            keys.append(main_key)

            # 变体查询
            for variant in task.query_variants:
                if not variant:
                    continue
                var_key = f"{task.target_source}::{variant}"
                if var_key not in deduped:
                    deduped[var_key] = (
                        task.target_source,
                        variant,
                        max(3, task.max_results // 2),
                    )
                keys.append(var_key)

            task_map[task.task_id] = keys

        return deduped, task_map

    @staticmethod
    def _search_one(
        tool: BaseSearchTool, query: str, max_results: int, key: str,
    ) -> List[SearchResult]:
        """执行单个查询。"""
        return tool.search(
            query=query,
            max_results=max_results,
            task_id="",    # 稍后由 execute() 赋值
            dimension="",  # 稍后由 execute() 赋值
        )

    def _resolve_tool(self, target_source: str) -> Optional[BaseSearchTool]:
        """根据 target_source 选取搜索工具。"""
        if target_source in self.tool_map:
            return self.tool_map[target_source]

        # "any" 默认回退到 news
        if target_source == "any":
            return self.tool_map.get("news") or next(iter(self.tool_map.values()), None)

        # 未知 source 尝试 fallback
        return self.tool_map.get("news")
