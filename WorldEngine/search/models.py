# -*- coding: utf-8 -*-
"""
搜索结果数据模型

与 PerceptionEngine 保持一致的 SearchTask / SearchResult / SearchResultBundle 结构。
"""

from dataclasses import dataclass, field
from typing import List


@dataclass
class SearchTask:
    """单个搜索任务"""

    task_id: str
    dimension: str          # "impact_factors" / "participants" / "key_questions"
    query: str
    query_variants: List[str] = field(default_factory=list)
    target_source: str = "news"     # "news" / "social" / "report" / "any"
    priority: int = 3               # 1 (最高) - 5 (最低)
    context: str = ""
    max_results: int = 10

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "dimension": self.dimension,
            "query": self.query,
            "query_variants": self.query_variants,
            "target_source": self.target_source,
            "priority": self.priority,
            "context": self.context,
            "max_results": self.max_results,
        }


@dataclass
class SearchResult:
    """单条搜索结果"""

    task_id: str
    dimension: str
    source_type: str        # "news" / "social" / "report"
    source_tool: str
    title: str
    content: str
    url: str
    published_date: str = ""
    relevance_score: float = 0.0
    cluster_id: int = -1

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "dimension": self.dimension,
            "source_type": self.source_type,
            "source_tool": self.source_tool,
            "title": self.title,
            "content": self.content,
            "url": self.url,
            "published_date": self.published_date,
            "relevance_score": self.relevance_score,
            "cluster_id": self.cluster_id,
        }


@dataclass
class SearchResultBundle:
    """全维度搜索结果包"""

    impact_results: List[SearchResult] = field(default_factory=list)
    participant_results: List[SearchResult] = field(default_factory=list)
    question_results: List[SearchResult] = field(default_factory=list)

    sampled_impact: List[SearchResult] = field(default_factory=list)
    sampled_participant: List[SearchResult] = field(default_factory=list)
    sampled_question: List[SearchResult] = field(default_factory=list)

    total_raw_count: int = 0
    total_sampled_count: int = 0
    search_duration_seconds: float = 0.0
    failed_tasks: List[str] = field(default_factory=list)

    @property
    def all_sampled(self) -> List[SearchResult]:
        return self.sampled_impact + self.sampled_participant + self.sampled_question

    def to_dict(self) -> dict:
        return {
            "impact_results": [r.to_dict() for r in self.impact_results],
            "participant_results": [r.to_dict() for r in self.participant_results],
            "question_results": [r.to_dict() for r in self.question_results],
            "sampled_impact": [r.to_dict() for r in self.sampled_impact],
            "sampled_participant": [r.to_dict() for r in self.sampled_participant],
            "sampled_question": [r.to_dict() for r in self.sampled_question],
            "total_raw_count": self.total_raw_count,
            "total_sampled_count": self.total_sampled_count,
            "search_duration_seconds": self.search_duration_seconds,
            "failed_tasks": self.failed_tasks,
        }
