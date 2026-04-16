# -*- coding: utf-8 -*-
"""
Phase 6a-0: 利益-目标提取节点 (v3 新增)

从 evidence 中的行为事实推断 human 实体的利益结构和目标体系。
包含利益覆盖审视（二次检查，降低遗漏率）。
"""

import json
from typing import Any, Dict
from WorldEngine.nodes.base_node import StateMutationNode
from WorldEngine.state.models import WorldBuildState, StakeholderInterest, GoalStructure
from WorldEngine.prompts.prompts import (
    INTEREST_EXTRACTION_PROMPT,
    INTEREST_COVERAGE_REVIEW_PROMPT,
)
from WorldEngine.utils.text_processing import extract_clean_response


class InterestExtractionNode(StateMutationNode):
    """利益-目标提取节点 — 仅对 type=='human' 的实体执行"""

    def __init__(self, llm_client):
        super().__init__(node_name="InterestExtractionNode")
        self.llm_client = llm_client

    def run(self, input_data: Any, **kwargs) -> Any:
        raise NotImplementedError("请使用 mutate_state()")

    def mutate_state(self, input_data: Any, state: WorldBuildState, **kwargs) -> WorldBuildState:
        """为每个人类类实体提取利益结构和目标体系"""
        human_entities = {eid: e for eid, e in state.entities.items() if e.type == "human"}
        self.log_info(f"为 {len(human_entities)} 个人类类实体提取利益-目标模型")

        for eid, entity in human_entities.items():
            # 阶段1: 利益提取
            interests, goal_structure = self._extract_interests(entity, state)

            # 阶段2: 利益覆盖审视
            supplementary = self._review_coverage(entity, interests)
            if supplementary:
                interests.extend(supplementary)
                self.log_info(f"  {entity.name}: 审视补充了 {len(supplementary)} 个利益维度")

            # 证据校验: 过滤无证据的利益
            valid_interests = self._validate_interests(interests, entity.evidence)

            entity.interests = [i.to_dict() for i in valid_interests]
            entity.goal_structure = goal_structure.to_dict() if goal_structure else None

            self.log_info(
                f"  ✓ {entity.name}: {len(valid_interests)} 个利益维度 "
                f"({sum(1 for i in valid_interests if i.priority == 'core')} core)"
            )

        return state

    def _extract_interests(self, entity, state: WorldBuildState):
        """阶段1: 从 evidence 中提取利益和目标"""
        related_edges = [e for e in state.edges if e.source == entity.id or e.target == entity.id]
        edges_text = "\n".join(
            f"- {e.source} --[{e.relation}]--> {e.target}: {e.description[:80]}"
            for e in related_edges
        ) or "无关联关系"

        evidence_text = "\n".join(f"- {ev}" for ev in entity.evidence[:10])

        system_prompt = INTEREST_EXTRACTION_PROMPT.format(
            entity_name=entity.name,
            entity_description=entity.description,
            evidence=evidence_text,
            initial_status=entity.initial_status or "尚未设置初始状态",
            related_edges=edges_text,
        )

        try:
            response = self.llm_client.invoke(
                system_prompt, f"请提取实体「{entity.name}」的利益-目标模型。",
                temperature=0.3,
            )
            result = extract_clean_response(response)
            if "error" in result:
                self.log_warning(f"利益提取失败 ({entity.name}): {result}")
                return [], None

            interests = [
                StakeholderInterest.from_dict(i)
                for i in result.get("interests", [])
            ]
            goal_data = result.get("goal_structure")
            goal_structure = GoalStructure.from_dict(goal_data) if goal_data else None

            return interests, goal_structure
        except Exception as e:
            self.log_warning(f"利益提取异常 ({entity.name}): {e}")
            return [], None

    def _review_coverage(self, entity, interests):
        """阶段2: 利益覆盖审视 — 检查是否有遗漏的行为模式"""
        if not entity.evidence:
            return []

        interests_summary = "\n".join(
            f"- [{i.priority}] {i.dimension}: {i.description}"
            for i in interests
        ) or "（无利益维度被提取）"

        evidence_text = "\n".join(f"- {ev}" for ev in entity.evidence[:10])

        system_prompt = INTEREST_COVERAGE_REVIEW_PROMPT.format(
            entity_name=entity.name,
            evidence=evidence_text,
            extracted_interests_summary=interests_summary,
        )

        try:
            response = self.llm_client.invoke(
                system_prompt, f"请审查实体「{entity.name}」的利益覆盖完整性。",
                temperature=0.3,
            )
            result = extract_clean_response(response)
            if "error" in result:
                return []

            if not result.get("has_gaps", False):
                return []

            return [
                StakeholderInterest.from_dict(i)
                for i in result.get("supplementary_interests", [])
            ]
        except Exception as e:
            self.log_warning(f"利益覆盖审视异常 ({entity.name}): {e}")
            return []

    @staticmethod
    def _validate_interests(interests, entity_evidence):
        """证据校验: 过滤无证据或证据不匹配的利益维度"""
        valid = []
        for interest in interests:
            supporting = interest.supporting_evidence
            if not supporting:
                continue  # 无证据引用 → 拦截

            # 模糊匹配: supporting_evidence 中的内容是否出现在实体 evidence 中
            has_match = False
            for s in supporting:
                snippet = s[:30]  # 取前30字做子串匹配
                for ev in entity_evidence:
                    if snippet in ev or ev[:30] in s:
                        has_match = True
                        break
                if has_match:
                    break

            if has_match:
                valid.append(interest)

        return valid
