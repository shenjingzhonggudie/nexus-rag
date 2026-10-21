"""从公开技术文档仓库拉取语料（需要联网）。

设计原则
--------
- **保留来源与许可证**：每个源记录 name / repo / license，下载后写
  ``data/SOURCES.md``；README 引用它。仓库里只提交脚本与清单，不提交第三方
  文档正文——规避许可证与体积问题。
- **以目录为单位抓取**：用 GitHub API 列目录、再用 raw 地址下载文件。
  列目录消耗 API 配额（未认证 60 次/小时），下载不消耗，所以每个技术栈只
  列 1~2 个目录即可。
- **容错**：单个文件失败不影响其他；失败清单打印出来供人工补。

用法
----
    python scripts/fetch_docs.py --list          # 只看清单
    python scripts/fetch_docs.py                 # 全部下载
    python scripts/fetch_docs.py --only k8s      # 只下某个技术栈

抓下来的文件会按 ``data/raw/<stack>/<文件名>.md`` 存放。文件名沿用仓库里的
名字，但把目录层级压平并加前缀，避免不同目录的同名文件互相覆盖。
"""

import argparse
import json
import re
import time
import urllib.error
import urllib.request
from pathlib import Path

RAW_DIR = Path("data/raw")
SOURCES_FILE = Path("data/SOURCES.md")

# 每个源：技术栈 / 展示名 / GitHub 仓库 / 中文目录 / 许可证
# 只收录确认存在、且允许再分发的公开仓库；许可证以下面记录为准。
SOURCES: list[dict] = [
    {
        "stack": "k8s",
        "name": "Kubernetes 中文文档（概念篇）",
        "repo": "kubernetes/website",
        "dirs": ["content/zh-cn/docs/concepts"],
        "license": "CC BY 4.0",
    },
    {
        "stack": "tidb",
        "name": "TiDB 中文文档（开发指南）",
        "repo": "pingcap/docs-cn",
        "dirs": ["develop"],
        "license": "Apache-2.0",
    },
    {
        "stack": "vue",
        "name": "Vue 3 中文文档",
        "repo": "vuejs-translations/docs-zh-cn",
        "dirs": ["src/guide"],
        "license": "MIT",
    },
    {
        "stack": "react",
        "name": "React 中文文档",
        "repo": "reactjs/zh-hans.react.dev",
        "dirs": ["src/content/learn"],
        "license": "CC BY 4.0",
    },
]


def _fetch_bytes(url: str, *, timeout: int, attempts: int = 3) -> bytes:
    """带重试地抓取一个 URL。

    网络偶发 ``SSL: UNEXPECTED_EOF_WHILE_READING`` 是常见的瞬时故障，
    单次失败不代表资源不存在，所以统一重试 3 次（退避 0.8s / 1.6s）。
    """
    last: Exception | None = None
    for attempt in range(attempts):
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": "ragkit-fetch/1.0"}
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read()
        except urllib.error.HTTPError as exc:
            if exc.code == 404:  # 真不存在，重试无意义
                raise
            last = exc
        except (urllib.error.URLError, OSError) as exc:
            last = exc
        time.sleep(0.8 * (attempt + 1))
    assert last is not None
    raise last


def _request_json(url: str):
    """请求 GitHub API 并解析 JSON（带重试与 User-Agent）。"""
    return json.loads(_fetch_bytes(url, timeout=30).decode("utf-8"))


def _download(url: str) -> bytes:
    """下载 raw 文件内容（带重试）。"""
    return _fetch_bytes(url, timeout=60)


def _slug(path: str) -> str:
    """把仓库内的相对路径压成安全的扁平文件名（层级用 ``__`` 分隔）。"""
    cleaned = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff._/-]+", "-", path).strip("-/")
    return cleaned.replace("/", "__").replace(".md", "")


