# -*- coding: utf-8 -*-
"""SSE 事件工具函数"""

from datetime import datetime


def make_event(event_type: str, data: dict) -> dict:
    """构造标准 SSE 事件字典。

    Args:
        event_type: 事件类型，如 "build:start"
        data: 事件数据

    Returns:
        符合 SSE 推送格式的 dict
    """
    return {
        "event": event_type,
        "data": data,
        "timestamp": datetime.now().isoformat(),
    }
