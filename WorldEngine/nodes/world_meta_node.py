# -*- coding: utf-8 -*-
"""
Phase 7: 世界元信息生成节点

LLM 为世界确定: tick 时间单位、世界描述摘要、每个实体的初始状态。
"""

import json
from typing import Any
from WorldEngine.nodes.base_node import StateMutationNode
from WorldEngine.state.models import WorldBuildState
from WorldEngine.prompts.prompts import WORLD_META_SYSTEM_PROMPT
from WorldEngine.utils.text_processing import extract_clean_response


class WorldMetaNode(StateMutationNode):
    """世界元信息生成节点"""

    def run(self, input_data: Any, **kwargs) -> Any:
        raise NotImplementedError("请使用 mutate_state()")

    def mutate_state(self, input_data: Any, state: WorldBuildState, **kwargs) -> WorldBuildState:
        """生成世界描述、tick 时间单位和每个实体的初始状态"""
        entities_summary = "\n".join(
            f"- [{e.type}] {e.name} (id={eid}): {e.description[:120]}"
            for eid, e in state.entities.items()
        )
        edges_summary = "\n".join(
            f"- {e.source} --[{e.relation}]--> {e.target} ({e.direction}): {e.description[:80]}"
            for e in state.edges
        )

        system_prompt = WORLD_META_SYSTEM_PROMPT.format(
            background=state.background,
            focus=state.focus,
            entities_summary=entities_summary,
            edges_summary=edges_summary,
        )

        user_prompt = "请为这个闭合小世界生成元信息。"

        self.log_info("生成世界元信息...")
        response = self.llm_client.invoke(system_prompt, user_prompt, temperature=0.5)
        result = extract_clean_response(response)

        if "error" in result:
            self.log_warning(f"世界元信息生成失败: {result}")
            state.world_description = f"围绕「{state.background}」与「{state.focus}」构建的闭合小世界。"
            state.tick_unit = "1周"
            return state

        state.world_description = result.get("world_description", "")
        state.tick_unit = result.get("tick_unit", "1周")

        # 为每个实体设置初始状态
        entity_states = result.get("entity_initial_states", {})
        for eid, meta in entity_states.items():
            if eid in state.entities:
                state.entities[eid].initial_status = meta.get("status", "")
                state.entities[eid].initial_tags = meta.get("tags", {})

        self.log_info(f"世界描述已生成，tick 单位: {state.tick_unit}")
        return state
