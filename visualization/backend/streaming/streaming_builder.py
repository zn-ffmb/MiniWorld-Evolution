# -*- coding: utf-8 -*-
"""
StreamingWorldBuilder — L1 构建的流式编排器

复用 WorldEngine 的所有 Node 组件，将 build() 循环改为
异步生成器（async generator），在每个 Phase 完成后 yield 事件。

不修改 WorldEngine 的任何已有代码。
"""

import asyncio
import os
from datetime import datetime
from typing import AsyncGenerator, Any, Dict

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

from visualization.backend.streaming.events import make_event


class StreamingWorldBuilder:
    """L1 构建的流式编排器。

    通过组合复用现有 Node 组件，在每个 Phase 之间 yield SSE 事件，
    实现世界构建过程的实时可视化推送。
    """

    def __init__(self, config):
        self.config = config

        self.llm_client = LLMClient(
            api_key=config.WORLD_ENGINE_API_KEY,
            model_name=config.WORLD_ENGINE_MODEL,
            base_url=config.WORLD_ENGINE_BASE_URL,
            max_tokens=config.WORLD_ENGINE_MAX_TOKENS,
        )

        self.search_coordinator = SearchCoordinator(
            tavily_api_key=config.TAVILY_API_KEY,
            bocha_api_key=config.BOCHA_API_KEY,
            bocha_base_url=config.BOCHA_BASE_URL,
            max_search_tasks=config.MAX_SEARCH_TASKS,
            search_concurrency=config.SEARCH_CONCURRENCY,
            search_timeout=config.SEARCH_TIMEOUT,
            max_sampled_per_dimension=config.MAX_SAMPLED_PER_DIMENSION,
        )

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
        self.evidence_validator = EvidenceValidator()

    async def build_stream(
        self, background: str, focus: str
    ) -> AsyncGenerator[dict, None]:
        """流式构建闭合小世界。

        每个 Phase 完成后 yield 一个事件 dict，
        由 FastAPI SSE 端点逐个推送给前端。
        """
        state = WorldBuildState(
            background=background,
            focus=focus,
            max_iterations=self.config.MAX_BUILD_ITERATIONS,
            created_at=datetime.now().isoformat(),
        )

        yield make_event("build:start", {
            "background": background,
            "focus": focus,
            "max_iterations": state.max_iterations,
        })

        while state.iteration < state.max_iterations and not state.is_converged:
            state.iteration += 1
            state.updated_at = datetime.now().isoformat()

            logger.info(f"[StreamingBuilder] 迭代 {state.iteration}/{state.max_iterations}")

            yield make_event("build:iteration_start", {
                "iteration": state.iteration,
                "max_iterations": state.max_iterations,
            })

            # Phase 1: 假设驱动搜索规划
            search_tasks = await asyncio.to_thread(
                self.search_plan_node.run,
                {
                    "background": background,
                    "focus": focus,
                    "current_entities": self._summarize_entities(state),
                    "current_edges": self._summarize_edges(state),
                    "convergence_report": state.convergence_report,
                    "iteration": state.iteration,
                },
            )

            yield make_event("build:search_plan", {
                "search_tasks": [
                    {
                        "query": t.query,
                        "dimension": t.dimension,
                        "target_source": t.target_source,
                    }
                    for t in search_tasks
                ],
            })

            # Phase 2: 路由搜索执行
            search_results = await asyncio.to_thread(
                self.search_execution_node.run, search_tasks
            )

            result_count = (
                search_results.count("\n[")
                if isinstance(search_results, str)
                else 0
            )
            yield make_event("build:search_done", {
                "result_count": result_count,
            })

            # Phase 3: 实体与关系提取
            extraction = await asyncio.to_thread(
                self.entity_extraction_node.run,
                {
                    "background": background,
                    "focus": focus,
                    "search_results": search_results,
                    "existing_entities": self._summarize_entities(state),
                    "existing_edges": self._summarize_edges(state),
                },
            )

            # 检测提取失败
            if "error" in extraction:
                # 保存原始失败结果到中间文件供调试
                debug_dir = os.path.join(self.config.LOGS_DIR, "extraction_failures")
                os.makedirs(debug_dir, exist_ok=True)
                debug_path = os.path.join(
                    debug_dir,
                    f"extraction_fail_iter{state.iteration}_{datetime.now().strftime('%H%M%S')}.txt",
                )
                with open(debug_path, "w", encoding="utf-8") as f:
                    f.write(f"=== 实体提取失败 ===\n")
                    f.write(f"时间: {datetime.now().isoformat()}\n")
                    f.write(f"迭代: {state.iteration}\n")
                    f.write(f"错误类型: {extraction.get('error', '未知')}\n")
                    f.write(f"\n=== 原始 LLM 输出 ===\n")
                    f.write(extraction.get("raw_text", "无"))
                logger.warning(f"提取失败的原始输出已保存: {debug_path}")

                yield make_event("build:extraction_failed", {
                    "iteration": state.iteration,
                    "error": extraction.get("error", "未知错误"),
                    "message": "实体提取失败，将在下一轮迭代中重试",
                    "debug_file": debug_path,
                })
                # 提取失败时跳过合并和收敛检测，直接进入下一轮
                yield make_event("build:iteration_end", {
                    "iteration": state.iteration,
                    "entities_count": len(state.entities),
                    "edges_count": len(state.edges),
                })
                continue

            extraction = self.evidence_validator.filter_extraction(extraction)

            yield make_event("build:entities_extracted", {
                "new_entities": extraction.get("new_entities", []),
                "updated_entities": [
                    e.get("id") for e in extraction.get("updated_entities", [])
                ],
                "new_edges": extraction.get("new_edges", []),
            })

            # Phase 4: 世界合并
            state = self.world_merge_node.mutate_state(extraction, state)

            human_count = sum(
                1 for e in state.entities.values() if e.type == "human"
            )
            nature_count = sum(
                1 for e in state.entities.values() if e.type == "nature"
            )
            yield make_event("build:merge_done", {
                "total_entities": len(state.entities),
                "total_edges": len(state.edges),
                "human_count": human_count,
                "nature_count": nature_count,
            })

            # 记录搜索轮次
            state.search_rounds.append(SearchRound(
                iteration=state.iteration,
                search_queries=[t.query for t in search_tasks],
                search_tools=[t.target_source for t in search_tasks],
                result_count=result_count,
                entities_extracted=[
                    e.get("id", "") for e in extraction.get("new_entities", [])
                ],
                edges_extracted=len(extraction.get("new_edges", [])),
                reasoning="; ".join(
                    t.context for t in search_tasks[:3] if t.context
                ),
                timestamp=datetime.now().isoformat(),
            ))

            # Phase 5: 闭合收敛检测
            converged, report = await asyncio.to_thread(
                self.convergence_check_node.check, state
            )
            state.is_converged = converged
            state.convergence_report = report

            yield make_event("build:convergence", {
                "converged": converged,
                "report": report,
            })

            yield make_event("build:iteration_end", {
                "iteration": state.iteration,
                "entities_count": len(state.entities),
                "edges_count": len(state.edges),
            })

        # ========== 后处理（收敛后）==========

        # Phase 6: Agent Prompt 生成（逐个推送进度）
        human_entities = {
            eid: e for eid, e in state.entities.items() if e.type == "human"
        }
        total_humans = len(human_entities)

        yield make_event("build:prompts_start", {
            "total_agents": total_humans,
        })

        for idx, (eid, entity) in enumerate(human_entities.items(), 1):
            # 逐个生成：动作空间 + Agent Prompt
            await asyncio.to_thread(
                self._generate_single_agent_prompt, entity, state
            )

            yield make_event("build:prompt_progress", {
                "agent_id": entity.id,
                "agent_name": entity.name,
                "progress": idx,
                "total": total_humans,
                "has_prompt": entity.agent_prompt is not None,
            })

        agent_count = sum(
            1 for e in state.entities.values()
            if e.type == "human" and e.agent_prompt
        )
        yield make_event("build:prompts_generated", {
            "agent_count": agent_count,
            "agents": [
                {"id": e.id, "name": e.name}
                for e in state.entities.values()
                if e.type == "human" and e.agent_prompt
            ],
        })

        # Phase 7: 世界元信息
        state = await asyncio.to_thread(
            self.world_meta_node.mutate_state, None, state
        )
        yield make_event("build:meta_generated", {
            "tick_unit": state.tick_unit,
            "world_description": state.world_description,
        })

        # Phase 8: 导出快照
        snapshot = self.snapshot_export_node.export(state)
        os.makedirs(self.config.WORLDS_DIR, exist_ok=True)
        snapshot.save(self.config.WORLDS_DIR)

        # 额外生成 Markdown 报告
        md_report = self.snapshot_export_node.export_markdown_report(snapshot)
        md_path = os.path.join(
            self.config.WORLDS_DIR, f"{snapshot.world_id}.md"
        )
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(md_report)

        yield make_event("build:complete", {
            "world_id": snapshot.world_id,
            "snapshot_summary": {
                "human_entity_count": snapshot.human_entity_count,
                "nature_entity_count": snapshot.nature_entity_count,
                "edge_count": snapshot.edge_count,
                "build_iterations": snapshot.build_iterations,
                "world_description": snapshot.world_description,
                "tick_unit": snapshot.tick_unit,
            },
        })

    @staticmethod
    def _summarize_entities(state: WorldBuildState) -> str:
        if not state.entities:
            return ""
        lines = []
        for eid, e in state.entities.items():
            lines.append(
                f"- [{e.type}] {e.name} (id={eid}): {e.description[:100]}"
            )
        return "\n".join(lines)

    @staticmethod
    def _summarize_edges(state: WorldBuildState) -> str:
        if not state.edges:
            return ""
        lines = []
        for e in state.edges:
            lines.append(f"- {e.source} --[{e.relation}]--> {e.target}")
        return "\n".join(lines)

    def _generate_single_agent_prompt(self, entity, state: WorldBuildState) -> None:
        """为单个人类类实体生成动作空间和 Agent Prompt。

        直接调用 PromptGenerationNode 的内部方法（它们是无状态的），
        避免调用 mutate_state() 整体处理所有实体。
        """
        try:
            action_space = self.prompt_generation_node._generate_action_space(
                entity, state
            )
            entity.action_space = action_space

            agent_prompt = self.prompt_generation_node._generate_agent_prompt(
                entity, state
            )
            entity.agent_prompt = agent_prompt
        except Exception as e:
            logger.warning(f"Agent Prompt 生成失败 ({entity.name}): {e}")
            entity.action_space = {
                "do": {"enabled": False, "scope": "", "influence_targets": [], "constraints": ""},
                "decide": {"enabled": False, "scope": "", "influence_targets": [], "constraints": ""},
                "say": {"enabled": False, "scope": "", "influence_targets": [], "constraints": ""},
            }
            entity.agent_prompt = None
        if not state.edges:
            return ""
        lines = []
        for e in state.edges:
            lines.append(f"- {e.source} --[{e.relation}]--> {e.target}")
        return "\n".join(lines)
