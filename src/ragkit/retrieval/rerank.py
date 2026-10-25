"""用 CrossEncoder 对融合候选的 query/text 对重新打分。

融合负责合并召回通道；本模块只使用问题与片段正文估计相关性。输出分数是
模型的原始 logit，可以为负，不表示概率，也不应用于规则拒答阈值。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from math import isfinite
from numbers import Integral
from threading import Lock
from typing import Any

import numpy as np

from ragkit.errors import RerankError
from ragkit.schemas import ScoredChunk


@dataclass
class _CachedModel:
    """同一配置复用模型，并串行调用可能改变模型内部状态的 predict。"""

    model: Any
    predict_lock: Any = field(default_factory=Lock)


_MODEL_CACHE: dict[tuple[str, str, int, bool], _CachedModel] = {}
_MODEL_CACHE_LOCK = Lock()


def _load_model(
    model_name: str, device: str, max_length: int, local_files_only: bool
) -> _CachedModel:
    """按完整加载配置缓存模型；加载失败不缓存，也不修改 embedding 状态。"""
    key = (model_name, device, max_length, local_files_only)
    with _MODEL_CACHE_LOCK:
        cached = _MODEL_CACHE.get(key)
        if cached is not None:
            return cached

        # 可选依赖仅在确有候选需要评分时导入。
        try:
            import torch
            from sentence_transformers import CrossEncoder
        except ImportError as exc:
            raise RerankError(
                "CrossEncoder reranking requires sentence-transformers>=6.1 and "
                "torch; install ragkit[rerank]."
            ) from exc
        except Exception as exc:
            raise RerankError(
                f"Failed to import CrossEncoder reranking dependencies: {exc}"
            ) from exc

        try:
            model = CrossEncoder(
                model_name,
                max_length=max_length,
                device=device,
                local_files_only=local_files_only,
                trust_remote_code=False,
                activation_fn=torch.nn.Identity(),
            )
            # 不传 num_labels：强行改成 1 会替换不兼容模型的原生分类头。
            native_labels = model.num_labels
            if (
                isinstance(native_labels, bool)
                or not isinstance(native_labels, Integral)
                or native_labels != 1
            ):
                raise RerankError(
                    f"CrossEncoder {model_name!r} must natively have num_labels=1; "
                    f"got {native_labels!r}."
                )
        except RerankError:
            raise
        except Exception as exc:
            raise RerankError(
                f"Failed to load CrossEncoder {model_name!r} "
                f"(device={device!r}, local_files_only={local_files_only}): {exc}"
            ) from exc

        cached = _CachedModel(model=model)
        _MODEL_CACHE[key] = cached
        return cached


def _validate_scores(raw_scores: Any, count: int) -> np.ndarray:
    """只接受每个候选一个有限实数；不将多分类输出摊平为相关性分。"""
    try:
        scores = np.asarray(raw_scores)
        if scores.shape == (count, 1):
            scores = scores[:, 0]
        elif scores.shape != (count,):
            raise RerankError(
                f"CrossEncoder returned score shape {scores.shape}; "
                f"expected ({count},) or ({count}, 1)."
            )

        if not (
            np.issubdtype(scores.dtype, np.integer)
            or np.issubdtype(scores.dtype, np.floating)
        ):
            raise RerankError(
                f"CrossEncoder scores must be real numbers; got dtype {scores.dtype}."
            )
        if not np.isfinite(scores).all():
            raise RerankError("CrossEncoder scores must be finite; got NaN or infinity.")
        if not all(isfinite(float(score)) for score in scores):
            raise RerankError("CrossEncoder scores must remain finite as Python floats.")
        return scores
    except RerankError:
        raise
    except Exception as exc:
        raise RerankError(f"Invalid CrossEncoder scores: {exc}") from exc


def rerank(
    query: str,
    candidates: list[ScoredChunk],
    *,
    final_k: int,
    model_name: str = "BAAI/bge-reranker-base",
    batch_size: int = 16,
    max_length: int = 512,
    device: str = "cpu",
    local_files_only: bool = True,
) -> list[ScoredChunk]:
    """用 query 与片段正文成对推理，再按独立相关性分取前 final_k 个。

    Args:
        query: 用户问题；存在候选时必须是非空白字符串。
        candidates: 融合阶段的有序候选；重复 chunk_id 只保留首次出现的块。
        final_k: 最多保留的块数，必须为正整数。
        model_name: CrossEncoder 模型名称或本地路径，必须是非空白字符串。
        batch_size: 交给模型 predict 的批大小，必须为正整数。
        max_length: 问题和正文合并后的模型输入长度上限，必须为正整数。
        device: 模型运行设备，默认 cpu。
        local_files_only: 默认只允许从本地缓存或路径加载模型。

    Returns:
        list[ScoredChunk]: 按原始 logit 降序，stage 为 rerank。同分保持融合
            顺序；原候选、片段及 metadata 均不修改。空候选不导入模型依赖。

    Raises:
        ValueError: 参数不合法，或有候选时问题为空白。
        RerankError: 依赖缺失、模型加载或推理失败，或模型输出不合契约。
    """
    for name, value in (
        ("final_k", final_k), ("batch_size", batch_size), ("max_length", max_length)
    ):
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise ValueError(f"{name} must be a positive integer.")
    if not isinstance(model_name, str) or not model_name.strip():
        raise ValueError("model_name must be a non-empty string.")
    if not isinstance(device, str) or not device.strip():
        raise ValueError("device must be a non-empty string.")
    if not isinstance(local_files_only, bool):
        raise ValueError("local_files_only must be a boolean.")
    if not candidates:
        return []
    if not isinstance(query, str) or not query.strip():
        raise ValueError("query must be a non-empty string when candidates are present.")

    unique: dict[str, ScoredChunk] = {}
    for candidate in candidates:
        unique.setdefault(candidate.chunk.chunk_id, candidate)
    ordered = list(unique.values())
    pairs = [(query, candidate.chunk.text) for candidate in ordered]
    cached = _load_model(model_name, device, max_length, local_files_only)
    try:
        with cached.predict_lock:
            raw_scores = cached.model.predict(
                pairs,
                batch_size=batch_size,
                show_progress_bar=False,
                convert_to_numpy=True,
            )
    except Exception as exc:
        raise RerankError(f"CrossEncoder {model_name!r} inference failed: {exc}") from exc

    scores = _validate_scores(raw_scores, len(ordered))
    # 按原始精度排序，避免转换到 Python float 后把不同分数压成同分。
    ranked_indices = sorted(
        range(len(ordered)), key=lambda index: scores[index], reverse=True
    )[:final_k]
    return [
        ScoredChunk(
            chunk=ordered[index].chunk,
            score=float(scores[index]),
            stage="rerank",
            sub_scores=ordered[index].sub_scores.copy(),
        )
        for index in ranked_indices
    ]
