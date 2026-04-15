# -*- coding: utf-8 -*-
"""
Agent 执行器

负责调用人类类实体的 LLM，传入可见信息，获取决策。
"""

import json
from loguru import logger

from EvolutionEngine.llms.base import LLMClient
from EvolutionEngine.state.models import EntityLiveState, AgentAction
from EvolutionEngine.prompts.prompts import AGENT_DECISION_USER_PROMPT


class AgentRunner:
    """人类类实体 Agent 执行器"""

    def __init__(self, llm_client: LLMClient, temperature: float = 0.7):
        self.llm_client = llm_client
        self.temperature = temperature

    def run_agent(
        self,
        entity: EntityLiveState,
        visible_context: str,
        tick: int,
        tick_unit: str,
        action_history: str = "",
        world_timeline: str = "",
    ) -> AgentAction:
        """
        执行单个 Agent 的决策。

        Args:
            entity: 人类类实体运行时状态
            visible_context: WorldLLM 规划的该 Agent 可见信息
            tick: 当前 tick
            tick_unit: 时间单位
            action_history: 该 Agent 的历史行动记录
            world_timeline: 公开世界事件时间线

        Returns:
            AgentAction
        """
        if not entity.agent_prompt:
            logger.warning(f"Agent {entity.name} 没有 agent_prompt，跳过")
            return AgentAction(
                agent_id=entity.id,
                agent_name=entity.name,
                action_type="wait",
                action_description="无 agent_prompt，保持观望",
                reasoning="缺少系统提示词",
                visible_context=visible_context,
            )

        # 格式化能力范围（兼容 v1 和 v2）
        action_space = entity.action_space or {}
        do_cap = self._format_capability(action_space, "do")
        decide_cap = self._format_capability(action_space, "decide")
        say_cap = self._format_capability(action_space, "say")

        user_prompt = AGENT_DECISION_USER_PROMPT.format(
            tick=tick,
            tick_unit=tick_unit,
            visible_context=visible_context or "暂无实体状态信息。",
            world_timeline=world_timeline or "尚无公开事件记录。",
            action_history=action_history or "你在之前的 tick 中未采取任何行动。",
            do_capability=do_cap,
            decide_capability=decide_cap,
            say_capability=say_cap,
        )

        try:
            response = self.llm_client.invoke(
                system_prompt=entity.agent_prompt,
                user_prompt=user_prompt,
                temperature=self.temperature,
            )

            result = self._parse_response(response)
            actions = result.get("actions", [])

            if not actions:
                return AgentAction(
                    agent_id=entity.id,
                    agent_name=entity.name,
                    action_type="wait",
                    action_description="Agent 选择不行动",
                    reasoning="无明确行动指令",
                    visible_context=visible_context,
                )

            # 取第一个动作作为主要动作（如果有多个，合并描述）
            primary = actions[0]
            if len(actions) > 1:
                desc_parts = [a.get("description", "") for a in actions]
                reasoning_parts = [a.get("reasoning", "") for a in actions]
                targets = []
                for a in actions:
                    targets.extend(a.get("target_entities", []))

                return AgentAction(
                    agent_id=entity.id,
                    agent_name=entity.name,
                    action_type=primary.get("type", "do"),
                    action_description=" | ".join(desc_parts),
                    reasoning=" | ".join(reasoning_parts),
                    target_entities=targets,
                    visible_context=visible_context,
                )

            return AgentAction(
                agent_id=entity.id,
                agent_name=entity.name,
                action_type=primary.get("type", "do"),
                action_description=primary.get("description", ""),
                reasoning=primary.get("reasoning", ""),
                target_entities=primary.get("target_entities", []),
                visible_context=visible_context,
            )

        except Exception as e:
            logger.warning(f"Agent {entity.name} 决策失败: {e}")
            return AgentAction(
                agent_id=entity.id,
                agent_name=entity.name,
                action_type="wait",
                action_description="决策过程出错，保持观望",
                reasoning=str(e)[:200],
                visible_context=visible_context,
            )

    @staticmethod
    def _parse_response(response: str) -> dict:
        """解析 LLM 响应中的 JSON"""
        text = response.strip()
        # 去除可能的 markdown 代码块标记
        if text.startswith("```"):
            lines = text.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines)

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # 尝试提取 JSON 子串
            start = text.find("{")
            end = text.rfind("}") + 1
            if start >= 0 and end > start:
                try:
                    return json.loads(text[start:end])
                except json.JSONDecodeError:
                    pass
            logger.warning(f"Agent 响应 JSON 解析失败: {text[:200]}")
            return {"actions": []}

    @staticmethod
    def _format_capability(action_space: dict, action_type: str) -> str:
        """将 v1/v2 动作空间格式化为 Agent 可读的能力描述文本"""
        value = action_space.get(action_type)

        if value is None:
            return "（你不具备此类行动能力）"

        if isinstance(value, list):
            # v1 兼容: ["具体动作1 → 影响: X", "具体动作2 → 影响: Y"]
            if not value:
                return "（你不具备此类行动能力）"
            cleaned = [a.split(" → ")[0] for a in value]
            return "能力范围包括: " + "; ".join(cleaned)

        if isinstance(value, dict):
            # v2 格式: {"enabled": true, "scope": "...", ...}
            if not value.get("enabled", False):
                return "（你不具备此类行动能力）"
            parts = []
            scope = value.get("scope", "")
            if scope:
                parts.append(scope)
            targets = value.get("influence_targets", [])
            if targets:
                parts.append(f"可影响: {', '.join(targets)}")
            constraints = value.get("constraints", "")
            if constraints:
                parts.append(f"约束: {constraints}")
            return " | ".join(p for p in parts if p)

        return "无"
