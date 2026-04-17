# -*- coding: utf-8 -*-
"""
Phase 3: 实体与关系提取节点

LLM 从搜索结果中提取实体(人类类/自然类) + 关系 + 证据。
每个实体/边必须附带 evidence + source_urls，无证据的被 EvidenceValidator 拦截。

v3: 搜索结果 > BATCH_THRESHOLD 条时自动分批提取，每批携带前批已提取实体上下文。
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

# 搜索结果超过此数量时自动分批提取
BATCH_THRESHOLD = 20
BATCH_SIZE = 15


class EntityExtractionNode(BaseNode):
    """实体与关系提取节点 — L1 最核心的节点"""

    def run(self, input_data: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """
        从搜索结果中提取实体和关系。自动判断是否需要分批。

        input_data:
            background, focus, search_results (JSON str),
            existing_entities (summary str), existing_edges (summary str)
        返回:
            {"new_entities": [...], "updated_entities": [...], "new_edges": [...]}
            或包含 "error" 字段的 dict
        """
        search_results = input_data["search_results"]

        # 计算搜索结果条数（粗略估算）
        result_count = search_results.count('"url"') if isinstance(search_results, str) else 0

        if result_count > BATCH_THRESHOLD:
            self.log_info(f"搜索结果 {result_count} 条 > {BATCH_THRESHOLD}，启用分批提取")
            return self._run_batched(input_data)
        else:
            return self._run_single(input_data)

    def _run_single(
        self, input_data: Dict[str, Any],
        extra_existing_entities: str = "",
    ) -> Dict[str, Any]:
        """单次提取（原有逻辑）"""
        background = input_data["background"]
        focus = input_data["focus"]
        search_results = input_data["search_results"]
        existing_entities = input_data.get("existing_entities", "")
        existing_edges = input_data.get("existing_edges", "")

        # 合并额外的已有实体上下文（分批时使用）
        if extra_existing_entities:
            if existing_entities:
                existing_entities = existing_entities + "\n" + extra_existing_entities
            else:
                existing_entities = extra_existing_entities

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

        response = self.llm_client.invoke(system_prompt, user_prompt, temperature=0.3)
        result = extract_clean_response(response)

        if "error" in result:
            self.log_error(f"实体提取失败: {result}")
            return result

        return result

    def _run_batched(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        分批提取：将搜索结果按 BATCH_SIZE 分割，
        每批携带前面已提取的实体列表作为上下文。
        """
        search_results_str = input_data["search_results"]

        # 按 JSON 数组元素分割搜索结果
        batches = self._split_search_results(search_results_str, BATCH_SIZE)
        self.log_info(f"分为 {len(batches)} 批提取")

        all_new_entities = []
        all_updated_entities = []
        all_new_edges = []
        accumulated_entity_summaries = ""

        for batch_idx, batch_text in enumerate(batches):
            self.log_info(f"提取批次 {batch_idx + 1}/{len(batches)}...")

            batch_input = {
                **input_data,
                "search_results": batch_text,
            }

            result = self._run_single(
                batch_input,
                extra_existing_entities=accumulated_entity_summaries,
            )

            if "error" in result:
                self.log_warning(
                    f"批次 {batch_idx + 1} 提取失败，跳过: {result.get('error')}"
                )
                continue

            batch_entities = result.get("new_entities", [])
            batch_updated = result.get("updated_entities", [])
            batch_edges = result.get("new_edges", [])

            self.log_info(
                f"批次 {batch_idx + 1}: "
                f"{len(batch_entities)} 个新实体, "
                f"{len(batch_updated)} 个更新, "
                f"{len(batch_edges)} 条新关系"
            )

            all_new_entities.extend(batch_entities)
            all_updated_entities.extend(batch_updated)
            all_new_edges.extend(batch_edges)

            # 累积已提取的实体摘要，供下一批使用
            for e in batch_entities:
                name = e.get("name", e.get("id", ""))
                etype = e.get("type", "")
                desc = e.get("description", "")[:80]
                accumulated_entity_summaries += f"\n- [{etype}] {name}: {desc}"

        if not all_new_entities and not all_updated_entities:
            self.log_warning("所有批次均未提取到实体")

        self.log_info(
            f"分批提取汇总: {len(all_new_entities)} 个新实体, "
            f"{len(all_updated_entities)} 个更新, "
            f"{len(all_new_edges)} 条新关系"
        )

        return {
            "new_entities": all_new_entities,
            "updated_entities": all_updated_entities,
            "new_edges": all_new_edges,
        }

    @staticmethod
    def _split_search_results(results_str: str, batch_size: int) -> List[str]:
        """
        将搜索结果 JSON 字符串按条目数分割。
        搜索结果是一个 JSON 数组字符串或混合文本。
        """
        try:
            results_list = json.loads(results_str)
            if isinstance(results_list, list):
                batches = []
                for i in range(0, len(results_list), batch_size):
                    batch = results_list[i:i + batch_size]
                    batches.append(json.dumps(batch, ensure_ascii=False))
                return batches if batches else [results_str]
        except (json.JSONDecodeError, TypeError):
            pass

        # 回退：按文本块分割（以 \n[ 或 \n{ 为分隔符粗略切分）
        lines = results_str.split("\n")
        chunk_size = max(len(lines) // 3, 1)
        batches = []
        for i in range(0, len(lines), chunk_size):
            chunk = "\n".join(lines[i:i + chunk_size])
            if chunk.strip():
                batches.append(chunk)
        return batches if batches else [results_str]


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
