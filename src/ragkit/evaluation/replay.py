"""用已保存的排名和拒答标记重评 v2 证据，不运行检索或验证回答正文。"""

from ragkit.evaluation.evidence import prefix_point_coverage
from ragkit.evaluation.metrics import coverage_recall, first_hit_mrr
from ragkit.evaluation.qrels import Qrel
from ragkit.schemas import Chunk


def _valid_offsets(start: object, end: object) -> bool:
    # bool 是 int 的子类，但不是合法的字符坐标。
    return type(start) is int and type(end) is int and 0 <= start < end


def _validate_inputs(
    qrels: list[Qrel], saved_rows: list[dict], chunks: dict[str, Chunk]
) -> dict[str, dict]:
    if not isinstance(qrels, list) or not isinstance(saved_rows, list):
        raise ValueError("qrels and saved_rows must be lists")
    if not isinstance(chunks, dict):
        raise ValueError("chunks must be a chunk_id -> Chunk dictionary")

    queries: set[str] = set()
    for qrel in qrels:
        if not isinstance(qrel, Qrel):
            raise ValueError("qrels must contain Qrel objects")
        if type(qrel.annotation_version) is not int or qrel.annotation_version != 2:
            raise ValueError("only v2 qrels are supported; mixed/non-v2 qrels are invalid")
        if not isinstance(qrel.query, str) or not qrel.query.strip():
            raise ValueError("qrel query must be a nonempty string")
        if qrel.query in queries:
            raise ValueError(f"duplicate qrel query: {qrel.query!r}")
        queries.add(qrel.query)
        for point in qrel.answer_points:
            for evidence in point.evidence:
                if not _valid_offsets(evidence.start, evidence.end):
                    raise ValueError(f"invalid evidence offsets for query {qrel.query!r}")

    by_query: dict[str, dict] = {}
    checked_chunks: set[str] = set()
    for row in saved_rows:
        if not isinstance(row, dict):
            raise ValueError("each saved row must be a dictionary")
        missing = {"query", "retrieved", "refused"} - row.keys()
        if missing:
            raise ValueError(f"saved row missing required field(s): {', '.join(sorted(missing))}")
        query = row["query"]
        if not isinstance(query, str) or not query.strip():
            raise ValueError("saved query must be a nonempty string")
        if query in by_query:
            raise ValueError(f"duplicate saved query: {query!r}")
        if type(row["refused"]) is not bool:
            raise ValueError(f"refused must be bool for query {query!r}")
        retrieved = row["retrieved"]
        if not isinstance(retrieved, list) or any(
            not isinstance(chunk_id, str) or not chunk_id for chunk_id in retrieved
        ):
            raise ValueError(f"retrieved must be a list of nonempty chunk IDs for {query!r}")
        for chunk_id in retrieved:
            if chunk_id in checked_chunks:
                continue
            if chunk_id not in chunks:
                raise ValueError(f"unknown chunk ID {chunk_id!r} for query {query!r}")
            chunk = chunks[chunk_id]
            if not isinstance(chunk, Chunk) or chunk.chunk_id != chunk_id:
                raise ValueError(f"invalid Chunk mapping for chunk ID {chunk_id!r}")
            if not isinstance(chunk.doc_id, str) or not chunk.doc_id.strip():
                raise ValueError(f"missing/invalid doc_id for chunk ID {chunk_id!r}")
            if not isinstance(chunk.metadata, dict) or not _valid_offsets(
                chunk.metadata.get("char_start"), chunk.metadata.get("char_end")
            ):
                raise ValueError(f"missing/invalid offsets for chunk ID {chunk_id!r}")
            checked_chunks.add(chunk_id)
        by_query[query] = row

    missing_queries = queries - by_query.keys()
    extra_queries = by_query.keys() - queries
    if missing_queries or extra_queries:
        raise ValueError(
            "saved queries must match qrels exactly; "
            f"missing queries: {sorted(missing_queries)!r}; "
            f"extra queries: {sorted(extra_queries)!r}"
        )
    return by_query


