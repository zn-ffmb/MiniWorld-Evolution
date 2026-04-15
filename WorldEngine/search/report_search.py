# -*- coding: utf-8 -*-
"""
研报 / 深度搜索工具 — 复合使用 Tavily + Bocha

用于召回深度分析报告、研究报告、白皮书等长文内容。
"""

from typing import List

from loguru import logger

from WorldEngine.search.base_tool import BaseSearchTool
from WorldEngine.search.models import SearchResult
from WorldEngine.search.vendors.tavily_search import TavilyNewsAgency
from WorldEngine.search.vendors.bocha_search import BochaMultimodalSearch


class ReportSearchTool(BaseSearchTool):
    """
    研报 / 深度搜索工具

    同时调用 Tavily deep_search + Bocha comprehensive_search，
    在查询中附加报告限定词，最终合并去重返回结果。
    """

    def __init__(self, tavily_api_key: str, bocha_api_key: str, bocha_base_url: str = None):
        if not tavily_api_key:
            raise ValueError("Tavily API Key 不能为空")
        if not bocha_api_key:
            raise ValueError("Bocha API Key 不能为空")
        self._tavily_key = tavily_api_key
        self._bocha_key = bocha_api_key
        self._bocha_base_url = bocha_base_url
        self._tavily = None
        self._bocha = None

    def _get_tavily(self):
        if self._tavily is None:
            self._tavily = TavilyNewsAgency(api_key=self._tavily_key)
        return self._tavily

    def _get_bocha(self):
        if self._bocha is None:
            self._bocha = BochaMultimodalSearch(
                api_key=self._bocha_key, base_url=self._bocha_base_url
            )
        return self._bocha

    def get_tool_name(self) -> str:
        return "report_search_hybrid"

    def search(self, query: str, max_results: int = 10, **kwargs) -> List[SearchResult]:
        task_id = kwargs.get("task_id", "")
        dimension = kwargs.get("dimension", "")
        report_query = f"{query} (研报 OR 报告 OR 分析 OR 研究 OR 白皮书 OR report)"

        results: List[SearchResult] = []

        # Tavily 深度搜索
        try:
            tavily = self._get_tavily()
            tavily_resp = tavily.deep_search_news(report_query)
            for item in tavily_resp.results:
                results.append(SearchResult(
                    task_id=task_id,
                    dimension=dimension,
                    source_type="report",
                    source_tool="tavily_deep",
                    title=item.title or "",
                    content=item.content or "",
                    url=item.url or "",
                    published_date=getattr(item, "published_date", "") or "",
                ))
        except Exception as exc:
            logger.warning(f"ReportSearchTool Tavily 搜索失败: {exc}")

        # Bocha 补充搜索
        try:
            bocha = self._get_bocha()
            bocha_resp = bocha.comprehensive_search(report_query)
            for item in bocha_resp.webpages:
                results.append(SearchResult(
                    task_id=task_id,
                    dimension=dimension,
                    source_type="report",
                    source_tool="bocha_report",
                    title=item.name or "",
                    content=item.snippet or "",
                    url=item.url or "",
                    published_date=getattr(item, "date_last_crawled", "") or "",
                ))
        except Exception as exc:
            logger.warning(f"ReportSearchTool Bocha 搜索失败: {exc}")

        # URL 去重
        seen_urls: set = set()
        unique: List[SearchResult] = []
        for r in results:
            if r.url and r.url not in seen_urls:
                seen_urls.add(r.url)
                unique.append(r)
        return unique
