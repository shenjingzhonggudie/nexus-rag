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

    p_serve = sub.add_parser("serve", help="启动 HTTP API（POST /ask、GET /healthz）")
    p_serve.add_argument("--host", default="127.0.0.1", help="监听地址（默认 127.0.0.1）")
    p_serve.add_argument("--port", type=int, default=8000, help="监听端口（默认 8000）")
    p_serve.add_argument("--config", default=None, help="YAML 配置路径（省略时用默认值 + 环境变量）")

    p_eval = sub.add_parser("eval", help="跑评测集并输出检索质量报告")
    p_eval.add_argument("--config", default=None, help="YAML 配置路径（省略时用默认值 + 环境变量）")
    p_eval.add_argument("--qrels", default="data/eval/qrels.json", help="评测集路径")
    p_eval.add_argument("--out", default="reports/eval.json", help="报告输出路径")

    args = parser.parse_args(argv)

    if args.version:
        print(f"ragkit {__version__}")
        return 0
    if args.command is None:
        parser.print_help()
        return 0
    if args.command == "build":
        return _cmd_build(args, environ)
    if args.command == "serve":
        return _cmd_serve(args, environ)
    if args.command == "eval":
        return _cmd_eval(args, environ)
    return _cmd_ask(args, environ)


def _cmd_build(args, environ: Mapping[str, str] | None) -> int:
    """建库子命令：load_config → build → 打印统计。

    Args:
        args: argparse 解析结果，使用 config（YAML 路径）和 root（语料目录）两个字段。
        environ: 环境变量映射；None 时读取当前进程环境，传入是为了测试隔离。

    Returns:
        int: 退出码。0 = 建库成功（坏文件只提示，不影响成功）；1 = 运行错误
            （配置非法、语料目录不存在）。
    """
    from ragkit.config import load_config
    from ragkit.errors import RagkitError
    from ragkit.index import build as build_index

    try:
        cfg = load_config(args.config, environ)
        # 决策 2：默认 cfg.data_dir（配置给默认、环境变量可覆盖），--root 显式最高
        root = Path(args.root) if args.root else cfg.data_dir
        built = build_index(root, cfg)
    except FileNotFoundError as e:
        # 语料目录或配置文件不存在
        print(f"错误：{e}", file=sys.stderr)
        return 1
    except RagkitError as e:
        # 配置非法等领域内的已知错误
        print(f"错误：{e}", file=sys.stderr)
        return 1

    # 文档数由块反推：同一文档的多个块只算一篇
    doc_ids = {c.doc_id for c in built.id_to_chunk.values()}
    print(f"已索引 {len(doc_ids)} 篇文档 → {len(built.store)} 块（索引目录：{cfg.index_dir}）")
    # 坏文件不影响建库成功，只列出来提示用户
    for f in built.failures:
        print(f"  跳过坏文件 {f.path}（{f.reason}）")
    return 0


def _cmd_ask(args, environ: Mapping[str, str] | None) -> int:
    """问答子命令：load_index → search → answer_question → 打印。

    Args:
        args: argparse 解析结果，使用 query（问题文本）和 config（YAML 路径）两个字段。
        environ: 环境变量映射；None 时读取当前进程环境，传入是为了测试隔离。

    Returns:
        int: 退出码。0 = 成功（含拒答——拒答是业务正常结果）；1 = 运行错误
            （配置非法、索引不存在、不完整或损坏）。
    """
    from ragkit.config import load_config
    from ragkit.errors import RagkitError
    from ragkit.generation import answer_question
    from ragkit.index import load_index
    from ragkit.retrieval.pipeline import search

    # 第一步：读配置，决定索引目录和检索、LLM 参数
    try:
        cfg = load_config(args.config, environ)
    except (FileNotFoundError, RagkitError) as e:
        print(f"错误：{e}", file=sys.stderr)
        return 1

    # 第二步：从磁盘加载 build 产出的索引，不重新处理文档
    try:
        built = load_index(
            cfg.index_dir,
            provider=cfg.embedding.provider,
            model_name=cfg.embedding.model_name,
        )
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

    # 第三步：检索，得到按相关度排好序的块
    result = search(
        args.query,
        bm25=built.bm25,
        store=built.store,
        id_to_chunk=built.id_to_chunk,
        dim=built.dim,
        retrieval=cfg.retrieval,
    )
    # 第四步：基于检索结果生成答案；结果为空或实词覆盖率低于阈值时拒答
    answer = answer_question(
        args.query, result, llm=cfg.llm, refuse_threshold=cfg.retrieval.refuse_threshold
    )

    # 拒答是业务上的正常结果，退出码仍为 0
    if answer.refused:
        print("未找到相关内容。")
        return 0

    print(answer.answer)
    print()
    # 引用序号从 1 开始，与答案对应
    for c in answer.citations:
        print(f"[{c.index}] {c.source}")
    return 0


