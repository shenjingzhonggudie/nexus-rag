import re
import unicodedata


_INVISIBLE_RE = re.compile(
    r"[\u200b-\u200d\ufeff\x00-\x08\x0b-\x1f\x7f-\x9f]"
)


def normalize_text(text: str) -> str:
    """规范化文本的换行、不可见字符、兼容字符和空白。

    Args:
        text: 待处理的原始文本。

    Returns:
        str: 换行统一为 LF、零宽及控制字符移除、经 NFKC 归一后的文本；
            保留换行和制表符语义，并将连续三个及以上换行压缩为两个。
    """
    # 1. 统一换行
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # 2. 删除零宽字符和控制字符，保留 \n、\t
    text = _INVISIBLE_RE.sub("", text)

    # 3. 全角及兼容字符归一
    text = unicodedata.normalize("NFKC", text)

    # 4. 去掉每行行尾空白，将行内制表符替换为单个空格
    text = "\n".join(
        line.rstrip().replace("\t", " ")
        for line in text.split("\n")
    )

    # 5. 最多保留一个空行
    return re.sub(r"\n{3,}", "\n\n", text)