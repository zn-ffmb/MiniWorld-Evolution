# -*- coding: utf-8 -*-
"""
L2 演变引擎运行脚本

用法:
    python run_evolution.py --world worlds/world_20260412_175043.json \
                            --perturbation "霍尔木兹海峡因伊朗革命卫队封锁完全中断通行" \
                            --max-ticks 5
"""

import argparse
import os
import sys

# 确保项目根目录在 sys.path 中
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from loguru import logger
from config import settings
from WorldEngine.state.models import WorldSnapshot
from EvolutionEngine.engine import EvolutionEngine
from EvolutionEngine.exporters.timeline_exporter import TimelineExporter


def main():
    parser = argparse.ArgumentParser(description="L2 闭合小世界演变引擎")
    parser.add_argument(
        "--world", "-w",
        type=str,
        required=True,
        help="L1 世界快照 JSON 文件路径",
    )
    parser.add_argument(
        "--perturbation", "-p",
        type=str,
        required=True,
        help="扰动事件描述",
    )
    parser.add_argument(
        "--max-ticks", "-t",
        type=int,
        default=None,
        help="最大演变轮次（默认使用 config 中的 EVOLUTION_MAX_TICKS）",
    )
    parser.add_argument(
        "--output-dir", "-o",
        type=str,
        default=None,
        help="输出目录（默认使用 config 中的 EVOLUTIONS_DIR）",
    )

    args = parser.parse_args()

    # 加载世界快照
    world_path = args.world
    if not os.path.isabs(world_path):
        world_path = os.path.join(PROJECT_ROOT, world_path)

    if not os.path.exists(world_path):
        logger.error(f"世界快照文件不存在: {world_path}")
        sys.exit(1)

    logger.info(f"加载世界快照: {world_path}")
    snapshot = WorldSnapshot.load(world_path)
    logger.info(
        f"世界: {snapshot.world_id} | "
        f"{snapshot.human_entity_count} human + {snapshot.nature_entity_count} nature | "
        f"{snapshot.edge_count} 条边"
    )

    # 初始化演变引擎
    engine = EvolutionEngine(settings)

    # 运行演变
    timeline = engine.evolve(
        snapshot=snapshot,
        perturbation=args.perturbation,
        max_ticks=args.max_ticks,
    )

    # 保存结果
    output_dir = args.output_dir or settings.EVOLUTIONS_DIR
    exporter = TimelineExporter()

    # 需要重建 state 用于 Markdown 导出
    from EvolutionEngine.state.models import EvolutionState
    state = EvolutionState.from_snapshot(snapshot, args.perturbation)
    # 从 timeline 恢复最终状态：重放所有 entity_updates
    for record in timeline.ticks:
        for update in record.entity_updates:
            from EvolutionEngine.state.models import EntityUpdate
            if isinstance(update, EntityUpdate):
                entity = state.entities.get(update.entity_id)
                if entity:
                    entity.status = update.new_status
                    if update.new_tags:
                        entity.tags = update.new_tags

    json_path, md_path = exporter.save(timeline, state, output_dir)

    logger.info(f"\n演变结果已保存:")
    logger.info(f"  JSON: {json_path}")
    logger.info(f"  Markdown: {md_path}")


if __name__ == "__main__":
    main()
