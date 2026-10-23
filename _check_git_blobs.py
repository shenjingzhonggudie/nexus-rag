"""验证 git 索引 / HEAD 中归档文件的字节与 ARCHIVE_MANIFEST 记录的 SHA-256 是否一致。"""

import hashlib
import json
import subprocess
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

DEST = Path("C:/Users/王佳浩/Desktop/项目/experiments/holdout-v1")
man = json.loads((DEST / "ARCHIVE_MANIFEST.json").read_text(encoding="utf-8"))


def blob(spec: str, rel: str) -> bytes:
    # spec="" 表示索引（git show :path）；否则 "<rev>:path"
    arg = f":{rel}" if spec == "" else f"{spec}:{rel}"
    return subprocess.run(["git", "show", arg], capture_output=True).stdout


for label, spec in (("索引", ""), ("HEAD", "HEAD")):
    bad = []
    for f in man["files"]:
        rel = f"experiments/holdout-v1/{f['path']}"
        data = blob(spec, rel)
        if not data:
            bad.append((f["path"], "缺失或空"))
            continue
        h = hashlib.sha256(data).hexdigest()
        if h != f["sha256"]:
            bad.append((f["path"], f"manifest={f['sha256'][:8]} blob={h[:8]}"))
    print(f"[{label}] 核对 {len(man['files'])} 个，不符 {len(bad)}")
    for p, why in bad[:5]:
        print(f"   {p}  {why}")

bad_ws = [
    f["path"]
    for f in man["files"]
    if not (DEST / f["path"]).exists()
    or hashlib.sha256((DEST / f["path"]).read_bytes()).hexdigest() != f["sha256"]
]
print(f"[工作区] 不符 {len(bad_ws)}: {bad_ws[:5]}")