def _cmd_serve(args, environ: Mapping[str, str] | None) -> int:
    """serve 子命令：启动 HTTP API；索引常驻内存，只付一次冷启动，Ctrl+C 退出。"""
    import logging

    from ragkit.api import create_server
    from ragkit.config import load_config
    from ragkit.errors import RagkitError
    from ragkit.index import load_index

    try:
        cfg = load_config(args.config, environ)
    except (FileNotFoundError, RagkitError) as e:
        print(f"错误：{e}", file=sys.stderr)
        return 1
    try:
        built = load_index(
            cfg.index_dir,
            provider=cfg.embedding.provider,
            model_name=cfg.embedding.model_name,
        )
    except FileNotFoundError:
        print(f"错误：索引不完整（{cfg.index_dir}），请重新运行 ragkit build", file=sys.stderr)
        return 1
    except (RagkitError, ValueError) as e:
        print(f"错误：索引不存在或损坏（{e}），请先运行 ragkit build", file=sys.stderr)
        return 1

    # 日志惯例：库只 getLogger、应用侧 basicConfig（格式归调用方定，库不越界）
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s | %(name)s | %(message)s"
    )

    server = create_server(args.host, args.port, built, cfg)
    print(
        f"ragkit serve 监听 http://{args.host}:{server.server_address[1]}"
        "（POST /ask、GET /healthz；Ctrl+C 停止）"
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止。")
    finally:
        server.server_close()
    return 0


def _cmd_eval(args, environ: Mapping[str, str] | None) -> int:
    """eval 子命令：跑评测集，打印摘要并把完整报告落盘。"""
    import json
    from pathlib import Path

    from ragkit.config import load_config
    from ragkit.errors import RagkitError
    from ragkit.evaluation import evaluate, load_qrels
    from ragkit.index import load_index

    try:
        cfg = load_config(args.config, environ)
    except (FileNotFoundError, RagkitError) as e:
        print(f"错误：{e}", file=sys.stderr)
        return 1
    try:
        built = load_index(
            cfg.index_dir,
            provider=cfg.embedding.provider,
            model_name=cfg.embedding.model_name,
        )
    except FileNotFoundError:
        print(f"错误：索引不完整（{cfg.index_dir}），请重新运行 ragkit build", file=sys.stderr)
        return 1
    except (RagkitError, ValueError) as e:
        print(f"错误：索引不存在或损坏（{e}），请先运行 ragkit build", file=sys.stderr)
        return 1
    try:
        qrels = load_qrels(Path(args.qrels))
    except (FileNotFoundError, ValueError) as e:
        print(f"错误：评测集加载失败：{e}", file=sys.stderr)
        return 1

    report = evaluate(built, cfg, qrels)

    # 打印摘要：有多个来源时**只报分组**，不报合计。
    # 合计会被两组的题目比例左右（external 占比一高，整体就掉），
    # 它不是系统能力，放在报告里容易被误读成"一个数字"。
    print(f"评测集 {len(report.per_query)} 条")
    if len(report.by_source) > 1:
        labels = {"internal": "内部组（读正文出题）", "external": "外部组（只看标题）"}
        print("按来源（两组必须分开看，合计会随两组比例变化）：")
        for name, stats in report.by_source.items():
            print(f"  {labels.get(name, name)}  n={stats.n}")
            print(
                f"    recall@1={stats.recall_at[1]:.3f}  "
                f"@3={stats.recall_at[3]:.3f}  "
                f"@5={stats.recall_at[5]:.3f}  MRR={stats.mrr:.3f}"
            )
    else:
        for k, v in report.recall_at.items():
            print(f"recall@{k} = {v:.3f}")
        print(f"MRR      = {report.mrr:.3f}")
    if report.n_no_answer:
        print(
            f"拒答    准确率 {report.refusal_accuracy:.3f}"
            f"（{report.n_no_answer} 条无答案）"
            f" | 误拒率 {report.false_refusal_rate:.3f}"
        )
    print(
        f"耗时  冷启动 {report.latency.cold_ms:.0f}ms | "
        f"热启动 P50 {report.latency.warm_p50_ms:.1f}ms "
        f"P95 {report.latency.warm_p95_ms:.1f}ms"
    )

    # 落盘完整报告（含逐条明细，消融实验直接读）
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(report.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"报告已写入 {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
