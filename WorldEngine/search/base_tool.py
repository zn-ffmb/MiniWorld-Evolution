# -*- coding: utf-8 -*-
"""
搜索工具抽象基类
"""

from abc import ABC, abstractmethod
from typing import List

from WorldEngine.search.models import SearchResult


class BaseSearchTool(ABC):
    """所有搜索工具实现统一接口"""

    @abstractmethod
    def search(self, query: str, max_results: int = 10, **kwargs) -> List[SearchResult]:
        ...

    @abstractmethod
    def get_tool_name(self) -> str:
        ...
