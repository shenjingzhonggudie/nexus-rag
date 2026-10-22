"""文件加载：TXT / Markdown → Document。"""

from .directory import load_dir
from .files import (
    load_file,
    strip_front_matter,
    strip_html_comments,
    strip_mdx_lines,
)
from .report import LoadFailure, LoadReport

__all__ = [
    "load_dir",
    "load_file",
    "strip_front_matter",
    "strip_html_comments",
    "strip_mdx_lines",
    "LoadFailure",
    "LoadReport",
]
