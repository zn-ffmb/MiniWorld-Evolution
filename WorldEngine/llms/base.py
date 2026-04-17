# -*- coding: utf-8 -*-
"""
统一的 OpenAI 兼容 LLM 客户端

支持流式/非流式调用，集成指数退避重试机制，自动注入当前时间上下文。
"""

import os
from datetime import datetime
from typing import Any, Dict, Optional, Generator
from loguru import logger
from openai import OpenAI

from WorldEngine.search.vendors.retry_helper import with_retry, RetryConfig

LLM_RETRY_CONFIG = RetryConfig(max_retries=3, initial_delay=2.0, backoff_factor=2.0, max_delay=30.0)


class LLMClient:
    """OpenAI 兼容的统一 LLM 客户端"""

    def __init__(self, api_key: str, model_name: str, base_url: Optional[str] = None, max_tokens: int = 8192):
        if not api_key:
            raise ValueError("LLM API Key 不能为空")
        if not model_name:
            raise ValueError("LLM 模型名称不能为空")

        self.api_key = api_key
        self.base_url = base_url
        self.model_name = model_name
        self.max_tokens = max_tokens

        timeout_fallback = os.getenv("LLM_REQUEST_TIMEOUT", "1800")
        try:
            self.timeout = float(timeout_fallback)
        except ValueError:
            self.timeout = 1800.0

        client_kwargs: Dict[str, Any] = {"api_key": api_key, "max_retries": 0}
        if base_url:
            client_kwargs["base_url"] = base_url
        self.client = OpenAI(**client_kwargs)

    @with_retry(LLM_RETRY_CONFIG)
    def invoke(self, system_prompt: str, user_prompt: str, **kwargs) -> str:
        """非流式调用 LLM"""
        current_time = datetime.now().strftime("%Y年%m月%d日%H时%M分")
        time_prefix = f"今天的实际时间是{current_time}"
        user_prompt = f"{time_prefix}\n{user_prompt}" if user_prompt else time_prefix

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        allowed_keys = {"temperature", "top_p", "presence_penalty", "frequency_penalty", "max_tokens"}
        extra_params = {k: v for k, v in kwargs.items() if k in allowed_keys and v is not None}
        timeout = kwargs.pop("timeout", self.timeout)

        if "max_tokens" not in extra_params:
            extra_params["max_tokens"] = self.max_tokens

        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=messages,
            timeout=timeout,
            **extra_params,
        )

        if response.choices and response.choices[0].message:
            finish_reason = response.choices[0].finish_reason
            content = response.choices[0].message.content or ""
            if finish_reason == "length":
                logger.warning(
                    f"[LLM] 输出被截断 (finish_reason=length)，"
                    f"max_tokens={extra_params.get('max_tokens', self.max_tokens)}，"
                    f"已输出 {len(content)} 字符。"
                    f"输入 token: {getattr(response.usage, 'prompt_tokens', '?')}，"
                    f"输出 token: {getattr(response.usage, 'completion_tokens', '?')}"
                )
            return content
        return ""

    def stream_invoke(self, system_prompt: str, user_prompt: str, **kwargs) -> Generator[str, None, None]:
        """流式调用 LLM，逐步返回响应内容"""
        current_time = datetime.now().strftime("%Y年%m月%d日%H时%M分")
        time_prefix = f"今天的实际时间是{current_time}"
        user_prompt = f"{time_prefix}\n{user_prompt}" if user_prompt else time_prefix

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        allowed_keys = {"temperature", "top_p", "presence_penalty", "frequency_penalty", "max_tokens"}
        extra_params = {k: v for k, v in kwargs.items() if k in allowed_keys and v is not None}
        timeout = kwargs.pop("timeout", self.timeout)

        if "max_tokens" not in extra_params:
            extra_params["max_tokens"] = self.max_tokens

        stream = self.client.chat.completions.create(
            model=self.model_name,
            messages=messages,
            stream=True,
            timeout=timeout,
            **extra_params,
        )

        for chunk in stream:
            if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    @with_retry(LLM_RETRY_CONFIG)
    def stream_invoke_to_string(self, system_prompt: str, user_prompt: str, **kwargs) -> str:
        """流式调用 LLM 并安全拼接为完整字符串"""
        byte_chunks = []
        for chunk in self.stream_invoke(system_prompt, user_prompt, **kwargs):
            byte_chunks.append(chunk.encode('utf-8'))

        if byte_chunks:
            return b''.join(byte_chunks).decode('utf-8', errors='replace')
        return ""
