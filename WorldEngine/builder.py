# -*- coding: utf-8 -*-
"""
WorldBuilder — L1 闭合小世界构建引擎主控类

类比 BettaFish 的 DeepSearchAgent，WorldBuilder 是 L1 的入口和调度中心。
通过迭代搜索-提取-验证-反思循环，构建满足闭合收敛条件的小世界快照。
"""

import os
from datetime import datetime
from loguru import logger

from WorldEngine.llms.base import LLMClient
from WorldEngine.state.models import WorldBuildState, WorldSnapshot, SearchRound
from WorldEngine.search.coordinator import SearchCoordinator
from WorldEngine.nodes.search_plan_node import SearchPlanNode
from WorldEngine.nodes.search_execution_node import SearchExecutionNode
from WorldEngine.nodes.entity_extraction_node import EntityExtractionNode, EvidenceValidator
from WorldEngine.nodes.world_merge_node import WorldMergeNode
from WorldEngine.nodes.convergence_check_node import ConvergenceCheckNode
from WorldEngine.nodes.prompt_generation_node import PromptGenerationNode
from WorldEngine.nodes.world_meta_node import WorldMetaNode
from WorldEngine.nodes.snapshot_export_node import SnapshotExportNode


class WorldBuilder:
    """L1 主控: 闭合小世界构建引擎"""

    def __init__(self, config):
        """
        初始化 WorldBuilder。

        Args:
            config: Settings 配置对象
        """
        self.config = config

        # LLM 客户端
        self.llm_client = LLMClient(
            api_key=config.WORLD_ENGINE_API_KEY,
            model_name=config.WORLD_ENGINE_MODEL,
            base_url=config.WORLD_ENGINE_BASE_URL,
            max_tokens=config.WORLD_ENGINE_MAX_TOKENS,
        )

        # 搜索协调器（路由 + 并行 + 维度聚类）
        self.search_coordinator = SearchCoordinator(
            tavily_api_key=config.TAVILY_API_KEY,
            bocha_api_key=config.BOCHA_API_KEY,
            bocha_base_url=config.BOCHA_BASE_URL,
            max_search_tasks=config.MAX_SEARCH_TASKS,
            search_concurrency=config.SEARCH_CONCURRENCY,
            search_timeout=config.SEARCH_TIMEOUT,
            max_sampled_per_dimension=config.MAX_SAMPLED_PER_DIMENSION,
        )

        # 各 Phase 节点
        self.search_plan_node = SearchPlanNode(
            self.llm_client,
            default_max_results=config.MAX_RESULTS_PER_TASK,
        )
        self.search_execution_node = SearchExecutionNode(
            coordinator=self.search_coordinator,
        )
        self.entity_extraction_node = EntityExtractionNode(self.llm_client)
        self.world_merge_node = WorldMergeNode()
        self.convergence_check_node = ConvergenceCheckNode(self.llm_client)
        self.prompt_generation_node = PromptGenerationNode(self.llm_client)
        self.world_meta_node = WorldMetaNode(self.llm_client)
        self.snapshot_export_node = SnapshotExportNode()

        # 校验器
        self.evidence_validator = EvidenceValidator()

    def build(self, background: str, focus: str) -> WorldSnapshot:
        """
        构建闭合小世界的主入口。

        Args:
            background: 用户输入的背景，如"美伊战争"
            focus: 用户输入的关注点，如"石油价格"

        Returns:
            WorldSnapshot 闭合小世界快照
        """
        # 初始化状态
        state = WorldBuildState(
            background=background,
            focus=focus,
            max_iterations=self.config.MAX_BUILD_ITERATIONS,
            created_at=datetime.now().isoformat(),
        )

        logger.info(f"开始构建闭合小世界: 背景=「{background}」, 关注点=「{focus}」")
        logger.info(f"最大迭代次数: {state.max_iterations}")

        # ========== 迭代构建循环 ==========
        while state.iteration < state.max_iterations and not state.is_converged:
            state.iteration += 1
            state.updated_at = datetime.now().isoformat()
            logger.info(f"\n{'='*60}")
            logger.info(f"=== 构建迭代 {state.iteration}/{state.max_iterations} ===")
            logger.info(f"{'='*60}")

            # Phase 1: 假设驱动搜索规划
            logger.info("--- Phase 1: 假设驱动搜索规划 ---")
            search_tasks = self.search_plan_node.run({
                "background": background,
                "focus": focus,
                "current_entities": self._summarize_entities(state),
                "current_edges": self._summarize_edges(state),
                "convergence_report": state.convergence_report,
                "iteration": state.iteration,
            })

            # Phase 2: 路由搜索执行
            logger.info("--- Phase 2: 路由搜索执行 ---")
            search_results = self.search_execution_node.run(search_tasks)

            # Phase 3: 实体与关系提取
            logger.info("--- Phase 3: 实体与关系提取 ---")
            extraction = self.entity_extraction_node.run({
                "background": background,
                "focus": focus,
                "search_results": search_results,
                "existing_entities": self._summarize_entities(state),
                "existing_edges": self._summarize_edges(state),
            })

            # 证据校验
            extraction = self.evidence_validator.filter_extraction(extraction)

            # Phase 4: 世界合并
            logger.info("--- Phase 4: 世界网络合并 ---")
            state = self.world_merge_node.mutate_state(extraction, state)

            # 记录搜索轮次
            state.search_rounds.append(SearchRound(
                iteration=state.iteration,
                search_queries=[t.query for t in search_tasks],
                search_tools=[t.target_source for t in search_tasks],
                result_count=len(search_results) if isinstance(search_results, list) else search_results.count('\n['),
                entities_extracted=[e.get("id", "") for e in extraction.get("new_entities", [])],
                edges_extracted=len(extraction.get("new_edges", [])),
                reasoning="; ".join(t.context for t in search_tasks[:3] if t.context),
                timestamp=datetime.now().isoformat(),
            ))

            # Phase 5: 闭合收敛检测
            logger.info("--- Phase 5: 闭合收敛检测 ---")
            converged, report = self.convergence_check_node.check(state)
            state.is_converged = converged
            state.convergence_report = report

            logger.info(f"收敛检测: {'✓ 通过' if converged else '✗ 未通过'}")
            logger.info(f"当前世界: {len(state.entities)} 实体, {len(state.edges)} 边")

            if self.config.SAVE_INTERMEDIATE_STATES:
                os.makedirs(self.config.LOGS_DIR, exist_ok=True)
                state.save_to_file(
                    os.path.join(self.config.LOGS_DIR, f"state_iter_{state.iteration}.json")
                )

        # ========== 后处理 (收敛后) ==========

        # Phase 6: Agent Prompt 生成
        logger.info(f"\n{'='*60}")
        logger.info("=== Phase 6: 生成 Agent Prompt ===")
        state = self.prompt_generation_node.mutate_state(None, state)

        # Phase 7: 世界元信息
        logger.info("=== Phase 7: 生成世界元信息 ===")
        state = self.world_meta_node.mutate_state(None, state)

        # Phase 8: 导出快照
        logger.info("=== Phase 8: 导出世界快照 ===")
        snapshot = self.snapshot_export_node.export(state)

        os.makedirs(self.config.WORLDS_DIR, exist_ok=True)
        json_path = snapshot.save(self.config.WORLDS_DIR)
        logger.info(f"世界快照 JSON 已保存: {json_path}")

        # 额外生成可读的 Markdown 报告
        md_report = self.snapshot_export_node.export_markdown_report(snapshot)
        md_path = json_path.replace(".json", ".md")
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(md_report)
        logger.info(f"世界报告 Markdown 已保存: {md_path}")

        logger.info(f"\n{'='*60}")
        logger.info(f"世界构建完成!")
        logger.info(f"  世界ID: {snapshot.world_id}")
        logger.info(f"  人类类实体: {snapshot.human_entity_count}")
        logger.info(f"  自然类实体: {snapshot.nature_entity_count}")
        logger.info(f"  关系边: {snapshot.edge_count}")
        logger.info(f"  构建轮次: {snapshot.build_iterations}")
        logger.info(f"{'='*60}")

        return snapshot

    @staticmethod
    def _summarize_entities(state: WorldBuildState) -> str:
        """生成实体摘要供 LLM 参考"""
        if not state.entities:
            return ""
        lines = []
        for eid, e in state.entities.items():
            lines.append(f"- [{e.type}] {e.name} (id={eid}): {e.description[:100]}")
        return "\n".join(lines)

    @staticmethod
    def _summarize_edges(state: WorldBuildState) -> str:
        """生成关系摘要供 LLM 参考"""
        if not state.edges:
            return ""
        lines = []
        for e in state.edges:
            lines.append(f"- {e.source} --[{e.relation}]--> {e.target}")
        return "\n".join(lines)
