# -*- coding: utf-8 -*-
"""演变模拟 API 路由"""

import asyncio
import json
import os
from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from config import Settings
from WorldEngine.state.models import WorldSnapshot
from visualization.backend.streaming.streaming_evolution import StreamingEvolutionEngine
from visualization.backend.task_manager import task_manager

router = APIRouter(prefix="/api/evolve", tags=["evolve"])


class EvolveRequest(BaseModel):
    world_id: str = Field(..., description="L1 世界快照 ID")
    perturbation: str = Field(..., min_length=1, max_length=1000, description="扰动事件描述")
    max_ticks: int = Field(default=None, ge=1, le=50, description="最大演变轮次")


class EvolveResponse(BaseModel):
    task_id: str
    status: str
    stream_url: str


@router.post("", response_model=EvolveResponse)
async def start_evolve(req: EvolveRequest):
    """启动 L2 演变任务。"""
    config = Settings()

    # 加载世界快照
    snapshot_path = os.path.join(config.WORLDS_DIR, f"{req.world_id}.json")
    if not os.path.exists(snapshot_path):
        raise HTTPException(status_code=404, detail=f"世界快照不存在: {req.world_id}")

    snapshot = WorldSnapshot.load(snapshot_path)

    task_id = f"evolve_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    try:
        queue = task_manager.register(task_id)
    except RuntimeError as e:
        raise HTTPException(status_code=429, detail=str(e))

    max_ticks = req.max_ticks

    async def _run():
        try:
            engine = StreamingEvolutionEngine(config)
            async for event in engine.evolve_stream(snapshot, req.perturbation, max_ticks):
                await queue.put(event)
        except Exception as e:
            await queue.put({
                "event": "evolve:error",
                "data": {"message": str(e)},
                "timestamp": datetime.now().isoformat(),
            })
        finally:
            await queue.put(None)

    task = asyncio.create_task(_run())
    task_manager.set_task(task_id, task)

    return EvolveResponse(
        task_id=task_id,
        status="started",
        stream_url=f"/api/evolve/stream/{task_id}",
    )


@router.get("/stream/{task_id}")
async def evolve_stream(task_id: str):
    """SSE 端点 — 推送演变事件流。"""
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
