# -*- coding: utf-8 -*-
"""世界构建 API 路由"""

import asyncio
import json
from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from config import Settings
from visualization.backend.streaming.streaming_builder import StreamingWorldBuilder
from visualization.backend.task_manager import task_manager

router = APIRouter(prefix="/api/build", tags=["build"])


class BuildRequest(BaseModel):
    background: str = Field(..., min_length=1, max_length=500, description="背景")
    focus: str = Field(..., min_length=1, max_length=500, description="关注点")
    max_iterations: int = Field(default=None, ge=1, le=10, description="最大迭代次数")


class BuildResponse(BaseModel):
    task_id: str
    status: str
    stream_url: str


@router.post("", response_model=BuildResponse)
async def start_build(req: BuildRequest):
    """启动 L1 世界构建任务。"""
    task_id = f"build_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    try:
        queue = task_manager.register(task_id)
    except RuntimeError as e:
        raise HTTPException(status_code=429, detail=str(e))

    config = Settings()
    if req.max_iterations is not None:
        config.MAX_BUILD_ITERATIONS = req.max_iterations

    async def _run():
        try:
            builder = StreamingWorldBuilder(config)
            async for event in builder.build_stream(req.background, req.focus):
                await queue.put(event)
        except Exception as e:
            await queue.put({
                "event": "build:error",
                "data": {"message": str(e)},
                "timestamp": datetime.now().isoformat(),
            })
        finally:
            await queue.put(None)

    task = asyncio.create_task(_run())
    task_manager.set_task(task_id, task)

    return BuildResponse(
        task_id=task_id,
        status="started",
        stream_url=f"/api/build/stream/{task_id}",
    )


@router.get("/stream/{task_id}")
async def build_stream(task_id: str):
    """SSE 端点 — 推送构建事件流。"""
    queue = task_manager.get_queue(task_id)
    if queue is None:
        raise HTTPException(status_code=404, detail="任务不存在")

    async def event_generator():
        try:
            while True:
                event = await queue.get()
                if event is None:
                    break
                yield {
                    "event": event["event"],
                    "data": json.dumps(event["data"], ensure_ascii=False),
                }
        finally:
            task_manager.cleanup(task_id)

    return EventSourceResponse(event_generator())
