"""按同文档区间并集评估回答要点；每段必要证据覆盖严格超过50%。"""

from collections.abc import Sequence

from ragkit.evaluation.qrels import AnswerPoint, AnswerSection
from ragkit.schemas import Chunk


def _merge(spans: list[tuple[int, int]]) -> list[tuple[int, int]]:
    merged: list[tuple[int, int]] = []
    for start, end in sorted(spans):
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def _covered_length(evidence: AnswerSection, spans: list[tuple[int, int]]) -> int:
    """spans 已合并、互不重叠，裁剪到证据范围后相加。"""
    return sum(max(0, min(end, evidence.end) - max(start, evidence.start))
               for start, end in spans)


def prefix_point_coverage(
    chunks: Sequence[Chunk], points: tuple[AnswerPoint, ...]
) -> tuple[list[set[int]], list[list[float]]]:
    """返回每个排名前缀命中的要点及最弱必要证据覆盖比例。

    分母始终是证据长度，不是检索块长度。重复和重叠块不重复计数；
    不同文档不拼接。同一要点的每段必要证据均须满足 covered*2 > length。
    """
    by_doc: dict[str, list[tuple[int, int]]] = {}
    hits_by_prefix: list[set[int]] = []
    coverage_by_prefix: list[list[float]] = []
    for chunk in chunks:
        start = chunk.metadata.get("char_start")
        end = chunk.metadata.get("char_end")
        if isinstance(start, int) and isinstance(end, int) and 0 <= start < end:
            by_doc[chunk.doc_id] = _merge([*by_doc.get(chunk.doc_id, []), (start, end)])
        hits: set[int] = set()
        point_coverage: list[float] = []
        for index, point in enumerate(points):
            covered = [_covered_length(e, by_doc.get(e.doc, [])) for e in point.evidence]
            lengths = [e.end - e.start for e in point.evidence]
            point_coverage.append(min(n / length for n, length in zip(covered, lengths)))
            if all(n * 2 > length for n, length in zip(covered, lengths)):
                hits.add(index)
        hits_by_prefix.append(hits)
        coverage_by_prefix.append(point_coverage)
    return hits_by_prefix, coverage_by_prefix
