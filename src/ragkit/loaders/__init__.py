"""文件加载：TXT / Markdown → Document。"""

from .directory import load_dir
from .files import load_file, strip_front_matter
from .report import LoadFailure, LoadReport

__all__ = ["load_dir", "load_file", "strip_front_matter", "LoadFailure", "LoadReport"]
