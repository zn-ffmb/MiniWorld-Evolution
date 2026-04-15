# -*- coding: utf-8 -*-
"""
节点基类

定义 WorldEngine 所有处理节点的基础接口。
复用 BettaFish 的 BaseNode / StateMutationNode 模式。
"""

from abc import ABC, abstractmethod
from typing import Any
from loguru import logger
from WorldEngine.llms.base import LLMClient
from WorldEngine.state.models import WorldBuildState


class BaseNode(ABC):
    """节点基类 — 不直接修改全局 state"""

    def __init__(self, llm_client: LLMClient = None, node_name: str = ""):
        self.llm_client = llm_client
        self.node_name = node_name or self.__class__.__name__

    @abstractmethod
    def run(self, input_data: Any, **kwargs) -> Any:
        pass

    def log_info(self, message: str):
        logger.info(f"[{self.node_name}] {message}")

    def log_warning(self, message: str):
        logger.warning(f"[{self.node_name}] {message}")

    def log_error(self, message: str):
        logger.error(f"[{self.node_name}] {message}")


class StateMutationNode(BaseNode):
    """带状态修改功能的节点基类"""

    @abstractmethod
    def mutate_state(self, input_data: Any, state: WorldBuildState, **kwargs) -> WorldBuildState:
        pass
