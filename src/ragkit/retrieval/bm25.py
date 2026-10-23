"""BM25 稀疏检索：__init__ 建统计，search 打分。"""

import math
import re
from collections import Counter

from ragkit.schemas import Chunk, ScoredChunk
from ragkit.text import tokenize, tokenize_terms

# 英文标识符：Kubernetes / JVM / v-model / Kafka / RSA 这类专有名词。
# 它们几乎不会被误分词，是判断"这个问题是不是在问语料之外的技术"的可靠信号。
_ENGLISH_TOKEN = re.compile(r"[A-Za-z][A-Za-z0-9_.+#-]*")

# 拒答判据专用的停用词：只收「纯疑问 / 指代 / 语气」词。
#
# 它们在任何中文技术文档里都高频，但**几乎不会是一个问题的答案核心名词**。
# 不过滤的后果（实测）：`我的电话号码是什么` 的实词是 {电话号码, 什么}，
# 其中 `什么` 的 idf 占总权重 31% → 覆盖率 0.311 远高于 0.05 的阈值，
# 于是「语料里根本没有的东西」也能通过拒答判定。`微生物是什么` 同理（也是 0.311）。
#
# **不收** `区别` / `方法` / `关系` / `原理` 这类词——它们在技术提问里可能正是
# 要找的东西（"两者的区别"），过滤掉会让分母失真。
#
# 只用于 :meth:`BM25Index.key_term_coverage`，**不影响 BM25 索引与检索排序**。
_STOPWORDS = frozenset(
    {
        "什么",
        "怎么",
        "怎样",
        "如何",
        "为何",
        "为什么",
        "哪些",
        "哪个",
        "是否",
        "能否",
        "可以",
        "需要",
        "应该",
        "时候",
        "请问",
        "告诉",
        "我们",
        "你们",
        "他们",
        "这个",
        "那个",
        "这些",
        "那些",
        "这样",
        "那样",
        "一个",
        "一下",
        "一些",
        "有点",
        "以及",
        "或者",
        "还是",
        "如果",
        "因为",
        "所以",
        "但是",
        "而且",
        "然后",
        "就是",
        "不是",
        "没有",
        "已经",
        "还有",
    }
)


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

        # chunk_id → 下标：拒答判据按命中块回捞原始词集合，避免重新分词
        self._id_to_index: dict[str, int] = {
            chunk.chunk_id: i for i, chunk in enumerate(chunks)
        }

        # 语料中所有词的最大 idf：给"语料外的查询词"一个合理权重（见 key_term_coverage）
        self._max_idf = max((self._idf(t) for t in self._df), default=1.0)

        # 小写词表：英文标识符大小写不一致（Kubernetes / kubernetes）时也能判断是否登陆
        self._lower_terms: set[str] = {term.lower() for term in self._df}

        # 原文拼接：判断"某个英文标识符是否在语料里"时比分词词表可靠。
        # AUTO_RANDOM 这类代码标识符在原文里是完整的，但 jieba 可能把它切成
        # AUTO / RANDOM，只查词表会误判成"语料外的技术"从而误拒。
        self._raw_text: str = "\n".join(chunk.text for chunk in chunks)

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

    def unknown_entities(self, query: str) -> list[str]:
        """查询里**语料中完全未出现**的英文标识符（如 Kafka / ZooKeeper / JVM）。

        这是比"实词覆盖率"更强的拒答信号：覆盖率会被口语化表述稀释（真实用户
        问"部署到生产要留意什么"，文档写"生产部署"），但一个语料里根本没出现过
        的技术名词（Kafka、ZooKeeper）几乎必然意味着"语料没有这个问题的答案"。

        Args:
            query: 查询文本。

        Returns:
            list[str]: 未登录的英文标识符（去重、保持原大小写）；没有则为空列表。
        """
        # 只看首字母大写的专有名词：v-model / v-if / v-show 这类框架指令小写开头，
        # 且分词形式不稳定（v / model / v-model），拿它们当"外来实体"会误拒正常问题。
        # 用原文而不是分词词表判断：AUTO_RANDOM 在原文里完整存在，但会被 jieba 切开。
        return [
            token
            for token in set(_ENGLISH_TOKEN.findall(query))
            if token[0].isupper()
            and token not in self._raw_text
            and token.lower() not in self._lower_terms
        ]

    def key_term_coverage(
        self, query: str, hits: list[ScoredChunk], *, top_n: int = 3
    ) -> float | None:
        """查询实词的 idf 加权覆盖率（0~1），用于拒答判断。

        实词 = 长度 ≥ 2 的**词语**（``tokenize_terms``，不含 bigram），再剔除
        :data:`_STOPWORDS` 里的疑问/指代词。覆盖率按 **idf 加权**，而不是
        简单计数——否则"Kubernetes 的 Service 怎么配置"会因为"配置""怎么"
        这类高频词在语料里随处可见而拿到很高的覆盖率，掩盖"Kubernetes /
        Service 根本没在语料出现"这一关键事实。

        停用词过滤是后补的：最初只按长度过滤单字，结果 ``什么`` 这类双字虚词
        漏了进来——实测 `我的电话号码是什么` 与 `微生物是什么` 的覆盖率都是
        0.311（全部来自 ``什么`` 的 idf），双双高于阈值、双双没被拒答。

        权重规则：
        - 语料内的词 → 它的 idf（越罕见权重越高）；
        - **语料外的词 → 全语料最大 idf**（把它当作"很可能重要却完全没被覆盖"
          的关键词），这是识别"语料里没有答案"的核心信号。

        为什么不用融合分做阈值：RRF / 加权融合的分数是排名分
        ``Σ w/(k+rank)``，取值集中在 0.012~0.017，只反映名次、不反映匹配质量，
        无法区分"第 1 名但毫不相关"和"第 1 名且高度相关"。

        Args:
            query: 查询文本。
            hits: 该查询的 BM25 检索结果（已按分数降序）。
            top_n: 参与覆盖统计的结果数；取前几个而非只取第一个，是为了避免
                单个块的偶然措辞导致误拒。

        Returns:
            float | None: 覆盖率 0~1；查询没有长度 ≥ 2 的实词时返回 None
                （无判定信号，调用方不应据此拒答）。
        """
        terms = {
            t for t in tokenize_terms(query) if len(t) >= 2 and t not in _STOPWORDS
        }
        if not terms:
            return None

        # 命中块用建索引时缓存好的词集合，不重新分词（避免每次查询的额外开销）
        covered: set[str] = set()
        for hit in hits[:top_n]:
            index = self._id_to_index.get(hit.chunk.chunk_id)
            if index is not None:
                covered.update(self._doc_freq[index])

        total_weight = 0.0
        matched_weight = 0.0
        for term in terms:
            weight = self._idf(term) if term in self._df else self._max_idf
            total_weight += weight
            if term in covered:
                matched_weight += weight

        return matched_weight / total_weight if total_weight > 0 else None
