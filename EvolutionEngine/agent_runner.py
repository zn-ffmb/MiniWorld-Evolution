# -*- coding: utf-8 -*-
"""
Agent 执行器 — v3.1 认知层级分流 + 策略推理 + 深度审议

根据实体的 cognition_style 选择不同的决策流程:
- strategic: 阶段1（策略推理）→ 阶段2（换位审议）
- intuitive: 单阶段直觉判断
- reactive:  单阶段情绪/叙事驱动反应
"""

import json
from loguru import logger

from EvolutionEngine.llms.base import LLMClient
from EvolutionEngine.state.models import EntityLiveState, AgentAction
from EvolutionEngine.prompts.prompts import (
    AGENT_DECISION_USER_PROMPT,
    AGENT_DELIBERATION_PROMPT,
    AGENT_DECISION_INTUITIVE_PROMPT,
    AGENT_DECISION_REACTIVE_PROMPT,
)
from config import settings


class AgentRunner:
    """人类类实体 Agent 执行器（v3.1 认知层级分流）"""

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
        根据实体认知层级分流执行决策。

        strategic: 阶段1（策略推理）→ 阶段2（换位审议）
        intuitive: 单阶段直觉判断
        reactive:  单阶段情绪/叙事驱动反应
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

        style = getattr(entity, 'cognition_style', 'strategic')

        if style == "reactive":
            return self._reactive_decide(
                entity, visible_context, tick, tick_unit,
                action_history, world_timeline,
            )
        elif style == "intuitive":
            return self._intuitive_decide(
                entity, visible_context, tick, tick_unit,
                action_history, world_timeline,
            )
        else:
            return self._strategic_decide_and_deliberate(
                entity, visible_context, tick, tick_unit,
                action_history, world_timeline,
            )

    # ─────────────────────────────────────────────────
    # strategic: 两阶段策略推理 + 审议
    # ─────────────────────────────────────────────────

    def _strategic_decide_and_deliberate(
        self,
        entity: EntityLiveState,
        visible_context: str,
        tick: int,
        tick_unit: str,
        action_history: str,
        world_timeline: str,
    ) -> AgentAction:
        """strategic 认知风格: 阶段1 策略推理 → 阶段2 换位审议"""
        # 阶段1: 策略推理
        stage1_result = self._strategic_decide(
            entity, visible_context, tick, tick_unit,
            action_history, world_timeline,
        )

        situation_assessment = stage1_result.get("situation_assessment", "")
        key_party_predictions = stage1_result.get("key_party_predictions", [])
        counterfactual = stage1_result.get("counterfactual", "")
        stage1_actions = stage1_result.get("actions", [])

        if not stage1_actions:
            return AgentAction(
                agent_id=entity.id,
                agent_name=entity.name,
                action_type="wait",
                action_description="策略推理后选择不行动",
                reasoning="无明确行动指令",
                visible_context=visible_context,
                situation_assessment=situation_assessment,
                key_party_predictions=key_party_predictions,
                counterfactual=counterfactual,
                cognition_style="strategic",
            )

        # 阶段2: 换位审议（可配置关闭）
        if settings.EVOLUTION_AGENT_DELIBERATION:
            stage2_result = self._deliberate(
                entity, stage1_result, action_history,
            )
            deliberation = stage2_result.get("deliberation", [])
            final_actions = stage2_result.get("actions", stage1_actions)
        else:
            deliberation = []
            final_actions = stage1_actions

        return self._build_final_action(
            entity=entity,
            actions=final_actions,
            visible_context=visible_context,
            situation_assessment=situation_assessment,
            key_party_predictions=key_party_predictions,
            counterfactual=counterfactual,
            deliberation=deliberation,
            cognition_style="strategic",
        )

    # ─────────────────────────────────────────────────
    # intuitive: 单阶段直觉判断
    # ─────────────────────────────────────────────────

    def _intuitive_decide(
        self,
        entity: EntityLiveState,
        visible_context: str,
        tick: int,
        tick_unit: str,
        action_history: str,
        world_timeline: str,
    ) -> AgentAction:
        """intuitive 认知风格: 凭经验和直觉的单阶段快速判断"""
        action_space = entity.action_space or {}
        do_cap = self._format_capability(action_space, "do")
        decide_cap = self._format_capability(action_space, "decide")
        say_cap = self._format_capability(action_space, "say")

        user_prompt = AGENT_DECISION_INTUITIVE_PROMPT.format(
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

            cognition_context = {
                "gut_feeling": result.get("gut_feeling", ""),
                "expectation": result.get("expectation", ""),
            }

            logger.debug(
                f"  {entity.name} [intuitive]: "
                f"直觉={cognition_context['gut_feeling'][:60]}"
            )

            return self._build_simple_action(
                entity, actions, visible_context,
                cognition_style="intuitive",
                cognition_context=cognition_context,
            )
        except Exception as e:
            logger.warning(f"Agent {entity.name} [intuitive] 决策失败: {e}")
            return AgentAction(
                agent_id=entity.id,
                agent_name=entity.name,
                action_type="wait",
                action_description="决策过程出错，保持观望",
                reasoning=str(e)[:200],
                visible_context=visible_context,
                cognition_style="intuitive",
            )

    # ─────────────────────────────────────────────────
    # reactive: 单阶段情绪/叙事驱动反应
    # ─────────────────────────────────────────────────

    def _reactive_decide(
        self,
        entity: EntityLiveState,
        visible_context: str,
        tick: int,
        tick_unit: str,
        action_history: str,
        world_timeline: str,
    ) -> AgentAction:
        """reactive 认知风格: 情绪/叙事驱动的群体反应"""
        action_space = entity.action_space or {}
        do_cap = self._format_capability(action_space, "do")
        decide_cap = self._format_capability(action_space, "decide")
        say_cap = self._format_capability(action_space, "say")

        user_prompt = AGENT_DECISION_REACTIVE_PROMPT.format(
            tick=tick,
            tick_unit=tick_unit,
            visible_context=visible_context or "暂无实体状态信息。",
            world_timeline=world_timeline or "尚无公开事件记录。",
            action_history=action_history or "之前无集体行为记录。",
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

            cognition_context = {
                "emotional_trigger": result.get("emotional_trigger", ""),
                "dominant_emotion": result.get("dominant_emotion", ""),
                "emotion_intensity": result.get("emotion_intensity", ""),
            }

            logger.debug(
                f"  {entity.name} [reactive]: "
                f"情绪={cognition_context['dominant_emotion']} "
                f"强度={cognition_context['emotion_intensity']}"
            )

            return self._build_simple_action(
                entity, actions, visible_context,
                cognition_style="reactive",
                cognition_context=cognition_context,
            )
        except Exception as e:
            logger.warning(f"Agent {entity.name} [reactive] 决策失败: {e}")
            return AgentAction(
                agent_id=entity.id,
                agent_name=entity.name,
                action_type="wait",
                action_description="群体反应出错，保持沉默",
                reasoning=str(e)[:200],
                visible_context=visible_context,
                cognition_style="reactive",
            )

    # ─────────────────────────────────────────────────
    # 阶段1: 策略推理（strategic 专用）
    # ─────────────────────────────────────────────────

    def _strategic_decide(
        self,
        entity: EntityLiveState,
        visible_context: str,
        tick: int,
        tick_unit: str,
        action_history: str,
        world_timeline: str,
    ) -> dict:
        """阶段1: 使用增强 Prompt 进行策略推理"""
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
            logger.debug(
                f"  {entity.name} 阶段1完成: "
                f"研判={result.get('situation_assessment', '')[:60]}"
            )
            return result
        except Exception as e:
            logger.warning(f"Agent {entity.name} 阶段1失败: {e}")
            return {"actions": []}

    # ─────────────────────────────────────────────────
    # 阶段2: 深度审议（换位审视）
    # ─────────────────────────────────────────────────

    def _deliberate(
        self,
        entity: EntityLiveState,
        stage1_result: dict,
        action_history: str,
    ) -> dict:
        """阶段2: 换位审视 + 一致性/时机/风险评估"""
        situation_assessment = stage1_result.get("situation_assessment", "")
        key_party_predictions = stage1_result.get("key_party_predictions", [])
        counterfactual = stage1_result.get("counterfactual", "")
        stage1_actions = stage1_result.get("actions", [])

        # 格式化关键方预判为可读文本
        opp_lines = []
        for pred in key_party_predictions:
            relationship = pred.get('relationship', '')
            rel_tag = f"（{relationship}）" if relationship else ""
            opp_lines.append(
                f"- {pred.get('party', pred.get('opponent', '?'))}{rel_tag}: "
                f"预计{pred.get('predicted_action', '?')}（{pred.get('reasoning', '')}）"
            )
        predictions_text = "\n".join(opp_lines) if opp_lines else "无关键方预判"

        # 格式化候选行动为可读文本
        action_lines = []
        for i, act in enumerate(stage1_actions, 1):
            action_lines.append(
                f"方案{i}: [{act.get('type', '?')}] {act.get('description', '?')}"
                f"（理由: {act.get('reasoning', '')}）"
            )
        candidate_actions_text = "\n".join(action_lines) if action_lines else "无候选方案"

        user_prompt = AGENT_DELIBERATION_PROMPT.format(
            entity_name=entity.name,
            situation_assessment=situation_assessment,
            opponent_predictions_text=predictions_text,
            counterfactual=counterfactual,
            candidate_actions_text=candidate_actions_text,
            action_history=action_history or "无历史行动记录。",
        )

        try:
            response = self.llm_client.invoke(
                system_prompt=entity.agent_prompt,
                user_prompt=user_prompt,
                temperature=self.temperature,
            )
            result = self._parse_response(response)
            final_decision = result.get("final_decision", "维持")
            logger.debug(
                f"  {entity.name} 阶段2完成: 决定={final_decision}"
            )
            return result
        except Exception as e:
            logger.warning(f"Agent {entity.name} 阶段2失败，使用阶段1结果: {e}")
            return {"actions": stage1_actions}

    # ─────────────────────────────────────────────────
    # 结果构建
    # ─────────────────────────────────────────────────

    def _build_final_action(
        self,
        entity: EntityLiveState,
        actions: list,
        visible_context: str,
        situation_assessment: str = "",
        key_party_predictions: list = None,
        counterfactual: str = "",
        deliberation: list = None,
        cognition_style: str = "strategic",
    ) -> AgentAction:
        """从 strategic 两阶段结果构建最终 AgentAction"""
        if not actions:
            return AgentAction(
                agent_id=entity.id,
                agent_name=entity.name,
                action_type="wait",
                action_description="审议后选择不行动",
                reasoning="",
                visible_context=visible_context,
                situation_assessment=situation_assessment,
                key_party_predictions=key_party_predictions or [],
                counterfactual=counterfactual,
                deliberation=deliberation or [],
                cognition_style=cognition_style,
            )

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
                situation_assessment=situation_assessment,
                key_party_predictions=key_party_predictions or [],
                counterfactual=counterfactual,
                deliberation=deliberation or [],
                cognition_style=cognition_style,
            )

        return AgentAction(
            agent_id=entity.id,
            agent_name=entity.name,
            action_type=primary.get("type", "do"),
            action_description=primary.get("description", ""),
            reasoning=primary.get("reasoning", ""),
            target_entities=primary.get("target_entities", []),
            visible_context=visible_context,
            situation_assessment=situation_assessment,
            key_party_predictions=key_party_predictions or [],
            counterfactual=counterfactual,
            deliberation=deliberation or [],
            cognition_style=cognition_style,
        )

    def _build_simple_action(
        self,
        entity: EntityLiveState,
        actions: list,
        visible_context: str,
        cognition_style: str = "",
        cognition_context: dict = None,
    ) -> AgentAction:
        """从 intuitive/reactive 单阶段结果构建 AgentAction"""
        if not actions:
            return AgentAction(
                agent_id=entity.id,
                agent_name=entity.name,
                action_type="wait",
                action_description="选择不行动",
                reasoning="",
                visible_context=visible_context,
                cognition_style=cognition_style,
                cognition_context=cognition_context or {},
            )

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
                cognition_style=cognition_style,
                cognition_context=cognition_context or {},
            )

        return AgentAction(
            agent_id=entity.id,
            agent_name=entity.name,
            action_type=primary.get("type", "do"),
            action_description=primary.get("description", ""),
            reasoning=primary.get("reasoning", ""),
            target_entities=primary.get("target_entities", []),
            visible_context=visible_context,
            cognition_style=cognition_style,
            cognition_context=cognition_context or {},
        )

    # ─────────────────────────────────────────────────
    # 工具方法
    # ─────────────────────────────────────────────────

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
