"""CLI 契约测试：build/ask 的输出与退出码、拒答=0、错误提示、环境变量隔离。"""

import logging

import jieba

from ragkit.cli import main


def _env(tmp_path):
    """环境注入：语料与索引目录都指向 tmp_path，与真实环境完全隔离（第 5 轮结论）。"""
    return {
        "RAG__DATA_DIR": str(tmp_path / "raw"),
        "RAG__INDEX_DIR": str(tmp_path / "idx"),
    }


def _make_corpus(tmp_path, empty=False):
    root = tmp_path / "raw"
    root.mkdir(exist_ok=True)
    if not empty:
        (root / "a.txt").write_text(
            "容器冷启动 优化指南\n\n冷启动是指容器首次启动时明显变慢的现象。",
            encoding="utf-8",
        )
    return root


def test_build_prints_stats(tmp_path, capsys):
    _make_corpus(tmp_path)

    rc = main(["build"], _env(tmp_path))

    out = capsys.readouterr().out
    assert rc == 0
    assert "已索引 1 篇文档" in out
    assert "1 块" in out
    assert (tmp_path / "idx" / "chunks.jsonl").exists()


def test_build_skips_bad_files(tmp_path, capsys):
    _make_corpus(tmp_path)
    (tmp_path / "raw" / "bad.md").write_bytes(b"\xff\xfe\x00\x01")

    rc = main(["build"], _env(tmp_path))

    out = capsys.readouterr().out
    assert rc == 0
    assert "跳过坏文件 bad.md" in out


def test_build_missing_root_returns_one(tmp_path, capsys):
    # raw 目录不存在（未创建语料）
    rc = main(["build"], _env(tmp_path))

    err = capsys.readouterr().err
    assert rc == 1
    assert "错误" in err


def test_build_missing_config_returns_one(tmp_path, capsys):
    rc = main(["build", "--config", str(tmp_path / "nope.yaml")], _env(tmp_path))

    assert rc == 1
    assert "错误" in capsys.readouterr().err


def test_ask_answers_with_citations(tmp_path, capsys):
    _make_corpus(tmp_path)
    env = _env(tmp_path)
    assert main(["build"], env) == 0

    rc = main(["ask", "容器冷启动"], env)

    out = capsys.readouterr().out
    assert rc == 0
    assert "[1] a.txt" in out          # 引用可溯源
    assert "冷启动" in out              # 回答含相关原文


def test_ask_refused_returns_zero(tmp_path, capsys):
    _make_corpus(tmp_path, empty=True)  # 空语料 → 空索引
    env = _env(tmp_path)
    main(["build"], env)

    rc = main(["ask", "任何问题"], env)

    out = capsys.readouterr().out
    assert rc == 0                       # 拒答是业务正常结果（第 16 轮决策 1）
    assert "未找到相关内容" in out


def test_ask_without_build_returns_one(tmp_path, capsys):
    _make_corpus(tmp_path)  # 语料在，但没有 build → idx 不存在

    rc = main(["ask", "容器冷启动"], _env(tmp_path))

    err = capsys.readouterr().err
    assert rc == 1
    assert "ragkit build" in err         # 提示先建库


def test_jieba_log_level_suppressed():
    # 债务 9 治理：分词层把 jieba 压到 WARNING，stderr 不再有首次加载的自述噪声
    import ragkit.text.tokenize  # noqa: F401  触发模块级 setLogLevel

    logger = getattr(jieba, "default_logger", None)
    assert logger is not None
    assert logger.level >= logging.WARNING
