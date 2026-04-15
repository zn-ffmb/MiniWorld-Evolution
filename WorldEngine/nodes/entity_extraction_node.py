# -*- coding: utf-8 -*-
"""
Phase 3: 实体与关系提取节点

LLM 从搜索结果中提取实体(人类类/自然类) + 关系 + 证据。
每个实体/边必须附带 evidence + source_urls，无证据的被 EvidenceValidator 拦截。
"""

import json
from typing import Any, Dict, List
from WorldEngine.nodes.base_node import BaseNode
from WorldEngine.state.models import Entity, Edge
from WorldEngine.prompts.prompts import (
    ENTITY_EXTRACTION_SYSTEM_PROMPT,
    ENTITY_EXTRACTION_EXISTING_CONTEXT,
    ENTITY_EXTRACTION_EMPTY_CONTEXT,
)
from WorldEngine.utils.text_processing import extract_clean_response


class EntityExtractionNode(BaseNode):
    """实体与关系提取节点 — L1 最核心的节点"""

    def run(self, input_data: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """
        从搜索结果中提取实体和关系。

        input_data:
            background, focus, search_results (JSON str),
            existing_entities (summary str), existing_edges (summary str)
        返回:
            {"new_entities": [...], "updated_entities": [...], "new_edges": [...]}
        """
        background = input_data["background"]
        focus = input_data["focus"]
        search_results = input_data["search_results"]
        existing_entities = input_data.get("existing_entities", "")
        existing_edges = input_data.get("existing_edges", "")

        # 构建上下文
        if existing_entities:
            existing_context = ENTITY_EXTRACTION_EXISTING_CONTEXT.format(
                existing_entities=existing_entities,
                existing_edges=existing_edges,
            )
        else:
            existing_context = ENTITY_EXTRACTION_EMPTY_CONTEXT

        system_prompt = ENTITY_EXTRACTION_SYSTEM_PROMPT.format(
            background=background,
            focus=focus,
            existing_context=existing_context,
        )

        user_prompt = f"以下是搜索结果，请从中提取实体和关系:\n\n{search_results}"

        self.log_info("从搜索结果中提取实体和关系...")
        response = self.llm_client.invoke(system_prompt, user_prompt, temperature=0.3)
        result = extract_clean_response(response)

        if "error" in result:
            self.log_error(f"实体提取失败: {result}")
            return {"new_entities": [], "updated_entities": [], "new_edges": []}

        new_entities = result.get("new_entities", [])
        updated_entities = result.get("updated_entities", [])
        new_edges = result.get("new_edges", [])

        self.log_info(
            f"提取: {len(new_entities)} 个新实体, "
            f"{len(updated_entities)} 个更新, "
            f"{len(new_edges)} 条新关系"
        )
        return result


class EvidenceValidator:
    """拦截无证据的实体和边"""

    @staticmethod
    def validate_entity(entity_data: Dict) -> bool:
        """实体必须有至少 1 条 evidence 和 1 条 source_url"""
        evidence = entity_data.get("evidence", [])
        source_urls = entity_data.get("source_urls", [])
        return len(evidence) > 0 and len(source_urls) > 0

    @staticmethod
    def validate_edge(edge_data: Dict) -> bool:
        """边必须有至少 1 条 evidence 和 1 条 source_url"""
        evidence = edge_data.get("evidence", [])
        source_urls = edge_data.get("source_urls", [])
        return len(evidence) > 0 and len(source_urls) > 0

    def filter_extraction(self, extraction: Dict[str, Any]) -> Dict[str, Any]:
        """过滤掉无证据的实体/边"""
        valid_new_entities = []
        rejected_entities = []
        for e in extraction.get("new_entities", []):
            if self.validate_entity(e):
                valid_new_entities.append(e)
            else:
                rejected_entities.append(e)

        valid_new_edges = []
        rejected_edges = []
        for e in extraction.get("new_edges", []):
            if self.validate_edge(e):
                valid_new_edges.append(e)
            else:
                rejected_edges.append(e)

        if rejected_entities or rejected_edges:
            from loguru import logger
            logger.warning(
                f"EvidenceValidator 拦截: "
                f"{len(rejected_entities)} 个无证据实体, "
                f"{len(rejected_edges)} 条无证据关系"
            )

        return {
            "new_entities": valid_new_entities,
            "updated_entities": extraction.get("updated_entities", []),
            "new_edges": valid_new_edges,
        }
