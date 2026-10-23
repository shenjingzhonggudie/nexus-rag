import sys
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
for sub in ("src/ragkit", "tests"):
    print("=== %s ===" % sub)
    for p in sorted(Path(sub).rglob("*")):
        if not p.is_file() or "__pycache__" in str(p) or p.suffix == ".pyc":
            continue
        rel = p.relative_to(sub).as_posix()
        n = len(p.read_text(encoding="utf-8", errors="ignore").splitlines())
        print("%-46s %5d" % (rel, n))
    print()
