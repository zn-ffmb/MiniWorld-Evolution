# -*- coding: utf-8 -*-
"""
重试机制工具模块

基于 BettaFish (https://github.com/666ghj/BettaFish) 的 utils/retry_helper.py 改写。
原始代码采用 GPL-2.0 许可证，本文件遵循相同许可。

提供通用的网络请求重试功能，增强系统健壮性。
"""

import time
from functools import wraps
from typing import Callable, Any
import requests
from loguru import logger


class RetryConfig:
    """重试配置类"""

    def __init__(
        self,
        max_retries: int = 3,
        initial_delay: float = 1.0,
        backoff_factor: float = 2.0,
        max_delay: float = 60.0,
        retry_on_exceptions: tuple = None,
    ):
        self.max_retries = max_retries
        self.initial_delay = initial_delay
        self.backoff_factor = backoff_factor
        self.max_delay = max_delay

        if retry_on_exceptions is None:
            self.retry_on_exceptions = (
                requests.exceptions.RequestException,
                ConnectionError,
                TimeoutError,
                Exception,
            )
        else:
            self.retry_on_exceptions = retry_on_exceptions


SEARCH_API_RETRY_CONFIG = RetryConfig(
    max_retries=5,
    initial_delay=2.0,
    backoff_factor=1.6,
    max_delay=25.0,
)


def with_graceful_retry(config: RetryConfig = None, default_return=None):
    """
    优雅重试装饰器 - 失败后返回默认值而非抛出异常。
    """
    if config is None:
        config = SEARCH_API_RETRY_CONFIG

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            for attempt in range(config.max_retries + 1):
                try:
                    result = func(*args, **kwargs)
                    if attempt > 0:
                        logger.info(f"{func.__name__} 在第 {attempt + 1} 次尝试后成功")
                    return result
                except config.retry_on_exceptions as e:
                    if attempt == config.max_retries:
                        logger.warning(
                            f"{func.__name__} 在 {config.max_retries + 1} 次尝试后失败: {e}"
                        )
                        return default_return
                    delay = min(
                        config.initial_delay * (config.backoff_factor ** attempt),
                        config.max_delay,
                    )
                    logger.warning(
                        f"{func.__name__} 第 {attempt + 1} 次失败: {e}, "
                        f"{delay:.1f}s 后重试..."
                    )
                    time.sleep(delay)
                except Exception as e:
                    logger.warning(f"{func.__name__} 不可重试异常: {e}")
                    return default_return
            return default_return

        return wrapper
    return decorator


def with_retry(config: RetryConfig = None):
    """
    严格重试装饰器 - 失败后抛出异常（用于 LLM 调用等关键路径）。
    """
    if config is None:
        config = SEARCH_API_RETRY_CONFIG

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            for attempt in range(config.max_retries + 1):
                try:
                    result = func(*args, **kwargs)
                    if attempt > 0:
                        logger.info(f"{func.__name__} 在第 {attempt + 1} 次尝试后成功")
                    return result
                except config.retry_on_exceptions as e:
                    if attempt == config.max_retries:
                        logger.error(
                            f"{func.__name__} 在 {config.max_retries + 1} 次尝试后仍然失败"
                        )
                        raise
                    delay = min(
                        config.initial_delay * (config.backoff_factor ** attempt),
                        config.max_delay,
                    )
                    logger.warning(
                        f"{func.__name__} 第 {attempt + 1} 次失败: {e}, "
                        f"{delay:.1f}s 后重试..."
                    )
                    time.sleep(delay)

        return wrapper
    return decorator
