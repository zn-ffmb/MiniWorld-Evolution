# -*- coding: utf-8 -*-
"""
Bocha 多模态搜索客户端

基于 BettaFish (https://github.com/666ghj/BettaFish) 的 MediaEngine/tools/search.py 改写。
原始代码采用 GPL-2.0 许可证，本文件遵循相同许可。

API Key 和 Base URL 通过构造函数传入，不依赖外部 config。
"""

import json
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field

import requests
from loguru import logger

from WorldEngine.search.vendors.retry_helper import (
    with_graceful_retry,
    SEARCH_API_RETRY_CONFIG,
)


@dataclass
class WebpageResult:
    """网页搜索结果"""
    name: str
    url: str
    snippet: str
    display_url: Optional[str] = None
    date_last_crawled: Optional[str] = None


@dataclass
class ImageResult:
    """图片搜索结果"""
    name: str
    content_url: str
    host_page_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None


@dataclass
class ModalCardResult:
    """模态卡结构化数据结果"""
    card_type: str
    content: Dict[str, Any]


@dataclass
class BochaResponse:
    """Bocha API 返回结果"""
    query: str
    conversation_id: Optional[str] = None
    answer: Optional[str] = None
    follow_ups: List[str] = field(default_factory=list)
    webpages: List[WebpageResult] = field(default_factory=list)
    images: List[ImageResult] = field(default_factory=list)
    modal_cards: List[ModalCardResult] = field(default_factory=list)


class BochaMultimodalSearch:
    """Bocha 多模态搜索客户端"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        if not api_key:
            raise ValueError(
                "Bocha API Key 未找到！请在初始化时提供 api_key 参数。"
            )
        self._base_url = base_url or "https://api.bocha.cn/v1/ai-search"
        self._headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "*/*",
        }

    def _parse_search_response(
        self, response_dict: Dict[str, Any], query: str
    ) -> BochaResponse:
        final_response = BochaResponse(query=query)
        final_response.conversation_id = response_dict.get("conversation_id")

        messages = response_dict.get("messages", [])
        for msg in messages:
            if msg.get("role") != "assistant":
                continue

            content_type = msg.get("content_type")
            content_str = msg.get("content", "{}")

            try:
                content_data = json.loads(content_str)
            except json.JSONDecodeError:
                content_data = content_str

            msg_type = msg.get("type")

            if msg_type == "answer" and content_type == "text":
                final_response.answer = content_data
            elif msg_type == "follow_up" and content_type == "text":
                final_response.follow_ups.append(content_data)
            elif msg_type == "source":
                if content_type == "webpage":
                    for item in content_data.get("value", []):
                        final_response.webpages.append(
                            WebpageResult(
                                name=item.get("name"),
                                url=item.get("url"),
                                snippet=item.get("snippet"),
                                display_url=item.get("displayUrl"),
                                date_last_crawled=item.get("dateLastCrawled"),
                            )
                        )
                elif content_type == "image":
                    final_response.images.append(
                        ImageResult(
                            name=content_data.get("name"),
                            content_url=content_data.get("contentUrl"),
                            host_page_url=content_data.get("hostPageUrl"),
                            thumbnail_url=content_data.get("thumbnailUrl"),
                            width=content_data.get("width"),
                            height=content_data.get("height"),
                        )
                    )
                else:
                    final_response.modal_cards.append(
                        ModalCardResult(card_type=content_type, content=content_data)
                    )

        return final_response

    @with_graceful_retry(
        SEARCH_API_RETRY_CONFIG, default_return=BochaResponse(query="搜索失败")
    )
    def _search_internal(self, **kwargs) -> BochaResponse:
        query = kwargs.get("query", "Unknown Query")
        payload = {"stream": False}
        payload.update(kwargs)

        response = requests.post(
            self._base_url, headers=self._headers, json=payload, timeout=30
        )
        response.raise_for_status()

        response_dict = response.json()
        if response_dict.get("code") != 200:
            logger.error(f"Bocha API 错误: {response_dict.get('msg', '未知')}")
            return BochaResponse(query=query)

        return self._parse_search_response(response_dict, query)

    def comprehensive_search(
        self, query: str, max_results: int = 10
    ) -> BochaResponse:
        logger.info(f"--- Bocha 综合搜索 (query: {query}) ---")
        return self._search_internal(query=query, count=max_results, answer=True)

    def web_search_only(self, query: str, max_results: int = 15) -> BochaResponse:
        return self._search_internal(query=query, count=max_results, answer=False)
