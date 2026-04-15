# -*- coding: utf-8 -*-
"""
MiniWorld L1: 闭合小世界构建引擎 CLI 入口

使用方式:
    python run_build_world.py --background "美伊战争" --focus "石油价格"
    python run_build_world.py -b "校园霸凌舆情" -f "舆论扩散" -n 3
"""

import argparse
import sys
import os

# 确保项目根目录在 sys.path 中
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from config import Settings
from WorldEngine.builder import WorldBuilder


def main():
    parser = argparse.ArgumentParser(description="MiniWorld L1: 构建闭合小世界")
    parser.add_argument("--background", "-b", required=True, help="背景, 如 '美伊战争'")
    parser.add_argument("--focus", "-f", required=True, help="关注点, 如 '石油价格'")
    parser.add_argument("--max-iterations", "-n", type=int, default=None, help="最大迭代次数 (默认读取配置)")
    args = parser.parse_args()

    config = Settings()
    if args.max_iterations is not None:
        config.MAX_BUILD_ITERATIONS = args.max_iterations

    # 验证必要配置
    if not config.WORLD_ENGINE_API_KEY:
        print("错误: 未配置 WORLD_ENGINE_API_KEY，请在 .env 文件中设置。")
        sys.exit(1)

    if not config.TAVILY_API_KEY and not config.BOCHA_API_KEY:
        print("警告: 未配置任何搜索 API Key (TAVILY_API_KEY / BOCHA_API_KEY)，搜索功能将不可用。")

    builder = WorldBuilder(config)
    snapshot = builder.build(background=args.background, focus=args.focus)

    print(f"\n世界构建完成!")
    print(f"  世界ID: {snapshot.world_id}")
    print(f"  人类类实体: {snapshot.human_entity_count}")
    print(f"  自然类实体: {snapshot.nature_entity_count}")
    print(f"  关系边: {snapshot.edge_count}")
    print(f"  构建轮次: {snapshot.build_iterations}")
    print(f"  快照路径: {config.WORLDS_DIR}/{snapshot.world_id}.json")
    print(f"  报告路径: {config.WORLDS_DIR}/{snapshot.world_id}.md")


if __name__ == "__main__":
    main()
