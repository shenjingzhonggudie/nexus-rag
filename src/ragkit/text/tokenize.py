"""文本分词：提取词语和相邻汉字双字组合，保留重复结果。"""

import logging

import jieba

from ragkit.text.normalize import normalize_text

# 债务表 9 的噪声治理（第 16 轮决策 3）：jieba 首次加载会向 stderr 打三行自述
# （Building prefix dict / Loading model / Prefix dict built），污染 CLI / API 输出。
# 在源头层（所有入口都经过的分词层）压到 WARNING，一次治理所有入口。
# 实测（2026-10-16）：setLogLevel 后子进程 stderr 完全干净；耗时不变，仍约 1.8s。
jieba.setLogLevel(logging.WARNING)


# 用 Unicode 码点区间识别中日韩统一表意文字，覆盖基本区及下列扩展区。
# 这里不包含中文标点、假名或韩文音节，也不等同于所有 Unicode 汉字区块。
_CJK_RANGES = (
    (0x3400, 0x4DBF),    # Extension A
    (0x4E00, 0x9FFF),    # Unified ideographs
    (0x20000, 0x2A6DF),  # Extension B
    (0x2A700, 0x2B73F),  # Extension C
    (0x2B740, 0x2B81F),  # Extension D
    (0x2B820, 0x2CEAF),  # Extension E
    (0x2CEB0, 0x2EBEF),  # Extension F
    (0x2EBF0, 0x2EE5F),  # Extension I
    (0x30000, 0x3134F),  # Extension G
    (0x31350, 0x323AF),  # Extension H
)


def _is_cjk(ch: str) -> bool:
    """判断输入是否为已列 Unicode 范围中的单个中日韩统一表意汉字。

    Args:
        ch: 待检查的字符串。

    Returns:
        bool: ch 恰有一个字符且其码点落在 _CJK_RANGES 中时为 True。
    """
    # 先检查长度，避免对空字符串或多字符字符串调用 ord()。
    # ord() 获取字符码点；any() 在任一区间匹配时返回 True。
    return len(ch) == 1 and any(
        start <= ord(ch) <= end for start, end in _CJK_RANGES
    )


def _has_token_content(token: str) -> bool:
    """判断词元是否含有至少一个可索引字符。

    Args:
        token: 待检查的分词结果。

    Returns:
        bool: 含汉字、ASCII 英文字母或 Unicode 数字时为 True。
    """
    # 只要含有一个有效字符就保留整个词元；纯空白、纯标点会被过滤。
    # isdigit() 可识别部分非 ASCII 数字，不限于 0 到 9。
    return any(
        _is_cjk(ch) or "a" <= ch <= "z" or "A" <= ch <= "Z" or ch.isdigit()
        for ch in token
    )


def tokenize_terms(text: str) -> list[str]:
    """先规范化文本，再使用 jieba 精确模式提取词语。

    Args:
        text (str): 待分词的原始文本。

    Returns:
        list[str]: 含汉字、ASCII 英文字母或数字的词元，按分词顺序排列。
            保留单字词、数字词和重复词；空文本返回空列表。
    """
    normalized_text = normalize_text(text)
    # cut_all=False 表示精确模式；逐个检查分词结果，过滤无有效内容的词元。
    return [
        term
        for term in jieba.cut(normalized_text, cut_all=False)
        if _has_token_content(term)
    ]


def tokenize_bigrams(text: str) -> list[str]:
    """先规范化文本，再提取连续汉字中的相邻双字组合（bigram）。

    Args:
        text (str): 待处理的原始文本。

    Returns:
        list[str]: 按出现顺序排列的相邻汉字对，不跨越非汉字字符。
            例如“中文分词”得到 ["中文", "文分", "分词"]；
            “中 文”不会组成“中文”。空文本或单个汉字返回空列表。
    """
    normalized_text = normalize_text(text)
    # 将文本与向后错开一位的切片配对，依次得到第 1/2、2/3 等相邻字符。
    # 只有左右两个字符都是汉字时才拼接；组合可以重叠，重复项也会保留。
    return [
        left + right
        for left, right in zip(normalized_text, normalized_text[1:])
        if _is_cjk(left) and _is_cjk(right)
    ]


def tokenize(text: str) -> list[str]:
    """规范化文本，依次合并词语分词结果和相邻汉字双字组合。

    输出先放全部词语，再放全部双字组合，因此不代表它们在原文中的位置。
    第 9 阶段的句子级抽取会独立重新分句，不依赖这里的输出顺序。

    Args:
        text (str): 待分词的原始文本。

    Returns:
        list[str]: 词语列表与双字组合列表的拼接结果，保留重复项。
            空文本返回空列表。
    """
    normalized_text = normalize_text(text)
    # 两个子函数也会规范化输入，以便单独调用；这里沿用现有处理流程。
    # 列表相加只拼接，不去重，同一个词可能同时出现在两部分结果中。
    return tokenize_terms(normalized_text) + tokenize_bigrams(normalized_text)
