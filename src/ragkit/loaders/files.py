"""单文件加载：读取 TXT 或 Markdown 文件并构造 Document。"""

import hashlib
import re
from pathlib import Path
from ragkit.errors import LoadError
from ragkit.schemas import Document
from ragkit.text import clean_heading

# 文件开头的 YAML front matter（Hugo / Jekyll / Docusaurus 等静态站点通用）：
# 形如 ---\ntitle: xxx\nweight: 10\n---\n。只在文件最开头匹配，正文中间的分隔线不受影响。
_FRONT_MATTER = re.compile(
    r"\A---[ \t]*\r?\n(?P<body>.*?)\r?\n---[ \t]*(?:\r?\n|\Z)", re.DOTALL
)
_FRONT_MATTER_TITLE = re.compile(r"^title:\s*(?P<title>.+?)\s*$", re.MULTILINE)


_HTML_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)

# 独占一行的 MDX 组件标签，如 `</Sandpack>`、`<Intro>`、`<SimpleTab  label="x">`。
# 只匹配**整行只有一个标签**的情况：`<Transition> 是内置组件` 这种出现在句子里的
# 标签必须保留——Vue 文档正是在讨论这些组件，删了就丢正文。
_MDX_TAG_LINE = re.compile(
    r"^[ \t]*</?[A-Z][A-Za-z0-9]*(?:[ \t][^>\n]*)?>[ \t]*$", re.MULTILINE
)


def strip_mdx_lines(text: str) -> str:
    """删除整行只有 MDX 组件标签的行。

    React 文档用 MDX 写，正文里散布 ``<Sandpack>`` / ``<Pitfall>`` / ``<LearnMore>``
    这类布局组件的开闭标签；TiDB 站点有 ``<SimpleTab>`` / ``<DevToolCard>``。
    它们单独成行时是纯噪音，切成块后就是 ``</Sandpack>\\n\\n`` 这种 13 字符的碎块。

    **只删独占一行的标签**：``<Transition> 是内置组件`` 这种句子里的标签保留，
    那是正文在讨论组件本身，删掉会丢失内容。

    Args:
        text: 待处理文本。

    Returns:
        str: 独占行的 MDX 标签已移除的文本（留下的空行由 normalize_text 压缩）。
    """
    return _MDX_TAG_LINE.sub("", text)


def strip_html_comments(text: str) -> str:
    """剥离 HTML 注释。

    Kubernetes 中文站点把**英文原文整段包在注释里**（中文译文才是正文），
    这些注释对中文检索是纯噪音：注释占比最高的文档达 72%，块文本里大量
    出现 ``<!-- overview -->``、``title: Concepts`` 这类元数据。

    **只在 ``<!--`` 与 ``-->`` 数量一致时执行**：配对不齐说明代码块里有孤立的
    标记（实测 2 篇如此），此时剥离有吞正文的风险，原样返回。

    Args:
        text: 待处理文本。

    Returns:
        str: 注释已移除的文本；配对不齐时原样返回。
    """
    if text.count("<!--") != text.count("-->"):
        return text
    return _HTML_COMMENT.sub("", text)


def strip_front_matter(text: str) -> str:
    """剥离文件开头的 YAML front matter。

    真实技术文档普遍带这一段元数据；不剥离的话 ``weight: 40``、``main_menu: true``
    会被当成正文参与分块与检索，既污染内容也干扰字符偏移。

    Args:
        text: 原文。

    Returns:
        str: 去掉 front matter 后的文本；没有 front matter 时原样返回。
    """
    return _FRONT_MATTER.sub("", text, count=1)


def _front_matter_title(text: str) -> str | None:
    """从 front matter 的 ``title:`` 字段取标题；没有则返回 None。

    优先级高于 ``# 一级标题``：压平后的文件名（``content__zh-cn__...__index``）
    不可读，而 front matter 里的 title 是作者写的可读标题。
    """
    matched = _FRONT_MATTER.match(text)
    if matched is None:
        return None
    title = _FRONT_MATTER_TITLE.search(matched.group("body"))
    if title is None:
        return None
    value = title.group("title").strip().strip("'\"")
    return value or None


