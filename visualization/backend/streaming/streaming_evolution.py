# -*- coding: utf-8 -*-
"""
StreamingEvolutionEngine — L2 演变的流式编排器

复用 EvolutionEngine 的 WorldLLM / AgentRunner / TimelineExporter，
将 evolve() 循环改为异步生成器，在每个 Step 完成后 yield 事件。

不修改 EvolutionEngine 的任何已有代码。
"""

import asyncio
import os
from datetime import datetime
from typing import AsyncGenerator

from loguru import logger

from EvolutionEngine.llms.base import LLMClient
from EvolutionEngine.world_llm import WorldLLM
from EvolutionEngine.agent_runner import AgentRunner
from EvolutionEngine.equilibrium import EquilibriumDetector
from EvolutionEngine.exporters.timeline_exporter import TimelineExporter
from EvolutionEngine.state.models import (
    EvolutionState,
    TickRecord,
)
from WorldEngine.state.models import WorldSnapshot

from visualization.backend.streaming.events import make_event


class StreamingEvolutionEngine:
    """L2 演变的流式编排器。

    通过组合复用现有 WorldLLM/AgentRunner 组件，
    在每个 Tick 的每个 Step 之间 yield SSE 事件。
    """

    def __init__(self, config):
        self.config = config

        world_llm_client = LLMClient(
            api_key=config.EVOLUTION_ENGINE_API_KEY,
            model_name=config.EVOLUTION_ENGINE_MODEL,
            base_url=config.EVOLUTION_ENGINE_BASE_URL,
            max_tokens=config.EVOLUTION_MAX_TOKENS,
        )
        agent_llm_client = LLMClient(
            api_key=config.EVOLUTION_ENGINE_API_KEY,
            model_name=config.EVOLUTION_ENGINE_MODEL,
            base_url=config.EVOLUTION_ENGINE_BASE_URL,
            max_tokens=config.EVOLUTION_MAX_TOKENS,
        )

        self.world_llm = WorldLLM(
            llm_client=world_llm_client,
            temperature=config.EVOLUTION_WORLD_TEMPERATURE,
        )
        self.agent_runner = AgentRunner(
            llm_client=agent_llm_client,
            temperature=config.EVOLUTION_AGENT_TEMPERATURE,
        )
        self.exporter = TimelineExporter()

        # v3: 均衡检测器
        equilibrium_window = getattr(config, "EVOLUTION_EQUILIBRIUM_WINDOW", 3)
        self.equilibrium_detector = EquilibriumDetector(window_size=equilibrium_window)

    async def evolve_stream(
        self,
        snapshot: WorldSnapshot,
        perturbation: str,
        max_ticks: int = None,
    ) -> AsyncGenerator[dict, None]:
        """流式演变闭合小世界。

        每个 tick 的每个 step 完成后 yield 一个事件 dict。
        """
        if max_ticks is None:
            max_ticks = self.config.EVOLUTION_MAX_TICKS

        state = EvolutionState.from_snapshot(snapshot, perturbation, max_ticks)

        yield make_event("evolve:start", {
            "world_id": state.world_id,
            "perturbation": perturbation,
            "max_ticks": max_ticks,
            "tick_unit": state.tick_unit,
            "entities": [
                {
                    "id": e.id,
                    "name": e.name,
                    "type": e.type,
                    "status": e.status,
                    "tags": e.tags,
                }
                for e in state.entities.values()
            ],
            "edges": [e.to_dict() for e in state.edges],
        })

        # ========== Tick 0: 扰动注入 ==========
        yield make_event("evolve:tick_start", {
            "tick": 0, "max_ticks": max_ticks,
        })

        logger.info("[StreamingEvolution] Tick 0: 扰动注入")
        updates, narrative = await asyncio.to_thread(
            self.world_llm.inject_perturbation, state
        )
        state.apply_updates(updates, tick=0)

        yield make_event("evolve:propagation", {
            "tick": 0,
            "entity_updates": [u.to_dict() for u in updates],
            "propagation_summary": f"扰动注入: {perturbation}",
        })
        yield make_event("evolve:narrative", {
            "tick": 0, "narrative": narrative,
        })
        yield make_event("evolve:tick_end", {
            "tick": 0,
            "updated_entities_count": len(updates),
        })

        # 记录 Tick 0
        state.timeline.append(TickRecord(
            tick=0,
            world_assessment=f"扰动事件: {state.perturbation}",
            entity_updates=updates,
            world_narrative=narrative,
            timestamp=datetime.now().isoformat(),
        ))

        # ========== Tick 1 ~ N ==========
        for tick in range(1, max_ticks + 1):
            state.current_tick = tick
            logger.info(f"[StreamingEvolution] Tick {tick}/{max_ticks}")

            yield make_event("evolve:tick_start", {
                "tick": tick, "max_ticks": max_ticks,
            })

            # Step 1: 局势评估
            assessment = await asyncio.to_thread(
                self.world_llm.assess, state
            )
            yield make_event("evolve:assessment", {
                "tick": tick, "assessment": assessment,
            })

            # Step 2: 准备统一的世界状态信息（不调用 LLM）
            plan = await asyncio.to_thread(
                self.world_llm.plan_tick, state, assessment
            )
            human_entities = {
                eid: e for eid, e in state.entities.items()
                if e.type == "human"
            }
            yield make_event("evolve:plan", {
                "tick": tick,
                "active_agents": list(human_entities.keys()),
                "execution_order": list(human_entities.keys()),
                "visibility": plan.visibility,
            })

            # Step 3: 所有 human Agent 并行决策（基于相同的客观世界数据）
            all_actions = []

            # 构建公开世界事件时间线（所有 Agent 共享）
            world_timeline = self._build_world_timeline(state)

            for agent_id, entity in human_entities.items():
                # 当前世界状态快照（所有 Agent 看到相同的客观数据）
                current_world_state = plan.visibility.get(agent_id, "")

                # 构建行动历史
                action_history = self._build_action_history(state, agent_id)

                action = await asyncio.to_thread(
                    self.agent_runner.run_agent,
                    entity=entity,
                    visible_context=current_world_state,
                    tick=tick,
                    tick_unit=state.tick_unit,
                    action_history=action_history,
                    world_timeline=world_timeline,
                )
                all_actions.append(action)

                entity.last_action = action.action_description
                entity.last_action_reasoning = action.reasoning

                yield make_event("evolve:agent_action", {
                    "tick": tick,
                    "agent_id": action.agent_id,
                    "agent_name": action.agent_name,
                    "action_type": action.action_type,
                    "action_description": action.action_description,
                    "reasoning": action.reasoning,
                    "target_entities": action.target_entities,
                })

            # Step 4: 传播与更新
            max_cascade = getattr(self.config, "EVOLUTION_MAX_CASCADE_ROUNDS", 3)
            tick_updates, prop_summary = await asyncio.to_thread(
                self.world_llm.propagate, state, all_actions, max_cascade_rounds=max_cascade
            )
            state.apply_updates(tick_updates, tick=tick)

            yield make_event("evolve:propagation", {
                "tick": tick,
                "entity_updates": [u.to_dict() for u in tick_updates],
                "propagation_summary": prop_summary,
            })

            # Step 5: 叙事总结
            tick_narrative = await asyncio.to_thread(
                self.world_llm.narrate, state, all_actions, tick_updates
            )

            yield make_event("evolve:narrative", {
                "tick": tick, "narrative": tick_narrative,
            })

            yield make_event("evolve:tick_end", {
                "tick": tick,
                "updated_entities_count": len(tick_updates),
            })

            # 记录 TickRecord
            state.timeline.append(TickRecord(
                tick=tick,
                world_assessment=assessment,
                active_agents=plan.active_agents,
                execution_order=plan.execution_order,
                visibility_plan=plan.visibility,
                agent_actions=all_actions,
                propagation_summary=prop_summary,
                entity_updates=tick_updates,
                world_narrative=tick_narrative,
                timestamp=datetime.now().isoformat(),
            ))

            # v3: 算法均衡检测
            is_eq, eq_reason = self.equilibrium_detector.check(state)
            if is_eq:
                state.is_terminated = True
                state.termination_reason = eq_reason
                yield make_event("evolve:equilibrium", {
                    "tick": tick,
                    "reason": eq_reason,
                })

            if state.is_terminated:
                break

        # 导出时间线
        timeline = self.exporter.build_timeline(state)

        output_dir = self.config.EVOLUTIONS_DIR
        os.makedirs(output_dir, exist_ok=True)
        self.exporter.save(timeline, state, output_dir)

        yield make_event("evolve:complete", {
            "total_ticks": timeline.total_ticks,
            "termination_reason": state.termination_reason or "",
            "summary": {
                "total_agent_actions": timeline.total_agent_actions,
                "total_entity_updates": timeline.total_entity_updates,
                "most_active_agent": timeline.most_active_agent,
                "most_changed_entity": timeline.most_changed_entity,
            },
        })

    def _build_world_timeline(self, state) -> str:
        """从时间线中构建公开世界事件摘要（所有 Agent 可见）"""
        lines = []
        for record in state.timeline:
            if record.world_narrative:
                lines.append(f"Tick {record.tick}: {record.world_narrative}")
        return "\n".join(lines) if lines else ""

    def _build_action_history(self, state, agent_id: str) -> str:
        """从时间线中提取某个 Agent 的完整行动历史（含效果）"""
        lines = []
        for record in state.timeline:
            for action in record.agent_actions:
                if action.agent_id != agent_id or action.action_type == "wait":
                    continue
                effects = []
                for update in record.entity_updates:
                    if agent_id in (update.caused_by or []):
                        effects.append(f"{update.entity_name}: {update.change_reason[:80]}")
                effect_str = "; ".join(effects) if effects else "无直接观察到的效果"
                lines.append(
                    f"Tick {record.tick}: [{action.action_type}] "
                    f"{action.action_description[:120]} → 效果: {effect_str}"
                )
        return "\n".join(lines) if lines else ""
