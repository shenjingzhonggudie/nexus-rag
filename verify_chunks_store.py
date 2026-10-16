"""临时验证：chunks.jsonl 坏行报错带行号。验证完保留（用户偏好：临时脚本不删）。"""

from pathlib import Path
import tempfile

from ragkit.index import read_chunks, write_chunks
from ragkit.schemas import Chunk

d = Path(tempfile.mkdtemp())
p = d / "chunks.jsonl"

# 第 1 行合法、第 2 行坏 JSON、第 3 行缺必填字段
c = Chunk(chunk_id="a#x@0", doc_id="a", text="正文", ordinal=0)
p.write_text(
    p.parent.as_uri() and ""  # noqa: 占位，下面直接覆盖
    or "",
    encoding="utf-8",
)
lines = [
    '{"chunk_id": "a#x@0", "doc_id": "a", "text": "正文", "ordinal": 0}',
    "{bad json}",
    '{"doc_id": "b"}',
]
p.write_text("\n".join(lines) + "\n", encoding="utf-8")

try:
    read_chunks(p)
    print("意外通过：坏行没有被拦住")
except ValueError as e:
    print("坏行报错 OK:", e)

# 对照：合法文件正常读
write_chunks(p, [c])
print("对照正常读:", [x.chunk_id for x in read_chunks(p)])
