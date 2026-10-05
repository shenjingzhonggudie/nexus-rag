import argparse
import sys

from ragkit import __version__


def main(argv: list[str] | None = None) -> int:
    """RAGKit 命令行入口。

    不传入 argv 时，读取真实的命令行参数；
    传入列表时，解析列表中的参数。
    如果没有提供任何参数，则打印帮助信息并返回 0。
    使用 --version 时，打印当前版本并返回 0。
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