def rescore_saved_results(
    qrels: list[Qrel],
    saved_rows: list[dict],
    chunks: dict[str, Chunk],
    *,
    ks: tuple[int, ...] = (1, 3, 5),
) -> dict:
    """按冻结的 v2 标注重评保存结果，返回 JSON 可序列化的指标和明细。

    仅使用每条保存行的 query、retrieved 和布尔 refused，忽略旧分数与
    题型标签。query 必须与 qrels 精确、一一对应。检索顺序和重复块均保留；
    所有被引用的块必须有整数坐标 0 <= char_start < char_end。

    同文档前缀区间取并集；每个要点的所有必要证据都须严格覆盖超过50%。
    needs_review 的已知要点仍显示覆盖明细，但不参与主指标或拒答分母，
    且整题完整命中始终记零。主 Recall/MRR/完整率按已完成可答题宏平均；
    保守完整率另将全部 pending 计入分母。无答案身份只采用 qrel.type。

    不加载文件、模型或索引，不复跑检索，不计算实测 latency，也不验证回答正文。
    输入不匹配、缺字段、非 v2 标注或非法被引用块均抛出 ValueError。
    """
    try:
        ks = tuple(ks)
    except TypeError as exc:
        raise ValueError("ks must contain unique positive integers") from exc
    if not ks or any(type(k) is not int or k <= 0 for k in ks) or len(set(ks)) != len(ks):
        raise ValueError("ks must contain unique positive integers")
    by_query = _validate_inputs(qrels, saved_rows, chunks)

    per_query: list[dict] = []
    for qrel in qrels:
        saved = by_query[qrel.query]
        retrieved = saved["retrieved"].copy()
        prefixes, coverage = prefix_point_coverage(
            [chunks[chunk_id] for chunk_id in retrieved], qrel.answer_points
        )
        total_points = len(qrel.answer_points)
        recall_at = {k: coverage_recall(prefixes, total_points, k) for k in ks}
        evaluated = qrel.annotation_status != "needs_review"
        is_no_answer = qrel.type == "no_answer"
        complete_at = {
            k: float(evaluated and not is_no_answer and total_points > 0 and recall_at[k] == 1.0)
            for k in ks
        }
        per_query.append({
            "id": qrel.id,
            "query": qrel.query,
            "annotation_status": qrel.annotation_status,
            "evaluated": evaluated,
            "is_no_answer": is_no_answer,
            "refused": saved["refused"],
            "retrieved": retrieved,
            "hits_by_prefix": [sorted(hits) for hits in prefixes],
            "point_coverage_by_prefix": coverage,
            "point_labels": [point.point for point in qrel.answer_points],
            "recall_at": recall_at,
            "mrr": first_hit_mrr(prefixes),
            "complete_at": complete_at,
        })

    answerable = [row for row in per_query if row["evaluated"] and not row["is_no_answer"]]
    no_answer = [row for row in per_query if row["evaluated"] and row["is_no_answer"]]
    n_answerable = len(answerable)
    n_no_answer = len(no_answer)
    n_pending = sum(not row["evaluated"] for row in per_query)
    conservative_denominator = n_answerable + n_pending
    complete_counts = {k: sum(row["complete_at"][k] for row in answerable) for k in ks}
    correct_refusals = sum(row["refused"] for row in no_answer)
    false_refusals = sum(row["refused"] for row in answerable)

    return {
        "scoring": {
            "mode": "saved_retrieval_evidence_regrade",
            "annotation_version": 2,
            "threshold": 0.5,
            "comparison": ">",
            "denominator": "evidence_characters",
            "union_by_document": True,
            "necessary_supports": "all",
            "recall_unit": "answer_points",
            "averaging": "macro_by_query",
            "mrr_target": "first_supported_point_prefix",
            "pending_policy": "excluded_from_primary_metrics_and_always_incomplete",
            "scope": "retrieval_evidence_not_answer_correctness",
            "latency_measured": False,
            "answer_text_verified": False,
        },
        "n_queries": len(per_query),
        "n_answerable": n_answerable,
        "n_no_answer": n_no_answer,
        "n_pending": n_pending,
        "recall_at": {
            k: sum(row["recall_at"][k] for row in answerable) / n_answerable
            if n_answerable else 0.0 for k in ks
        },
        "mrr": sum(row["mrr"] for row in answerable) / n_answerable if n_answerable else 0.0,
        "complete_at": {
            k: complete_counts[k] / n_answerable if n_answerable else 0.0 for k in ks
        },
        "refusal": {
            "correct": correct_refusals,
            "total": n_no_answer,
            "accuracy": correct_refusals / n_no_answer if n_no_answer else 0.0,
            "false_refusals": false_refusals,
            "answerable_total": n_answerable,
            "false_rate": false_refusals / n_answerable if n_answerable else 0.0,
        },
        "conservative_complete": {
            "denominator": conservative_denominator,
            "complete_at": {
                k: complete_counts[k] / conservative_denominator
                if conservative_denominator else 0.0 for k in ks
            },
        },
        "per_query": per_query,
    }
