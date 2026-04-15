# -*- coding: utf-8 -*-
"""世界和演变记录查询 API 路由"""

import json
import os
from typing import Optional

from fastapi import APIRouter, HTTPException

from config import Settings
from WorldEngine.state.models import WorldSnapshot

router = APIRouter(prefix="/api/worlds", tags=["worlds"])


@router.get("")
async def list_worlds():
    """列出所有已有的世界快照。"""
    config = Settings()
    worlds_dir = config.WORLDS_DIR

    if not os.path.isdir(worlds_dir):
        return {"worlds": []}

    worlds = []
    for fname in sorted(os.listdir(worlds_dir), reverse=True):
        if not fname.endswith(".json"):
            continue
        fpath = os.path.join(worlds_dir, fname)
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                data = json.load(f)
            worlds.append({
                "world_id": data.get("world_id", ""),
                "background": data.get("background", ""),
                "focus": data.get("focus", ""),
                "human_entity_count": data.get("human_entity_count", 0),
                "nature_entity_count": data.get("nature_entity_count", 0),
                "edge_count": data.get("edge_count", 0),
                "created_at": data.get("created_at", ""),
                "world_description": data.get("world_description", "")[:200],
            })
        except (json.JSONDecodeError, KeyError):
            continue

    return {"worlds": worlds}


@router.get("/{world_id}")
async def get_world(world_id: str):
    """获取指定世界的完整快照。"""
    config = Settings()
    fpath = os.path.join(config.WORLDS_DIR, f"{world_id}.json")
    if not os.path.exists(fpath):
        raise HTTPException(status_code=404, detail="世界快照不存在")

    with open(fpath, "r", encoding="utf-8") as f:
        data = json.load(f)

    return data


@router.get("/{world_id}/evolutions")
async def list_evolutions(world_id: str):
    """列出指定世界的所有演变记录。"""
    config = Settings()
    evolutions_dir = config.EVOLUTIONS_DIR

    if not os.path.isdir(evolutions_dir):
        return {"evolutions": []}

    evolutions = []
    for fname in sorted(os.listdir(evolutions_dir), reverse=True):
        if not fname.endswith(".json"):
            continue
        if world_id not in fname:
            continue
        fpath = os.path.join(evolutions_dir, fname)
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                data = json.load(f)
            evolutions.append({
                "world_id": data.get("world_id", ""),
                "perturbation": data.get("perturbation", ""),
                "total_ticks": data.get("total_ticks", 0),
                "total_agent_actions": data.get("total_agent_actions", 0),
                "total_entity_updates": data.get("total_entity_updates", 0),
                "started_at": data.get("started_at", ""),
                "finished_at": data.get("finished_at", ""),
            })
        except (json.JSONDecodeError, KeyError):
            continue

    return {"evolutions": evolutions}
