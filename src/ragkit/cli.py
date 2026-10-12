import argparse
import sys

from ragkit import __version__


def main(argv: list[str] | None = None) -> int:
    """RAGKit 命令行入口。

    Args:
        argv: 要解析的参数列表；None 时读取真实命令行参数。

    Returns:
        int: 正常显示帮助或版本信息时返回 0。argparse 的参数错误和 --help
            退出行为由 argparse 自身处理。
    """
    parser = argparse.ArgumentParser(
        prog="ragkit",
        description="From-scratch Chinese technical-doc RAG system",
    )

    parser.add_argument(
        "--version",
        action="store_true",
        help="显示 RAGKit 的版本号",
    )

    args = parser.parse_args(argv)

    if args.version:
        print(f"ragkit {__version__}")
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
