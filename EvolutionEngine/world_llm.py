# -*- coding: utf-8 -*-
"""
WorldLLM — 世界规则引擎

不是参与者，而是世界运转规则的执行者。
负责: 局势评估 → Tick 规划 → 传播裁决 → 叙事总结。
"""

import json
from typing import List, Tuple
from loguru import logger

from EvolutionEngine.llms.base import LLMClient
from EvolutionEngine.state.models import (
    EvolutionState,
    AgentAction,
    EntityUpdate,
    TickRecord,
)
from EvolutionEngine.prompts.prompts import (
    WORLD_ASSESS_PROMPT,
    WORLD_PROPAGATE_PROMPT,
    WORLD_NARRATE_PROMPT,
    WORLD_PERTURBATION_PROMPT,
)
from WorldEngine.utils.text_processing import extract_clean_response


class TickPlan:
    """Tick 规划结果"""

    def __init__(
        self,
        active_agents: list,
        execution_order: list,
        visibility: dict,
        reasoning: str = "",
    ):
        self.active_agents = active_agents
        self.execution_order = execution_order
        self.visibility = visibility  # {agent_id: visible_info_str}
        self.reasoning = reasoning


class WorldLLM:
    """
    世界规则引擎

    类似 BettaFish ForumEngine 的 LLM Host，但职责从
    "调控讨论方向"升级为"调控整个世界的运转"。
    """

    def __init__(self, llm_client: LLMClient, temperature: float = 0.3):
        self.llm_client = llm_client
        self.temperature = temperature

    def inject_perturbation(
        self, state: EvolutionState
    ) -> Tuple[List[EntityUpdate], str]:
        """
        Tick 0: 注入扰动，返回初始冲击的实体更新和叙事。

        Returns:
            (entity_updates, perturbation_narrative)
        """
        prompt = WORLD_PERTURBATION_PROMPT.format(
            background=state.background,
            focus=state.focus,
            world_description=state.world_description,
            tick_unit=state.tick_unit,
            all_entity_states=state.get_all_status_summary(),
            edges_summary=state.get_edges_summary(),
            perturbation=state.perturbation,
        )

        response = self.llm_client.invoke(
            system_prompt=prompt,
            user_prompt=f"扰动事件: 「{state.perturbation}」\n请分析即时影响。",
            temperature=self.temperature,
        )

        result = extract_clean_response(response)
        if "error" in result:
            logger.warning(f"扰动注入 JSON 解析失败: {result}")
            return [], f"扰动发生: {state.perturbation}"

        updates = self._parse_entity_updates(result.get("entity_updates", []), state)
        narrative = result.get("perturbation_narrative", f"扰动发生: {state.perturbation}")

        return updates, narrative

    def assess(self, state: EvolutionState) -> str:
        """
        Step 1: 评估当前世界局势。

        Returns:
            局势评估文本
        """
        last_narrative = ""
        if state.timeline:
            # 提供完整的世界事件历史（所有 Tick 的叙事摘要）
            narratives = []
            for record in state.timeline:
                if record.world_narrative:
                    prefix = "扰动注入" if record.tick == 0 else f"Tick {record.tick}"
                    narratives.append(f"[{prefix}] {record.world_narrative}")
            last_narrative = "\n".join(narratives)

        prompt = WORLD_ASSESS_PROMPT.format(
            background=state.background,
            focus=state.focus,
            tick=state.current_tick,
            tick_unit=state.tick_unit,
            all_entity_states=state.get_all_status_summary(),
            last_tick_narrative=last_narrative or "（首轮演变，无上一 tick 记录）",
        )

        response = self.llm_client.invoke(
            system_prompt=prompt,
            user_prompt="请评估当前世界局势。",
            temperature=self.temperature,
        )

        return response.strip()

    def plan_tick(self, state: EvolutionState, assessment: str) -> TickPlan:
        """
        Step 2: 为所有 Agent 准备统一的世界状态信息。

        所有 human 类实体每 tick 均参与决策。
        每个 Agent 看到相同的客观世界数据（当前实体状态摘要），
        差异化通过各自的 system_prompt（角色身份）实现。

        不调用 LLM — 所有信息来自模拟已有数据。

        Returns:
            TickPlan
        """
        human_entities = state.get_human_entities()
        all_ids = list(human_entities.keys())

        # 所有 Agent 看到相同的客观世界状态
        world_state = state.get_all_status_summary()

        return TickPlan(
            active_agents=all_ids,
            execution_order=all_ids,
            visibility={eid: world_state for eid in all_ids},
            reasoning="所有 Agent 均参与决策，接收统一的客观世界状态",
        )

    def propagate(
        self, state: EvolutionState, actions: List[AgentAction]
    ) -> Tuple[List[EntityUpdate], str]:
        """
        Step 4: 汇总 Agent 动作，沿边传播影响，更新实体状态。

        Returns:
            (entity_updates, propagation_summary)
        """
        actions_summary = "\n".join(
            f"- {a.agent_name} [{a.action_type}]: {a.action_description}"
            f" (理由: {a.reasoning[:100]})"
            for a in actions
            if a.action_type != "wait"
        )

        if not actions_summary:
            actions_summary = "本 tick 无 Agent 采取行动"

        prompt = WORLD_PROPAGATE_PROMPT.format(
            background=state.background,
            focus=state.focus,
            tick=state.current_tick,
            tick_unit=state.tick_unit,
            edges_summary=state.get_edges_summary(),
            all_entity_states=state.get_all_status_summary(),
            agent_actions_summary=actions_summary,
        )

        response = self.llm_client.invoke(
            system_prompt=prompt,
            user_prompt="请执行传播并更新实体状态。",
            temperature=self.temperature,
        )

        result = extract_clean_response(response)
        if "error" in result:
            logger.warning(f"传播 JSON 解析失败: {result}")
            return [], "传播解析失败"

        updates = self._parse_entity_updates(
            result.get("entity_updates", [])
            + result.get("secondary_propagation", []),
            state,
        )
        summary = result.get("propagation_summary", "")

        return updates, summary

    def narrate(
        self, state: EvolutionState, actions: List[AgentAction], updates: List[EntityUpdate]
    ) -> str:
        """
        Step 5: 生成本 tick 的叙事总结。

        Returns:
            叙事文本
        """
        actions_summary = "\n".join(
            f"- {a.agent_name}: {a.action_description}"
            for a in actions
            if a.action_type != "wait"
        ) or "无 Agent 行动"

        updates_summary = "\n".join(
            f"- {u.entity_name}: {u.change_reason}"
            for u in updates
        ) or "无实体状态变化"

        prompt = WORLD_NARRATE_PROMPT.format(
            background=state.background,
            focus=state.focus,
            tick_unit=state.tick_unit,
            tick=state.current_tick,
            actions_summary=actions_summary,
            updates_summary=updates_summary,
        )

        response = self.llm_client.invoke(
            system_prompt=prompt,
            user_prompt="请生成本 tick 的叙事总结。",
            temperature=self.temperature,
        )

        return response.strip()

    @staticmethod
    def _parse_entity_updates(
        raw_updates: list, state: EvolutionState
    ) -> List[EntityUpdate]:
        """将 LLM 返回的 JSON 更新列表转为 EntityUpdate 对象"""
        # 构建名称→ID映射，用于 LLM 返回中文名称时的回退匹配
        name_to_id = {e.name: eid for eid, e in state.entities.items()}

        updates = []
        for item in raw_updates:
            if not isinstance(item, dict):
                continue
            eid = item.get("entity_id", "")
            entity = state.entities.get(eid)
            # 回退: 按名称匹配
            if entity is None:
                matched_id = name_to_id.get(eid)
                if matched_id:
                    eid = matched_id
                    entity = state.entities.get(eid)
            if entity is None:
                logger.debug(f"忽略不存在的实体更新: {eid}")
                continue

            updates.append(EntityUpdate(
                entity_id=eid,
                entity_name=entity.name,
                old_status=entity.status,
                new_status=item.get("new_status", entity.status),
                old_tags=dict(entity.tags),
                new_tags=item.get("new_tags", dict(entity.tags)),
                change_reason=item.get("change_reason", ""),
                caused_by=item.get("caused_by", []),
            ))

        return updates
