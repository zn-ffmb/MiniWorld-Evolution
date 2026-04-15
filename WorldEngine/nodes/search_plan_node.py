# -*- coding: utf-8 -*-
"""
Phase 1: 假设驱动搜索规划节点

LLM 分析背景+关注点 → 生成三维度假设框架 + 定向搜索任务列表。
与 PerceptionEngine HypothesisGenerator 架构一致。
"""

import json
import re
from typing import Any, Dict, List
from WorldEngine.nodes.base_node import BaseNode
from WorldEngine.search.models import SearchTask
from WorldEngine.prompts.prompts import (
    HYPOTHESIS_PLAN_SYSTEM_PROMPT,
    HYPOTHESIS_PLAN_ITERATION_CONTEXT,
    HYPOTHESIS_PLAN_FIRST_ITERATION_CONTEXT,
)
from WorldEngine.utils.text_processing import extract_clean_response


def _clean_json_text(text: str) -> str:
    """移除 LLM 输出中可能附带的 markdown 代码块标记"""
    text = re.sub(r"```json\s*", "", text)
    text = re.sub(r"```\s*$", "", text)
    text = re.sub(r"```", "", text)
    for i, ch in enumerate(text):
        if ch == "{":
            return text[i:]
    return text.strip()


class SearchPlanNode(BaseNode):
    """假设驱动搜索规划节点"""

    def __init__(self, llm_client, default_max_results: int = 10):
        super().__init__(llm_client, node_name="SearchPlanNode")
        self.default_max_results = default_max_results

    def run(self, input_data: Dict[str, Any], **kwargs) -> List[SearchTask]:
        """
        生成搜索任务列表。

        input_data:
            background, focus, current_entities, current_edges,
            convergence_report, iteration
        返回:
            List[SearchTask]
        """
        background = input_data["background"]
        focus = input_data["focus"]
        iteration = input_data.get("iteration", 1)

        # 构建迭代上下文
        if iteration <= 1 or not input_data.get("current_entities"):
            iteration_context = HYPOTHESIS_PLAN_FIRST_ITERATION_CONTEXT
        else:
            iteration_context = HYPOTHESIS_PLAN_ITERATION_CONTEXT.format(
                iteration=iteration,
                current_entities=input_data.get("current_entities", "无"),
                current_edges=input_data.get("current_edges", "无"),
                convergence_report=input_data.get("convergence_report", "无"),
            )

        system_prompt = HYPOTHESIS_PLAN_SYSTEM_PROMPT.format(
            background=background,
            focus=focus,
            iteration_context=iteration_context,
        )

        user_prompt = f"背景: {background}\n关注点: {focus}\n请建立分析框架并生成搜索任务。"

        self.log_info(f"规划第 {iteration} 轮搜索策略（假设驱动）...")
        response = self.llm_client.invoke(system_prompt, user_prompt, temperature=0.7)

        tasks = self._parse_search_tasks(response, background, focus)
        tasks = self._validate_and_enrich(tasks, background, focus)

        self.log_info(f"生成 {len(tasks)} 个搜索任务")
        return tasks

    def _parse_search_tasks(
        self, raw: str, background: str, focus: str
    ) -> List[SearchTask]:
        """从 LLM 输出中解析搜索任务列表"""
        cleaned = _clean_json_text(raw)
        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError:
            # 尝试 extract_clean_response 兜底
            data = extract_clean_response(raw)
            if "error" in data:
                self.log_warning("LLM 响应解析失败，使用默认搜索任务")
                return self._default_tasks(background, focus)

        tasks: List[SearchTask] = []
        for item in data.get("search_tasks", []):
            tasks.append(SearchTask(
                task_id=item.get("task_id", f"task_{len(tasks)+1:02d}"),
                dimension=item.get("dimension", "key_questions"),
                query=item.get("query", ""),
                query_variants=item.get("query_variants", []),
                target_source=item.get("target_source", "news"),
                priority=item.get("priority", 3),
                context=item.get("context", ""),
                max_results=item.get("max_results", self.default_max_results),
            ))

        if not tasks:
            self.log_warning("LLM 未生成 search_tasks，使用默认搜索任务")
            return self._default_tasks(background, focus)

        return tasks

    def _validate_and_enrich(
        self, tasks: List[SearchTask], background: str, focus: str
    ) -> List[SearchTask]:
        """确保搜索任务覆盖三种数据源渠道"""
        sources = {t.target_source for t in tasks}
        base_query = f"{background} {focus}"

        if "social" not in sources:
            tasks.append(SearchTask(
                task_id="auto_social_01",
                dimension="participants",
                query=f"{base_query} 讨论 观点",
                target_source="social",
                priority=2,
                context="自动补充：社交媒体维度搜索",
            ))

        if "report" not in sources:
            tasks.append(SearchTask(
                task_id="auto_report_01",
                dimension="impact_factors",
                query=f"{base_query} 深度分析 研究",
                target_source="report",
                priority=2,
                context="自动补充：深度报告维度搜索",
            ))

        # 清理空变体
        for t in tasks:
            t.query_variants = [v for v in t.query_variants if v]

        return tasks

    def _default_tasks(self, background: str, focus: str) -> List[SearchTask]:
        """LLM 解析失败时的默认搜索任务"""
        return [
            SearchTask(
                task_id="default_01",
                dimension="impact_factors",
                query=f"{background} {focus}",
                target_source="news",
                priority=1,
                context="主题搜索",
            ),
            SearchTask(
                task_id="default_02",
                dimension="impact_factors",
                query=f"{background} 最新动态 影响",
                target_source="news",
                priority=1,
                context="最新新闻",
            ),
            SearchTask(
                task_id="default_03",
                dimension="impact_factors",
                query=f"{focus} 影响因素 分析",
                target_source="report",
                priority=2,
                context="背景分析",
            ),
            SearchTask(
                task_id="default_04",
                dimension="participants",
                query=f"{background} 关键参与方 利益主体",
                target_source="news",
                priority=2,
                context="实体发现",
            ),
            SearchTask(
                task_id="default_05",
                dimension="participants",
                query=f"{background} {focus} 讨论 观点",
                target_source="social",
                priority=2,
                context="社交声音",
            ),
            SearchTask(
                task_id="default_06",
                dimension="key_questions",
                query=f"{background} {focus} 历史 规律",
                target_source="report",
                priority=3,
                context="历史类比",
            ),
        ]
