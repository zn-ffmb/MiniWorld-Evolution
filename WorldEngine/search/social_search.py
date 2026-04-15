# -*- coding: utf-8 -*-
"""
社交媒体搜索工具 — 底层使用 Bocha AI Search

在查询中附加社交平台限定词以提高社交内容召回率。
"""

from typing import List

from loguru import logger

from WorldEngine.search.base_tool import BaseSearchTool
from WorldEngine.search.models import SearchResult
from WorldEngine.search.vendors.bocha_search import BochaMultimodalSearch


class SocialSearchTool(BaseSearchTool):
    """
    社交媒体搜索工具

    在查询中附加社交平台限定词以提高社交内容召回率。
    底层使用 Bocha 的 comprehensive_search。
    """

    def __init__(self, api_key: str, base_url: str = None):
        if not api_key:
            raise ValueError("Bocha API Key 不能为空")
        self._api_key = api_key
        self._base_url = base_url
        self._bocha = None

    def _get_bocha(self):
        if self._bocha is None:
            self._bocha = BochaMultimodalSearch(
                api_key=self._api_key, base_url=self._base_url
            )
        return self._bocha

    def get_tool_name(self) -> str:
        return "social_search_bocha"

    def search(self, query: str, max_results: int = 10, **kwargs) -> List[SearchResult]:
        task_id = kwargs.get("task_id", "")
        dimension = kwargs.get("dimension", "")
        social_query = f"{query} (微博 OROR 论坛 OR 讨论)"

        try:
            bocha = self._get_bocha()
            resp = bocha.comprehensive_search(social_query)
            return self._convert(resp, task_id, dimension)
        except Exception as exc:
            logger.warning(f"SocialSearchTool 搜索失败: {exc}")
            return []

    @staticmethod
    def _convert(resp, task_id: str, dimension: str) -> List[SearchResult]:
        results: List[SearchResult] = []
        for item in resp.webpages:
            results.append(SearchResult(
                task_id=task_id,
                dimension=dimension,
                source_type="social",
                source_tool="social_search_bocha",
                title=item.name or "",
                content=item.snippet or "",
                url=item.url or "",
                published_date=getattr(item, "date_last_crawled", "") or "",
            ))
        return results
