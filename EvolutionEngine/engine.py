# -*- coding: utf-8 -*-
"""
EvolutionEngine — L2 闭合小世界演变引擎主控类

从 WorldSnapshot fork 运行时状态，注入扰动，
tick-by-tick 演变，输出完整的 EvolutionTimeline。
"""

from datetime import datetime
from loguru import logger

from EvolutionEngine.llms.base import LLMClient
from EvolutionEngine.world_llm import WorldLLM
from EvolutionEngine.agent_runner import AgentRunner
from EvolutionEngine.exporters.timeline_exporter import TimelineExporter
from EvolutionEngine.state.models import (
    EvolutionState,
    EvolutionTimeline,
    TickRecord,
)
from WorldEngine.state.models import WorldSnapshot


class EvolutionEngine:
    """L2 闭合小世界演变引擎 — 主控类"""

    def __init__(self, config):
        """
        初始化 EvolutionEngine。

        Args:
            config: Settings 配置对象
        """
        self.config = config

        # WorldLLM 客户端
        world_llm_client = LLMClient(
            api_key=config.EVOLUTION_ENGINE_API_KEY,
            model_name=config.EVOLUTION_ENGINE_MODEL,
            base_url=config.EVOLUTION_ENGINE_BASE_URL,
            max_tokens=config.EVOLUTION_MAX_TOKENS,
        )

        # Agent 客户端（可复用同一个，或配置不同模型）
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

    def evolve(
        self,
        snapshot: WorldSnapshot,
        perturbation: str,
        max_ticks: int = None,
    ) -> EvolutionTimeline:
        """
        从 WorldSnapshot fork 运行时状态，注入扰动，演变。

        Args:
            snapshot: L1 构建的闭合小世界快照
            perturbation: 扰动事件描述
            max_ticks: 最大演变轮次（默认使用 config 值）

        Returns:
            EvolutionTimeline 完整演变时间线
        """
        if max_ticks is None:
            max_ticks = self.config.EVOLUTION_MAX_TICKS

        # 1. 初始化演变状态
        state = EvolutionState.from_snapshot(snapshot, perturbation, max_ticks)

        logger.info(f"开始闭合小世界演变")
        logger.info(f"  世界: {state.world_id}")
        logger.info(f"  背景: {state.background}")
        logger.info(f"  关注点: {state.focus}")
        logger.info(f"  扰动: {perturbation}")
        logger.info(f"  最大 tick: {max_ticks}")
        logger.info(f"  实体: {len(state.entities)} 个")
        logger.info(f"  关系: {len(state.edges)} 条")

        # 2. Tick 0: 注入扰动
        logger.info(f"\n{'='*60}")
        logger.info("=== Tick 0: 扰动注入 ===")
        logger.info(f"{'='*60}")

        tick0_record = self._inject_perturbation(state)
        state.timeline.append(tick0_record)

        # 3. 演变主循环
        for tick in range(1, max_ticks + 1):
            state.current_tick = tick
            logger.info(f"\n{'='*60}")
            logger.info(f"=== Tick {tick}/{max_ticks} ({state.tick_unit}) ===")
            logger.info(f"{'='*60}")

            record = self._run_tick(state)
            state.timeline.append(record)

            if state.is_terminated:
                logger.info(f"演变提前终止: {state.termination_reason}")
                break

        # 4. 构建并导出时间线
        timeline = self.exporter.build_timeline(state)

        logger.info(f"\n{'='*60}")
        logger.info(f"演变完成!")
        logger.info(f"  总 tick: {timeline.total_ticks}")
        logger.info(f"  总 Agent 动作: {timeline.total_agent_actions}")
        logger.info(f"  总实体变更: {timeline.total_entity_updates}")
        logger.info(f"  最活跃 Agent: {timeline.most_active_agent}")
        logger.info(f"  变化最多的实体: {timeline.most_changed_entity}")
        logger.info(f"{'='*60}")

        return timeline

    def _inject_perturbation(self, state: EvolutionState) -> TickRecord:
        """Tick 0: 注入扰动事件"""
        updates, narrative = self.world_llm.inject_perturbation(state)

        # 应用扰动产生的状态变更
        state.apply_updates(updates, tick=0)

        logger.info(f"扰动注入完成: {len(updates)} 个实体受影响")
        logger.info(f"叙事: {narrative[:200]}")

        return TickRecord(
            tick=0,
            world_assessment=f"扰动事件: {state.perturbation}",
            entity_updates=updates,
            world_narrative=narrative,
            timestamp=datetime.now().isoformat(),
        )

    def _run_tick(self, state: EvolutionState) -> TickRecord:
        """执行单个 tick 的完整流程"""

        # Step 1: WorldLLM 评估局势
        logger.info("--- Step 1: 局势评估 ---")
        assessment = self.world_llm.assess(state)
        logger.info(f"评估: {assessment[:200]}")

        # Step 2: 准备统一的世界状态信息（不调用 LLM）
        logger.info("--- Step 2: 信息准备 ---")
        plan = self.world_llm.plan_tick(state, assessment)
        human_entities = state.get_human_entities()
        logger.info(
            f"参与决策 Agent: {[e.name for e in human_entities.values()]}"
        )

        # Step 3: 所有 human Agent 并行决策（基于相同的客观世界数据）
        logger.info("--- Step 3: Agent 并行决策 ---")
        all_actions = []

        # 构建公开世界事件时间线（所有 Agent 共享）
        world_timeline = self._build_world_timeline(state)

        for agent_id, entity in human_entities.items():
            # 当前世界状态快照（所有 Agent 看到相同的客观数据）
            current_world_state = plan.visibility.get(agent_id, "")

            # 构建该 Agent 的行动历史
            action_history = self._build_action_history(state, agent_id)

            action = self.agent_runner.run_agent(
                entity=entity,
                visible_context=current_world_state,
                tick=state.current_tick,
                tick_unit=state.tick_unit,
                action_history=action_history,
                world_timeline=world_timeline,
            )
            all_actions.append(action)

            # 更新实体的 last_action
            entity.last_action = action.action_description
            entity.last_action_reasoning = action.reasoning

            logger.info(
                f"  {entity.name} [{action.action_type}]: "
                f"{action.action_description[:100]}"
            )

        # Step 4: WorldLLM 传播与更新
        logger.info("--- Step 4: 传播与更新 ---")
        updates, prop_summary = self.world_llm.propagate(state, all_actions)

        # 应用状态变更
        state.apply_updates(updates, tick=state.current_tick)
        logger.info(f"传播完成: {len(updates)} 个实体状态更新")

        # Step 5: WorldLLM 叙事总结
        logger.info("--- Step 5: 叙事总结 ---")
        narrative = self.world_llm.narrate(state, all_actions, updates)
        logger.info(f"叙事: {narrative[:200]}")

        return TickRecord(
            tick=state.current_tick,
            world_assessment=assessment,
            active_agents=plan.active_agents,
            execution_order=plan.execution_order,
            visibility_plan=plan.visibility,
            agent_actions=all_actions,
            propagation_summary=prop_summary,
            entity_updates=updates,
            world_narrative=narrative,
            timestamp=datetime.now().isoformat(),
        )

    def _build_action_history(self, state: EvolutionState, agent_id: str) -> str:
        """从时间线中提取某个 Agent 的完整行动历史（含效果）"""
        lines = []
        for record in state.timeline:
            for action in record.agent_actions:
                if action.agent_id != agent_id or action.action_type == "wait":
                    continue

                # 查找该动作导致的实体状态变化
                effects = []
                for update in record.entity_updates:
                    if agent_id in (update.caused_by or []):
                        effects.append(
                            f"{update.entity_name}: {update.change_reason[:80]}"
                        )

                effect_str = "; ".join(effects) if effects else "无直接观察到的效果"
                lines.append(
                    f"Tick {record.tick}: [{action.action_type}] "
                    f"{action.action_description[:120]} → 效果: {effect_str}"
                )

        return "\n".join(lines) if lines else ""

    def _build_world_timeline(self, state: EvolutionState) -> str:
        """构建公开世界事件时间线（所有 Agent 共享的公共知识）"""
        lines = []
        for record in state.timeline:
            narrative = record.world_narrative
            if narrative:
                if record.tick == 0:
                    lines.append(f"[扰动注入] {narrative}")
                else:
                    lines.append(f"[Tick {record.tick}] {narrative}")
        return "\n".join(lines) if lines else ""
