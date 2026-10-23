import sys
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
SKIP = {".venv",".git","__pycache__",".pytest_cache","data/raw","data/index","data/index.hashing"}
rows = []
for p in sorted(Path(".").rglob("*")):
    if not p.is_file(): continue
    rel = p.relative_to(".").as_posix()
    if any(rel == d or rel.startswith(d + "/") for d in SKIP): continue
    if p.suffix in {".pyc",".npy"}: continue
    rows.append((rel, p.stat().st_size))
head = [r for r in rows if not r[0].startswith(("src/ragkit/","tests/","experiments/"))]
arch = [r for r in rows if r[0].startswith("experiments/")]
print("非 src/tests 文件:", len(head))
for rel, size in head:
    print("%s\t%d" % (rel, size))
print()
print("归档文件数:", len(arch))
