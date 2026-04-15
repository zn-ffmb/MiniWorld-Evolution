# -*- coding: utf-8 -*-
"""
新闻搜索工具 — 底层使用 Tavily API

支持 6 种搜索模式。
"""

from typing import List

from loguru import logger

from WorldEngine.search.base_tool import BaseSearchTool
from WorldEngine.search.models import SearchResult
from WorldEngine.search.vendors.tavily_search import TavilyNewsAgency, TavilyResponse


class NewsSearchTool(BaseSearchTool):
    """
    新闻搜索工具

    支持 6 种搜索模式（与 BettaFish QueryEngine 一致）：
      basic_search_news / deep_search_news / search_news_last_24_hours
      search_news_last_week / search_news_by_date / search_images_for_news
    """

    def __init__(self, api_key: str):
        if not api_key:
            raise ValueError("Tavily API Key 不能为空")
        self._api_key = api_key
        self._agency = None

    def _get_agency(self):
        if self._agency is None:
            self._agency = TavilyNewsAgency(api_key=self._api_key)
        return self._agency

    def get_tool_name(self) -> str:
        return "news_search_tavily"

    def search(self, query: str, max_results: int = 10, **kwargs) -> List[SearchResult]:
        tool_name = kwargs.get("search_tool", "basic_search_news")
        task_id = kwargs.get("task_id", "")
        dimension = kwargs.get("dimension", "")

        try:
            agency = self._get_agency()
            resp = self._execute(agency, tool_name, query, max_results, **kwargs)
            return self._convert(resp, task_id, dimension)
        except Exception as exc:
            logger.warning(f"NewsSearchTool 搜索失败 [{tool_name}]: {exc}")
            return []

    def _execute(self, agency, tool_name: str, query: str, max_results: int, **kwargs):
        if tool_name == "deep_search_news":
            return agency.deep_search_news(query)
        if tool_name == "search_news_last_24_hours":
            return agency.search_news_last_24_hours(query)
        if tool_name == "search_news_last_week":
            return agency.search_news_last_week(query)
        if tool_name == "search_news_by_date":
            return agency.search_news_by_date(
                query,
                kwargs.get("start_date", ""),
                kwargs.get("end_date", ""),
            )
        # 默认 basic_search_news
        return agency.basic_search_news(query, max_results)

    @staticmethod
    def _convert(resp, task_id: str, dimension: str) -> List[SearchResult]:
        results: List[SearchResult] = []
        for item in resp.results:
            results.append(SearchResult(
                task_id=task_id,
                dimension=dimension,
                source_type="news",
                source_tool="news_search_tavily",
                title=item.title or "",
                content=item.content or "",
                url=item.url or "",
                published_date=getattr(item, "published_date", "") or "",
                relevance_score=getattr(item, "score", 0.0) or 0.0,
            ))
        return results
