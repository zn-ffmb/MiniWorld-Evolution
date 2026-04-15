# -*- coding: utf-8 -*-
"""
Tavily 新闻搜索客户端

基于 BettaFish (https://github.com/666ghj/BettaFish) 的 QueryEngine/tools/search.py 改写。
原始代码采用 GPL-2.0 许可证，本文件遵循相同许可。

提供 TavilyNewsAgency 和相关数据类，供 NewsSearchTool / ReportSearchTool 使用。
"""

import os
from typing import List, Optional
from dataclasses import dataclass, field

from WorldEngine.search.vendors.retry_helper import (
    with_graceful_retry,
    SEARCH_API_RETRY_CONFIG,
)

try:
    from tavily import TavilyClient
except ImportError:
    raise ImportError("Tavily 库未安装，请运行 `pip install tavily-python`。")


@dataclass
class SearchResult:
    """网页搜索结果"""
    title: str
    url: str
    content: str
    score: Optional[float] = None
    raw_content: Optional[str] = None
    published_date: Optional[str] = None


@dataclass
class ImageResult:
    """图片搜索结果"""
    url: str
    description: Optional[str] = None


@dataclass
class TavilyResponse:
    """Tavily API 返回结果"""
    query: str
    answer: Optional[str] = None
    results: List[SearchResult] = field(default_factory=list)
    images: List[ImageResult] = field(default_factory=list)
    response_time: Optional[float] = None


class TavilyNewsAgency:
    """Tavily 新闻搜索客户端"""

    def __init__(self, api_key: Optional[str] = None):
        if api_key is None:
            api_key = os.getenv("TAVILY_API_KEY")
            if not api_key:
                raise ValueError(
                    "Tavily API Key 未找到！请设置 TAVILY_API_KEY 环境变量或在初始化时提供。"
                )
        self._client = TavilyClient(api_key=api_key)

    @with_graceful_retry(SEARCH_API_RETRY_CONFIG, default_return=TavilyResponse(query="搜索失败"))
    def _search_internal(self, **kwargs) -> TavilyResponse:
        kwargs["topic"] = "general"
        api_params = {k: v for k, v in kwargs.items() if v is not None}
        response_dict = self._client.search(**api_params)

        search_results = [
            SearchResult(
                title=item.get("title"),
                url=item.get("url"),
                content=item.get("content"),
                score=item.get("score"),
                raw_content=item.get("raw_content"),
                published_date=item.get("published_date"),
            )
            for item in response_dict.get("results", [])
        ]

        image_results = [
            ImageResult(url=item.get("url"), description=item.get("description"))
            for item in response_dict.get("images", [])
        ]

        return TavilyResponse(
            query=response_dict.get("query"),
            answer=response_dict.get("answer"),
            results=search_results,
            images=image_results,
            response_time=response_dict.get("response_time"),
        )

    def basic_search_news(self, query: str, max_results: int = 7) -> TavilyResponse:
        return self._search_internal(
            query=query, max_results=max_results, search_depth="basic", include_answer=False
        )

    def deep_search_news(self, query: str) -> TavilyResponse:
        return self._search_internal(
            query=query, search_depth="advanced", max_results=20, include_answer="advanced"
        )

    def search_news_last_24_hours(self, query: str) -> TavilyResponse:
        return self._search_internal(query=query, time_range="d", max_results=10)

    def search_news_last_week(self, query: str) -> TavilyResponse:
        return self._search_internal(query=query, time_range="w", max_results=10)

    def search_news_by_date(self, query: str, start_date: str, end_date: str) -> TavilyResponse:
        return self._search_internal(
            query=query, start_date=start_date, end_date=end_date, max_results=15
        )

    def search_images_for_news(self, query: str) -> TavilyResponse:
        return self._search_internal(
            query=query, include_images=True, include_image_descriptions=True, max_results=5
        )
