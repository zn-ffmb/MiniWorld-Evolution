# -*- coding: utf-8 -*-
"""
MiniWorld 全局配置

使用 pydantic-settings 管理全局配置，支持从环境变量和 .env 文件自动加载。
"""

from pathlib import Path
from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional


PROJECT_ROOT: Path = Path(__file__).resolve().parent
CWD_ENV: Path = Path.cwd() / ".env"
ENV_FILE: str = str(CWD_ENV if CWD_ENV.exists() else (PROJECT_ROOT / ".env"))


class Settings(BaseSettings):
    """MiniWorld 全局配置 (从 .env 加载)"""

    # --- LLM 配置 ---
    WORLD_ENGINE_API_KEY: str = Field("", description="L1 构建用 LLM API 密钥")
    WORLD_ENGINE_MODEL: str = Field("qwen-plus", description="L1 构建用 LLM 模型名称")
    WORLD_ENGINE_BASE_URL: Optional[str] = Field(None, description="L1 构建用 LLM Base URL")
    WORLD_ENGINE_MAX_TOKENS: int = Field(8192, description="LLM 单次生成最大 token 数")

    # --- 搜索 API ---
    TAVILY_API_KEY: Optional[str] = Field(None, description="Tavily 新闻搜索 API 密钥")
    BOCHA_API_KEY: Optional[str] = Field(None, description="Bocha 多模态搜索 API 密钥")
    BOCHA_BASE_URL: Optional[str] = Field("https://api.bocha.cn/v1/ai-search", description="Bocha API Base URL")

    # --- 关键词优化 LLM ---
    KEYWORD_OPTIMIZER_API_KEY: Optional[str] = Field(None, description="关键词优化器 API 密钥")
    KEYWORD_OPTIMIZER_MODEL: str = Field("qwen-plus", description="关键词优化器模型名称")
    KEYWORD_OPTIMIZER_BASE_URL: Optional[str] = Field(None, description="关键词优化器 Base URL")

    # --- L1 构建参数 ---
    MAX_BUILD_ITERATIONS: int = Field(3, description="最大迭代次数")
    SAVE_INTERMEDIATE_STATES: bool = Field(False, description="是否保存中间状态")

    # --- 搜索路由参数（与 PerceptionEngine 一致）---
    MAX_RESULTS_PER_TASK: int = Field(10, description="每个搜索任务最大结果数")
    MAX_SEARCH_TASKS: int = Field(15, description="最大搜索任务总数")
    SEARCH_CONCURRENCY: int = Field(5, description="搜索并行线程数")
    SEARCH_TIMEOUT: int = Field(30, description="单个搜索请求超时（秒）")
    MAX_SAMPLED_PER_DIMENSION: int = Field(15, description="每个维度聚类采样后最大保留数")

    # --- L2 演变参数 ---
    EVOLUTION_ENGINE_API_KEY: str = Field("", description="L2 WorldLLM 用 LLM API 密钥")
    EVOLUTION_ENGINE_MODEL: str = Field("qwen-plus", description="L2 WorldLLM 模型")
    EVOLUTION_ENGINE_BASE_URL: Optional[str] = Field(None, description="L2 WorldLLM Base URL")
    EVOLUTION_MAX_TOKENS: int = Field(8192, description="L2 LLM 单次最大 token")
    EVOLUTION_MAX_TICKS: int = Field(10, description="默认最大演变轮次")
    EVOLUTION_AGENT_TEMPERATURE: float = Field(0.7, description="Agent 决策 temperature")
    EVOLUTION_WORLD_TEMPERATURE: float = Field(0.3, description="WorldLLM temperature")
    EVOLUTION_EQUILIBRIUM_WINDOW: int = Field(3, description="均衡检测窗口(连续N个tick)")
    EVOLUTION_AGENT_DELIBERATION: bool = Field(True, description="是否启用Agent两阶段审议(关闭则仅执行策略推理阶段)")
    EVOLUTION_MAX_CASCADE_ROUNDS: int = Field(3, description="级联传播最大轮次(1=仅一级传播,不做级联)")

    # --- 输出路径 ---
    WORLDS_DIR: str = Field("worlds", description="世界快照存放目录")
    EVOLUTIONS_DIR: str = Field("evolutions", description="演变时间线存放目录")
    LOGS_DIR: str = Field("logs", description="日志存放目录")

    model_config = {"env_file": ENV_FILE, "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()
