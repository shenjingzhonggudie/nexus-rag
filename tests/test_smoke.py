import re

import pytest

import ragkit
from ragkit.cli import main


def test_version():
    # 文件顶部的 import ragkit 若失败，pytest 会在收集测试时报告错误。
    # 版本号必须是字符串，避免误写成 0.01 这样的浮点数。
    assert isinstance(ragkit.__version__, str)
    # fullmatch 要求整个字符串符合“数字.数字.数字”格式。
    # 不绑定具体版本号，因此正常升级版本时无需修改测试。
    assert re.fullmatch(r"\d+\.\d+\.\d+", ragkit.__version__) is not None


def test_cli_version(capsys):
    # 直接传入参数列表，验证 --version 分支正常返回 0。
    assert main(["--version"]) == 0
    # capsys 是 pytest 提供的输出捕获夹具；.out 取得标准输出。
    # 输出应包含当前版本号，但不要求固定的输出前缀或排版。
    assert ragkit.__version__ in capsys.readouterr().out


def test_cli_no_args_and_help():
    # 空列表表示无命令行参数，不会读取运行 pytest 时的参数。
    # 当前约定是打印帮助信息并正常返回 0。
    assert main([]) == 0
    # argparse 处理 --help 时会打印帮助并抛出 SystemExit，而非返回整数。
    # pytest.raises 捕获该异常，避免它中断测试，并保留异常供后续检查。
    with pytest.raises(SystemExit) as exc_info:
        main(["--help"])
    # 退出码 0 表示正常退出；通过 .value 访问捕获到的异常实例。
    assert exc_info.value.code == 0