def load_file(path: Path, *, source: str | None = None) -> Document:
    """读取单个文件并构造 Document。

    Args:
        path: 待读取的文件路径。
        source: 结果中的来源标识；省略时取 path.name。批量加载时由调用方传入
            相对根目录的 POSIX 路径，使 source 与 metadata["path"] 同坐标系。

    Returns:
        Document: title 取自 Markdown 的首个标题行，找不到时回退为不含扩展名的
            文件名；metadata 固定包含 path、size、ext、encoding、content_hash
            五个键，其中 path 与 source 同坐标系、content_hash 取 SHA-256 十六进制
            摘要的前 16 位（64 bit）。

    Raises:
        LoadError: 读取、解码或构造 Document 失败。

    编码策略：先按 utf-8-sig 解码（顺带去掉 UTF-8 BOM），失败回退 gbk，两者都
    失败才抛 LoadError。metadata["encoding"] 记录的是**编码家族**（"utf-8" /
    "gbk"），而不是具体 codec 名（utf-8-sig）——契约要稳定、实现可变：将来换成
    别的读法（手动判 BOM、errors="replace" 兜底）时这个值不应跟着变；而"文件有
    没有 BOM"已经由 size 与 content_hash（两者都基于原始字节）体现，不需要
    encoding 重复承担。
    """
    # 来源标识：调用方未指定时使用文件名；批量加载时可传入相对目录的路径。
    if source is None:
        source = path.name

    try:
        # 一次读取原始字节，供解码、统计文件大小和计算内容哈希共同使用。
        raw = path.read_bytes()
        try:
            # 优先按 UTF-8 解码；utf-8-sig 会自动去掉文件开头的 UTF-8 BOM。
            content = raw.decode("utf-8-sig")
            # 记录"编码家族"而非 codec 名（utf-8 而非 utf-8-sig），理由见 docstring。
            encoding = "utf-8"
        except UnicodeDecodeError:
            # UTF-8 解码失败时回退到 GBK；仍失败则交给外层包装为 LoadError。
            content = raw.decode("gbk")
            encoding = "gbk"

        # front matter 的 title 优先于文件名；随后正文里也剥掉这段元数据
        front_title = _front_matter_title(content)
        content = strip_front_matter(content)
        # k8s 中文文档用注释包住英文原文：剥离后只留中文正文
        content = strip_html_comments(content)
        # React/TiDB 用 MDX 写正文：独占一行的 <Sandpack> 之类是纯噪音
        content = strip_mdx_lines(content)

        # 默认标题使用不含最后一个扩展名的文件名，例如 a.md 的标题为 a。
        title = front_title or path.stem
        # 只有在 front matter 没给 title 时，才回退到找 # 一级标题
        if path.suffix.lower() in {".md", ".markdown"} and front_title is None:
            # Markdown 按行查找首个匹配的 # 标题：允许 0～3 个前导空格、
            # 1～6 个 #，且 # 后必须有空格或制表符；未找到时保留默认标题。
            for line in content.splitlines():
                heading = re.match(r"^ {0,3}#{1,6}[ \t]+(.+?)\s*$", line)
                if heading:
                    # clean_heading 统一处理闭合 #、{#anchor}、{/* JSX */} 三种尾巴
                    title = clean_heading(line.strip()) or title
                    break
        # 将正文、标题和元数据组装为 Document；标题存放在独立的 title 字段。
        # 临时规则：doc_id 取 source，第 3 阶段再重新决定稳定 ID。
        return Document(
            doc_id=source,
            source=source,
            text=content,
            title=title,
            # 元数据固定包含以下五个键，记录文件属性和内容指纹。
            metadata={
                # 与 source 同坐标系：批量加载时是相对 root 的 POSIX 路径。
                # 不能写 str(path)，否则机器相关的绝对路径会泄漏进索引与 manifest。
                "path": source,
                "size": len(raw),  # 原始字节数（包含 BOM），不是正文字符数。
                "ext": path.suffix.lower(),  # 小写扩展名，包含前导点，例如 .md。
                "encoding": encoding,  # 编码家族（utf-8 / gbk），见 docstring。
                # 对原始字节计算 SHA-256 并取前 16 位十六进制（64 bit）：
                # 用途是在同一批文件里判断"内容变没变"，10^2~10^4 量级下碰撞可忽略。
                "content_hash": hashlib.sha256(raw).hexdigest()[:16],
            },
        )
    except (OSError, UnicodeDecodeError) as e:
        # 只包装"环境问题"(OSError) 与"数据问题"(UnicodeDecodeError)；TypeError、
        # AttributeError 这类自身缺陷必须直接抛出，否则会被伪装成坏文件静默跳过。
        # from e 保留异常因果链，方便定位最初的失败原因。
        raise LoadError(
            # 此处保留调用方给的原始路径（便于人类定位）；
            # 进入 LoadFailure 时由 load_dir 换成 source 坐标系。
            path=str(path),
            reason=str(e),
            error_type=type(e).__name__,
        ) from e
