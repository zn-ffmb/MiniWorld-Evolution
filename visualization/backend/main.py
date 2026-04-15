# -*- coding: utf-8 -*-
"""
MiniWorld 可视化后端 — FastAPI 入口

启动方式:
    cd d:\\MINI_WORLD
    uvicorn visualization.backend.main:app --reload --host 0.0.0.0 --port 8000
"""

import os
import sys

# 确保项目根目录在 sys.path 中
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from visualization.backend.routers import build, evolve, worlds

app = FastAPI(
    title="MiniWorld 可视化",
    description="闭合小世界构建与演变模拟可视化平台",
    version="1.0.0",
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:8000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:8000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(build.router)
app.include_router(evolve.router)
app.include_router(worlds.router)


@app.get("/api/health")
async def health():
    return {"status": "ok"}


# 生产模式挂载前端静态文件
frontend_dist = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "frontend", "dist",
)
if os.path.isdir(frontend_dist):
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")