def _list_tree(repo: str, directory: str) -> list[dict]:
    """用 git trees API 递归列出目录下的 markdown 文件（每仓库只消耗 1 次配额）。

    Args:
        repo: ``owner/name`` 形式的仓库。
        directory: 仓库内的目录前缀。

    Returns:
        list[dict]: 每项含 ``path``（仓库内相对路径）与 ``download_url``。

    Raises:
        ValueError: main / master 分支都取不到树时抛出。
    """
    for branch in ("main", "master"):
        url = f"https://api.github.com/repos/{repo}/git/trees/{branch}?recursive=1"
        try:
            data = _request_json(url)
        except urllib.error.HTTPError as exc:
            if exc.code == 404:  # 分支不存在，换下一个
                continue
            raise
        prefix = directory.rstrip("/") + "/"
        return [
            {
                "path": item["path"],
                "download_url": (
                    f"https://raw.githubusercontent.com/{repo}/{branch}/{item['path']}"
                ),
            }
            for item in data.get("tree", [])
            if item.get("type") == "blob"
            and item["path"].startswith(prefix)
            and item["path"].endswith(".md")
        ]
    raise ValueError(f"{repo} 的 main / master 分支都取不到文件树")


def fetch(source: dict, *, limit: int) -> tuple[int, list[str]]:
    """抓取一个源的全部 markdown 文件。

    Args:
        source: SOURCES 里的一项。
        limit: 每个目录最多抓多少个文件（控制规模与耗时）。

    Returns:
        tuple[int, list[str]]: (成功数, 失败说明列表)。
    """
    out_dir = RAW_DIR / source["stack"]
    out_dir.mkdir(parents=True, exist_ok=True)

    ok = 0
    failures: list[str] = []
    for directory in source["dirs"]:
        try:
            files = _list_tree(source["repo"], directory)[:limit]
        except (urllib.error.URLError, urllib.error.HTTPError, ValueError) as exc:
            failures.append(f"{source['stack']} 列目录失败 {directory}: {exc}")
            continue

        for item in files:
            target = out_dir / f"{_slug(item['path'])}.md"
            try:
                target.write_bytes(_download(item["download_url"]))
                ok += 1
            except (urllib.error.URLError, urllib.error.HTTPError) as exc:
                failures.append(f"{source['stack']} 下载失败 {item['path']}: {exc}")
    return ok, failures


def write_sources_md(chosen: list[dict]) -> None:
    """写数据来源与许可证清单（README 会引用它）。"""
    lines = [
        "# 数据来源与许可证",
        "",
        "本项目语料来自以下公开文档仓库，按各自许可证使用。",
        "仓库内**不提交**这些文档正文，由 `scripts/fetch_docs.py` 按需拉取。",
        "",
        "| 技术栈 | 来源 | 仓库 | 许可证 |",
        "|---|---|---|---|",
    ]
    for source in chosen:
        lines.append(
            f"| {source['stack']} | {source['name']} | `{source['repo']}` | {source['license']} |"
        )
    lines.append("")
    SOURCES_FILE.parent.mkdir(parents=True, exist_ok=True)
    SOURCES_FILE.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    """命令行入口：列清单 / 下载。"""
    parser = argparse.ArgumentParser(description="从公开仓库拉取中文技术文档")
    parser.add_argument("--list", action="store_true", help="只打印清单，不下载")
    parser.add_argument("--only", default="", help="只处理指定技术栈（如 k8s）")
    parser.add_argument("--limit", type=int, default=25, help="每个目录最多抓几个文件（按路径排序取前 N 个）")
    args = parser.parse_args()

    chosen = [s for s in SOURCES if not args.only or s["stack"] == args.only]
    if not chosen:
        print(f"没有匹配的技术栈：{args.only}")
        return

    if args.list:
        for source in chosen:
            print(
                f"{source['stack']:<8}{source['name']}\n"
                f"         仓库 {source['repo']}  目录 {source['dirs']}  "
                f"许可证 {source['license']}"
            )
        return

    total_ok = 0
    all_failures: list[str] = []
    for source in chosen:
        ok, failures = fetch(source, limit=args.limit)
        total_ok += ok
        all_failures.extend(failures)
        print(f"{source['stack']}: 成功 {ok} 篇" + (f"，失败 {len(failures)} 项" if failures else ""))

    # 始终写完整来源清单：--only 只影响下载范围，不该让 SOURCES.md 丢掉其他源
    write_sources_md(SOURCES)
    print(f"\n合计 {total_ok} 篇 → {RAW_DIR}")
    print(f"来源与许可证 → {SOURCES_FILE}")
    if all_failures:
        print("\n以下项失败，请检查网络或手动补：")
        for line in all_failures[:20]:
            print(f"  - {line}")


if __name__ == "__main__":
    main()
