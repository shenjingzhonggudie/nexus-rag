"""BM25 稀疏检索：__init__ 建统计，search 打分。"""

import math
from collections import Counter

from ragkit.schemas import Chunk, ScoredChunk
from ragkit.text import tokenize


class BM25Index:
    """按 BM25 公式对 query 与每个块算相关性分。

    建索引（__init__）统计 df / 词频 / 块长；查询（search）只用这些统计，
    不重新分词任何块。分数无上界、不归一化（阶段 7 用 RRF 融合的理由）。
    """

    def __init__(self, chunks: list[Chunk], *, k1: float = 1.5, b: float = 0.75):
        """对全部块分词并统计词频、块长和文档频率。

        Args:
            chunks: 待索引的文本块；检索结果的下标与此列表一一对应。
            k1: 词频饱和参数，越大则词频对分数的影响越大。
            b: 长度归一化强度，0 表示不考虑块长，1 表示完全按块长归一化。
        """
        self._k1 = k1          # 词频饱和参数
        self._b = b            # 长度归一化强度
        self._chunks = chunks  # 被索引的文本块，下标与下面各统计量对齐

        # 每块：词频 + token 数。tokenize 双通道、保留重复 → Counter 直接得词频。
        self._doc_freq: list[Counter] = []  # 每块的词 → 词频
        self._doc_len: list[int] = []       # 每块的 token 数
        for chunk in chunks:
            tokens = tokenize(chunk.text)
            self._doc_freq.append(Counter(tokens))
            self._doc_len.append(len(tokens))

        self._n = len(chunks)  # 块总数
        # 平均块长（token 数）；无块时为 0.0，避免除零
        self._avgdl = (sum(self._doc_len) / self._n) if self._n else 0.0

        # df：词 → 含该词的块数（Counter 的 key 已去重，每个块只加一次）。
        self._df: dict[str, int] = {}  # 文档频率，用于计算 idf
        for freq in self._doc_freq:
            for term in freq:
                self._df[term] = self._df.get(term, 0) + 1

    def _idf(self, term: str) -> float:
        """计算词的逆文档频率，越稀有的词权重越高。

        Args:
            term: 语料中出现过的词。

        Returns:
            float: idf 值；公式内加 1 保证结果恒为正，常见词也不会得到负权重。

        Raises:
            KeyError: term 未在语料中出现（不在 df 表中）时抛出。
        """
        df = self._df[term]
        return math.log(1.0 + (self._n - df + 0.5) / (df + 0.5))

    def search(self, query: str, *, top_k: int = 20) -> list[ScoredChunk]:
        """用 BM25 对 query 与每个块打分，返回得分最高的若干块。
        score(D, Q) = Σ_{t ∈ Q} IDF(t) · f(t,D)·(k1+1) / ( f(t,D) + k1·(1 − b + b·|D|/avgdl) )
        IDF(t) = ln( 1 + (N − df(t) + 0.5) / (df(t) + 0.5) )

        Args:
            query: 查询文本，内部会分词并规范化。
            top_k: 最多返回的块数。

        Returns:
            list[ScoredChunk]: 按分数从高到低排列，stage 为 "bm25"。
                只包含分数大于 0 的块；query 无有效词或所有词都未在语料中
                出现时返回空列表。
        """
        tokens = tokenize(query)          # tokenize 内部已 normalize
        if not tokens:
            # 空 query：与 dense 保持一致，返回 top_k 个分数全 0 的块（而非空列表）
            return [
                ScoredChunk(chunk=chunk, score=0.0, stage="bm25")
                for chunk in self._chunks[:top_k]
            ]

        # 只保留语料里出现过的词；df=0 的词不参与（否则 idf 会爆掉）。
        # set() 去重：query 里重复的词只计一次，不按出现次数加权。
        query_terms = [t for t in set(tokens) if t in self._df]
        if not query_terms:
            return []

        scored: list[tuple[float, Chunk]] = []
        for i, chunk in enumerate(self._chunks):
            score = 0.0
            freq = self._doc_freq[i]
            for term in query_terms:
                tf = freq.get(term, 0)
                if tf == 0:
                    continue
                # 长度归一化项；avgdl==0（全部块为空）时退化为纯 k1 惩罚，避免 0/0。
                len_ratio = self._doc_len[i] / self._avgdl if self._avgdl else 0.0
                norm = self._k1 * (1.0 - self._b + self._b * len_ratio)
                # BM25 单词得分：idf × 饱和后的词频（分母含长度归一化 norm）。
                score += self._idf(term) * (tf * (self._k1 + 1.0)) / (tf + norm)
            if score > 0.0:
                scored.append((score, chunk))

        # 按分数降序；只取前 top_k 个。
        scored.sort(key=lambda item: item[0], reverse=True)
        return [
            ScoredChunk(chunk=chunk, score=score, stage="bm25")
            for score, chunk in scored[:top_k]
        ]
