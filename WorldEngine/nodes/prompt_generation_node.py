# -*- coding: utf-8 -*-
"""
Phase 6: Agent Prompt 生成节点

对每个人类类实体:
  Step 6a: 生成动作空间 (做/定/说)
  Step 6b: 生成完整的 Agent 系统 Prompt
"""

import json
from typing import Any
from WorldEngine.nodes.base_node import StateMutationNode
from WorldEngine.state.models import WorldBuildState
from WorldEngine.prompts.prompts import ACTION_SPACE_SYSTEM_PROMPT, AGENT_GENERATION_SYSTEM_PROMPT
from WorldEngine.utils.text_processing import extract_clean_response


class PromptGenerationNode(StateMutationNode):
    """Agent Prompt 生成节点 — 仅对 type=='human' 的实体执行"""

    def run(self, input_data: Any, **kwargs) -> Any:
        raise NotImplementedError("请使用 mutate_state()")

    def mutate_state(self, input_data: Any, state: WorldBuildState, **kwargs) -> WorldBuildState:
        """为每个人类类实体生成动作能力边界和 Agent Prompt"""
        human_entities = {eid: e for eid, e in state.entities.items() if e.type == "human"}
        self.log_info(f"为 {len(human_entities)} 个人类类实体生成 Agent Prompt")

        for eid, entity in human_entities.items():
            # Step 6a: 动作能力边界生成
            action_space = self._generate_action_space(entity, state)
            entity.action_space = action_space

            # Step 6b: Agent 系统 Prompt 生成
            agent_prompt = self._generate_agent_prompt(entity, state)
            entity.agent_prompt = agent_prompt

            enabled_count = sum(1 for k in ("do", "decide", "say") if action_space.get(k, {}).get("enabled", False))
            self.log_info(f"  ✓ {entity.name}: {enabled_count}/3 类能力已启用")

        return state

    def _generate_action_space(self, entity, state: WorldBuildState) -> dict:
        """为人类类实体生成动作能力边界 {do: {...}, decide: {...}, say: {...}}"""
        out_edges = [e for e in state.edges if e.source == entity.id]
        in_edges = [e for e in state.edges if e.target == entity.id]

        can_influence = json.dumps([
            {
                "target": state.entities[e.target].name if e.target in state.entities else e.target,
                "relation": e.relation,
                "description": e.description,
            }
            for e in out_edges if e.target in state.entities
        ], ensure_ascii=False)

        influenced_by = json.dumps([
            {
                "source": state.entities[e.source].name if e.source in state.entities else e.source,
                "relation": e.relation,
            }
            for e in in_edges if e.source in state.entities
        ], ensure_ascii=False)

        evidence_text = "\n".join(entity.evidence[:5])

        system_prompt = ACTION_SPACE_SYSTEM_PROMPT.format(
            entity_name=entity.name,
            entity_description=entity.description,
            evidence=evidence_text,
            can_influence=can_influence,
            influenced_by=influenced_by,
            background=state.background,
            focus=state.focus,
        )

        user_prompt = f"请为实体「{entity.name}」生成动作能力边界。"

        _default = {
            "do": {"enabled": False, "scope": "", "influence_targets": [], "constraints": ""},
            "decide": {"enabled": False, "scope": "", "influence_targets": [], "constraints": ""},
            "say": {"enabled": False, "scope": "", "influence_targets": [], "constraints": ""},
        }

        try:
            response = self.llm_client.invoke(system_prompt, user_prompt, temperature=0.5)
            result = extract_clean_response(response)
            if "error" not in result:
                # v2 格式: result 直接包含 do/decide/say 字典
                for key in ("do", "decide", "say"):
                    if key in result and isinstance(result[key], dict):
                        _default[key] = result[key]
                return _default
        except Exception as e:
            self.log_warning(f"动作能力边界生成失败 ({entity.name}): {e}")

        return _default

    def _generate_agent_prompt(self, entity, state: WorldBuildState) -> str:
        """生成完整的 Agent 系统 Prompt"""
        related_edges = [e for e in state.edges if e.source == entity.id or e.target == entity.id]

        neighbor_ids = set()
        for edge in related_edges:
            neighbor_ids.add(edge.source if edge.source != entity.id else edge.target)
        neighbors = [state.entities[nid] for nid in neighbor_ids if nid in state.entities]

        # 构建能力描述文本
        do_capability = self._format_capability(entity.action_space, "do")
        decide_capability = self._format_capability(entity.action_space, "decide")
        say_capability = self._format_capability(entity.action_space, "say")

        # 影响目标
        influence_targets = "\n".join(
            f"- {state.entities[e.target].name}: {e.relation}" if e.target in state.entities else ""
            for e in related_edges if e.source == entity.id
        )

        all_entity_names = [e.name for e in state.entities.values()]

        related_edges_text = json.dumps([
            {
                "relation": e.relation,
                "description": e.description,
                "target": state.entities.get(e.target).name if e.source == entity.id and e.target in state.entities else None,
                "source": state.entities.get(e.source).name if e.target == entity.id and e.source in state.entities else None,
            }
            for e in related_edges
        ], ensure_ascii=False)

        neighbors_text = json.dumps([
            {"name": n.name, "type": n.type, "description": n.description[:100]}
            for n in neighbors
        ], ensure_ascii=False)

        evidence_text = "\n".join(entity.evidence[:8])

        # v3: 构建结构化利益段落
        interests_section = self._format_interests_section(entity)

        system_prompt = AGENT_GENERATION_SYSTEM_PROMPT.format(
            entity_name=entity.name,
            entity_type=entity.type,
            entity_description=entity.description,
            evidence=evidence_text,
            do_capability=do_capability,
            decide_capability=decide_capability,
            say_capability=say_capability,
            influence_targets=influence_targets,
            interests_section=interests_section,
            all_entity_names=", ".join(all_entity_names),
            related_edges=related_edges_text,
            neighbors=neighbors_text,
            background=state.background,
            focus=state.focus,
        )

        user_prompt = f"请为实体「{entity.name}」生成完整的 Agent 系统提示词。"

        try:
            response = self.llm_client.invoke(system_prompt, user_prompt, temperature=0.5)
            # Agent Prompt 输出是纯文本 Markdown，不需要 JSON 解析
            # 清理可能的代码块标签
            prompt = response.strip()
            if prompt.startswith("```"):
                lines = prompt.split("\n")
                # 去掉首尾的 ``` 行
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].strip() == "```":
                    lines = lines[:-1]
                prompt = "\n".join(lines)
            return prompt
        except Exception as e:
            self.log_warning(f"Agent Prompt 生成失败 ({entity.name}): {e}")
            return f"你是「{entity.name}」。{entity.description}"

    @staticmethod
    def _format_capability(action_space: dict, action_type: str) -> str:
        """将 v2 能力边界格式化为 Agent Prompt 中可读的文本"""
        cap = action_space.get(action_type, {})

        if isinstance(cap, list):
            # 兼容 v1 格式: list[str]
            if not cap:
                return "- 你不具备此类行动能力"
            cleaned = [a.split(" → ")[0] for a in cap]
            return "- **能力范围**: " + "; ".join(cleaned)

        if isinstance(cap, dict):
            if not cap.get("enabled", False):
                return "- 你不具备此类行动能力"
            parts = []
            scope = cap.get("scope", "")
            if scope:
                parts.append(f"- **能力范围**: {scope}")
            targets = cap.get("influence_targets", [])
            if targets:
                parts.append(f"- **可影响**: {', '.join(targets)}")
            constraints = cap.get("constraints", "")
            if constraints:
                parts.append(f"- **约束**: {constraints}")
            return "\n".join(parts) if parts else "- 你不具备此类行动能力"

    @staticmethod
    def _format_interests_section(entity) -> str:
        """v3: 将结构化利益数据格式化为 agent_prompt 中的可读段落"""
        interests = entity.interests or []
        goal_structure = entity.goal_structure

        if not interests and not goal_structure:
            return "- 从 evidence 中提取该实体的核心利益诉求\n- 短期目标和长期目标"

        lines = []

        # 利益维度按优先级排序
        priority_order = {"core": 0, "important": 1, "secondary": 2}
        satisfaction_emoji = {
            "satisfied": "✅",
            "threatened": "⚠️",
            "under_attack": "🔴",
        }

        sorted_interests = sorted(
            interests,
            key=lambda i: priority_order.get(
                i.get("priority", "important") if isinstance(i, dict) else getattr(i, "priority", "important"),
                1,
            ),
        )

        if sorted_interests:
            lines.append("### 利益维度（按优先级排序）")
            for idx, interest in enumerate(sorted_interests, 1):
                if isinstance(interest, dict):
                    dim = interest.get("dimension", "")
                    desc = interest.get("description", "")
                    pri = interest.get("priority", "important")
                    sat = interest.get("current_satisfaction", "")
                    related = interest.get("related_entities", [])
                else:
                    dim = interest.dimension
                    desc = interest.description
                    pri = interest.priority
                    sat = interest.current_satisfaction
                    related = interest.related_entities

                pri_label = {"core": "核心", "important": "重要", "secondary": "次要"}.get(pri, pri)
                sat_label = satisfaction_emoji.get(sat, "")
                line = f"{idx}. [{pri_label}] {dim} — {desc}（当前: {sat}{sat_label}）"
                if related:
                    line += f"\n   └ 相关方: {', '.join(related)}"
                lines.append(line)

        if goal_structure:
            gs = goal_structure if isinstance(goal_structure, dict) else goal_structure.to_dict()
            lines.append("\n### 目标体系")
            for g in gs.get("survival_goals", []):
                lines.append(f"- 底线: {g}")
            for g in gs.get("strategic_goals", []):
                lines.append(f"- 战略: {g}")
            for g in gs.get("opportunistic_goals", []):
                lines.append(f"- 机会: {g}")
            rc = gs.get("rationality_constraints", "")
            if rc:
                lines.append(f"\n### 决策约束\n{rc}")

        return "\n".join(lines)

        return "- 你不具备此类行动能力"
