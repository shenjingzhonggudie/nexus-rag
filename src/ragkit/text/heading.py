"""Markdown 标题清理：去掉 ``#`` 前缀、闭合 ``#``、锚点与 JSX 注释。

真实文档的标题会带各种"语法尾巴"，直接用会污染展示与标注：

- ``## 标题 ##``              闭合 #（部分 Markdown 风格）
- ``## 标题 {#anchor}``       VuePress / Docusaurus 的锚点
- ``## 标题 {/* comment */}`` React 文档的 JSX 注释
"""

import re

_CLOSING_HASH = re.compile(r"[ \t]+#+[ \t]*$")
_ANCHOR = re.compile(r"\s*\{#[^}]+\}\s*$")
_JSX_COMMENT = re.compile(r"\s*\{/\*.*?\*/\}\s*$")
# Hugo shortcode：{{% heading "whatsnext" %}} / {{< note >}}，会整行变成"标题"
_HUGO_SHORTCODE = re.compile(r"\{\{[%<].*?[%>]\}\}")


def clean_heading(line: str) -> str:
    """把一行 Markdown 标题清理成可读文本。

    Args:
        line: 原始标题行，可含 ``##`` 前缀、闭合 ``#``、``{#anchor}``、
            ``{/* JSX 注释 */}``。

    Returns:
        str: 清理后的标题；输入为空或只有 ``#`` 时返回空串。
    """
    text = line.lstrip("#").strip()
    text = _CLOSING_HASH.sub("", text).strip()
    text = _ANCHOR.sub("", text).strip()
    text = _JSX_COMMENT.sub("", text).strip()
    text = _HUGO_SHORTCODE.sub("", text).strip()
    return text
