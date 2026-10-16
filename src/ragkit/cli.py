"""命令行入口：ragkit build（建库）与 ragkit ask（问答）。

薄壳契约：本模块只做三件事——解析参数、调领域函数、格式化输出。
不装任何业务逻辑（阈值、排序、过滤都不进 CLI），不 import numpy / jieba。
领域层的 import 全部延迟到子命令函数内：--version / --help 秒回，
不触发 jieba / numpy 的加载。
"""

import argparse
import sys
from collections.abc import Mapping
from pathlib import Path

from ragkit import __version__


def main(
    argv: list[str] | None = None,
    environ: Mapping[str, str] | None = None,
) -> int:
    """RAGKit 命令行入口。

    Args:
        argv: 要解析的参数列表；None 时读取真实命令行参数。
        environ: 环境变量映射；None 时读取当前进程环境。参数化是为了
            测试隔离（第 5 轮结论：参数可注入 = 测试可隔离），行为向后
            兼容（第 0 课的 main(argv) 调用不受影响）。

    Returns:
        int: 退出码。0 = 成功（含拒答——拒答是业务正常结果，第 16 轮
            决策 1）；1 = 运行错误（配置非法、索引缺失或损坏、语料目录
            不存在）；2 = 用法错误（argparse 自带）。
    """
    parser = argparse.ArgumentParser(
        prog="ragkit",
        description="From-scratch Chinese technical-doc RAG system",
    )
    parser.add_argument(
        "--version", action="store_true", help="显示 RAGKit 的版本号"
    )

    sub = parser.add_subparsers(dest="command")
    p_build = sub.add_parser("build", help="从语料目录建库到 index_dir")
    p_build.add_argument("--config", default=None, help="YAML 配置路径（省略时用默认值 + 环境变量）")
    p_build.add_argument("--root", default=None, help="语料目录（默认 cfg.data_dir，可被环境变量覆盖）")

    p_ask = sub.add_parser("ask", help="提问并回答")
    p_ask.add_argument("query", help="问题文本")
    p_ask.add_argument("--config", default=None, help="YAML 配置路径（省略时用默认值 + 环境变量）")

    args = parser.parse_args(argv)

    if args.version:
        print(f"ragkit {__version__}")
        return 0
    if args.command is None:
        parser.print_help()
        return 0
    if args.command == "build":
        return _cmd_build(args, environ)
    return _cmd_ask(args, environ)


def _cmd_build(args, environ: Mapping[str, str] | None) -> int:
    """建库子命令：load_config → build → 打印统计。"""
    from ragkit.config import load_config
    from ragkit.errors import RagkitError
    from ragkit.index import build as build_index

    try:
        cfg = load_config(args.config, environ)
        # 决策 2：默认 cfg.data_dir（配置给默认、环境变量可覆盖），--root 显式最高
        root = Path(args.root) if args.root else cfg.data_dir
        built = build_index(root, cfg)
    except FileNotFoundError as e:
        print(f"错误：{e}", file=sys.stderr)
        return 1
    except RagkitError as e:
        print(f"错误：{e}", file=sys.stderr)
        return 1

    doc_ids = {c.doc_id for c in built.id_to_chunk.values()}
    print(f"已索引 {len(doc_ids)} 篇文档 → {len(built.store)} 块（索引目录：{cfg.index_dir}）")
    for f in built.failures:
        print(f"  跳过坏文件 {f.path}（{f.reason}）")
    return 0


def _cmd_ask(args, environ: Mapping[str, str] | None) -> int:
    """问答子命令：load_index → search → answer_question → 打印。"""
    from ragkit.config import load_config
    from ragkit.errors import RagkitError
    from ragkit.generation import answer_question
    from ragkit.index import load_index
    from ragkit.retrieval.pipeline import search

    try:
        cfg = load_config(args.config, environ)
    except (FileNotFoundError, RagkitError) as e:
        print(f"错误：{e}", file=sys.stderr)
        return 1

    try:
        built = load_index(cfg.index_dir)
    except FileNotFoundError:
        # chunks.jsonl 缺失（build 写到一半的半成品）
        print(
            f"错误：索引不完整（{cfg.index_dir}），请重新运行 ragkit build",
            file=sys.stderr,
        )
        return 1
    except (RagkitError, ValueError) as e:
        # 目录不存在 / manifest 损坏（StoreCorruptError ⊂ RagkitError）/ id 不一致
        print(f"错误：索引不存在或损坏（{e}），请先运行 ragkit build", file=sys.stderr)
        return 1

    result = search(
        args.query,
        bm25=built.bm25,
        store=built.store,
        id_to_chunk=built.id_to_chunk,
        dim=built.dim,
        retrieval=cfg.retrieval,
    )
    answer = answer_question(args.query, result, llm=cfg.llm)

    if answer.refused:
        print("未找到相关内容。")
        return 0

    print(answer.answer)
    print()
    for c in answer.citations:
        print(f"[{c.index}] {c.source}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
