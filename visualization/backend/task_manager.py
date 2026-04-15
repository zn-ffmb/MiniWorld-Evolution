# -*- coding: utf-8 -*-
"""异步任务管理器 — 基于内存 Queue 的轻量方案"""

import asyncio
import json
from typing import Optional

from loguru import logger


class TaskManager:
    """管理进行中的异步构建/演变任务。

    每个任务由一个 asyncio.Queue 关联，streaming 编排器往 Queue
    里 put 事件，SSE 端点从 Queue 里消费事件并推送给前端。
    """

    def __init__(self, max_concurrent: int = 3):
        self._queues: dict[str, asyncio.Queue] = {}
        self._tasks: dict[str, asyncio.Task] = {}
        self._max_concurrent = max_concurrent

    @property
    def active_count(self) -> int:
        return sum(1 for t in self._tasks.values() if not t.done())

    def register(self, task_id: str) -> asyncio.Queue:
        """为新任务注册一个 Queue。"""
        if self.active_count >= self._max_concurrent:
            raise RuntimeError(
                f"已达最大并发任务数 ({self._max_concurrent})，请等待现有任务完成。"
            )
        queue: asyncio.Queue = asyncio.Queue()
        self._queues[task_id] = queue
        return queue

    def set_task(self, task_id: str, task: asyncio.Task) -> None:
        self._tasks[task_id] = task

    def get_queue(self, task_id: str) -> Optional[asyncio.Queue]:
        return self._queues.get(task_id)

    def cleanup(self, task_id: str) -> None:
        """清理已完成的任务资源。"""
        self._queues.pop(task_id, None)
        self._tasks.pop(task_id, None)

    def list_tasks(self) -> list[dict]:
        """列出所有任务及其状态。"""
        result = []
        for tid, task in self._tasks.items():
            result.append({
                "task_id": tid,
                "done": task.done(),
                "cancelled": task.cancelled(),
            })
        return result


# 全局单例
task_manager = TaskManager(max_concurrent=3)
