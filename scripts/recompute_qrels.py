"""重算 qrels 的字符区间：HTML 注释剥离后，原文坐标变了。

标注格式是「文档 + 小节标题 + 字符区间」，所以只要小节标题还在，
就能重新定位区间——这是当初"标注不绑切分"设计的直接收益。
"""

import json
import sys
from pathlib import Path

from ragkit.chunking import iter_heading_sections
from ragkit.loaders import load_file
from ragkit.text import clean_heading
from ragkit.text.normalize import normalize_text

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

QRELS = Path("data/eval/qrels.json")
qrels = json.loads(QRELS.read_text(encoding="utf-8"))

_cache: dict[str, dict[str, tuple[int, int]]] = {}


def section_map(doc_id: str) -> dict[str, tuple[int, int]]:
    """某篇文档的 小节标题 -> 字符区间（按当前 loader 的产出坐标）。"""
    if doc_id not in _cache:
        doc = load_file(Path("data/raw", doc_id))
        normalized = normalize_text(doc.text)
        mapping: dict[str, tuple[int, int]] = {}
        for start, end in iter_heading_sections(normalized):
            body = normalized[start:end]
            if not body.strip():
                continue
            mapping[clean_heading(body.splitlines()[0])] = (start, end)
        _cache[doc_id] = mapping
    return _cache[doc_id]


ok = 0
failed: list[str] = []
for q in qrels:
    for answer in q.get("answers", []):
        span = section_map(answer["doc"]).get(answer["section"])
        if span is None:
            failed.append(f"{answer['doc']} :: {answer['section'][:50]}")
            continue
        answer["start"], answer["end"] = span
        ok += 1

QRELS.write_text(json.dumps(qrels, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"重算成功 {ok} 个区间，失败 {len(failed)} 个")
for line in failed[:20]:
    print("  未找到:", line)
