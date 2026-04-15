# -*- coding: utf-8 -*-
"""
聚类采样器 — 自实现 KMeans++ 语义聚类

当某维度的搜索结果数量超过阈值时，使用 sentence-transformers 将
结果映射到向量空间，KMeans++ 分簇后每簇取最靠近质心的结果作为代表。

无 scikit-learn 依赖 — 仅需 numpy + sentence-transformers。
"""

from pathlib import Path
from typing import List

import numpy as np
from loguru import logger

from WorldEngine.search.models import SearchResult

# 项目本地模型路径（优先使用，避免依赖 HuggingFace 缓存）
_LOCAL_MODEL_DIR = Path(__file__).resolve().parents[2] / "models" / "paraphrase-multilingual-MiniLM-L12-v2"


def _resolve_model_path(model_name: str) -> str:
    """如果项目本地存在模型快照，返回本地路径；否则回退到在线名称。"""
    snapshots = _LOCAL_MODEL_DIR / "snapshots"
    if snapshots.is_dir():
        # 取第一个快照（通常只有一个 commit hash 目录）
        for child in snapshots.iterdir():
            if child.is_dir() and (child / "config.json").exists():
                return str(child)
    return model_name


class ClusterSampler:
    """
    搜索结果聚类采样器

    - 当结果数 <= max_sampled 时直接返回（不触发模型加载）
    - 超过阈值时延迟加载 sentence-transformers 模型并执行 KMeans++ 采样
    - 每个簇选择最靠近质心的结果作为代表
    """

    _model = None  # 延迟加载，进程内单例

    def __init__(
        self,
        max_sampled: int = 15,
        model_name: str = "paraphrase-multilingual-MiniLM-L12-v2",
    ):
        self.max_sampled = max_sampled
        self.model_name = model_name

    def sample(self, results: List[SearchResult]) -> List[SearchResult]:
        if len(results) <= self.max_sampled:
            return results

        logger.info(
            f"ClusterSampler: {len(results)} 条结果 → 采样 {self.max_sampled} 条"
        )

        texts = [f"{r.title} {r.content[:200]}" for r in results]
        embeddings = self._encode(texts)
        labels = self._kmeans(embeddings, self.max_sampled)

        sampled: List[SearchResult] = []
        for cluster_id in range(self.max_sampled):
            indices = [i for i, lb in enumerate(labels) if lb == cluster_id]
            if not indices:
                continue
            cluster_vecs = embeddings[indices]
            centroid = cluster_vecs.mean(axis=0)
            dists = np.linalg.norm(cluster_vecs - centroid, axis=1)
            best_local = int(np.argmin(dists))
            best_global = indices[best_local]
            chosen = results[best_global]
            chosen.cluster_id = cluster_id
            sampled.append(chosen)

        logger.info(f"ClusterSampler: 最终保留 {len(sampled)} 条结果")
        return sampled

    def _encode(self, texts: List[str]) -> np.ndarray:
        if ClusterSampler._model is None:
            resolved = _resolve_model_path(self.model_name)
            logger.info(f"加载 sentence-transformers 模型: {resolved}")
            from sentence_transformers import SentenceTransformer
            ClusterSampler._model = SentenceTransformer(resolved)
        return ClusterSampler._model.encode(texts, show_progress_bar=False)

    @staticmethod
    def _kmeans(
        data: np.ndarray, k: int, max_iter: int = 50, seed: int = 42
    ) -> np.ndarray:
        """轻量 KMeans++ 实现，无 scikit-learn 依赖。"""
        rng = np.random.RandomState(seed)
        n = data.shape[0]
        k = min(k, n)

        # KMeans++ 初始化
        centers = [data[rng.randint(n)]]
        for _ in range(1, k):
            dists = np.min(
                [np.linalg.norm(data - c, axis=1) ** 2 for c in centers], axis=0
            )
            probs = dists / dists.sum()
            cumprobs = np.cumsum(probs)
            r = rng.rand()
            idx = int(np.searchsorted(cumprobs, r))
            idx = min(idx, n - 1)
            centers.append(data[idx])
        centers = np.array(centers)

        labels = np.zeros(n, dtype=int)
        for _ in range(max_iter):
            dists_all = np.array(
                [np.linalg.norm(data - c, axis=1) for c in centers]
            )  # shape (k, n)
            new_labels = np.argmin(dists_all, axis=0)
            if np.array_equal(new_labels, labels):
                break
            labels = new_labels
            for j in range(k):
                members = data[labels == j]
                if len(members) > 0:
                    centers[j] = members.mean(axis=0)

        return labels
