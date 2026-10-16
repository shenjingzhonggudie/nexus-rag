"""临时验证：jieba.setLogLevel(WARNING) 能否抑制 "Building prefix dict" 的 stderr 噪声。"""

import logging
import subprocess
import sys

# 子进程里设 log level 后触发 jieba 分词，看 stderr 是否干净
code = """
import logging, jieba
jieba.setLogLevel(logging.WARNING)
print(list(jieba.cut("容器冷启动")))
"""

r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
print("带 setLogLevel 的 stderr:")
print(repr(r.stderr))
print("干净:", "Building prefix dict" not in r.stderr)

# 对照组：不设 log level
code2 = """
import jieba
print(list(jieba.cut("容器冷启动")))
"""
r2 = subprocess.run([sys.executable, "-c", code2], capture_output=True, text=True)
print("不设的 stderr:")
print(repr(r2.stderr))
print("有噪声:", "Building prefix dict" in r2.stderr)
