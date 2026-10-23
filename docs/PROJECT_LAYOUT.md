# 模块与数据契约

本文说明当前源码的职责、接口和边界。运行方法与实测结果见 [README](../README.md)，开发约定见 [AGENTS](../AGENTS.md)，标注格式见 [data/README](../data/README.md)。

## 数据流与模块职责

```text
建库：load_dir → Document → chunk_document → Chunk → embed_text
       → 向量库四文件 + chunks.jsonl → BuiltIndex

查询：load_index → BuiltIndex → search（BM25 / dense → 排名融合）
       → RetrievalResult → answer_question → Answer → CLI 文本 / HTTP JSON

评测：load_qrels + BuiltIndex → search → 区间命中与拒答统计 → EvalReport
```

| 模块 | 职责与主要接口 |
|---|---|
| `schemas.py` | `Document`、`Chunk`、`ScoredChunk`、`Citation`、检索轨迹和 `Answer`；支持字典互转 |
| `config.py` | 配置校验、YAML 与环境变量合并；`load_config(path=None, environ=None) -> AppConfig` |
| `text/` | 文本规范化、jieba 分词、连续汉字 bigram、标题清理 |
| `loaders/` | `load_file(path, *, source=None) -> Document`；`load_dir(root, *, suffixes=...) -> LoadReport` |
| `chunking/` | `chunk_document(document, *, strategy="fixed", chunk_size=300, overlap=50) -> list[Chunk]` |
| `embeddings/` | `configure(*, provider="hashing", model_name="")`；`embed_text(text, *, dim) -> list[float]` |
| `stores/` | `VectorStore`；`write(...)` 与 `load(directory)` 读写向量文件 |
| `index/` | `build(root, cfg) -> BuiltIndex`；`load_index(index_dir, *, provider="hashing", model_name="") -> BuiltIndex` |
| `retrieval/` | BM25、向量点积、等权 RRF 和加权排名融合；`search(...) -> RetrievalResult` |
| `generation/` | `answer_question(question, result, *, llm, refuse_threshold=0.0) -> Answer` |
| `api/`、`cli.py` | 参数/请求解析、调用领域函数、输出转换；HTTP 服务附带静态检索页面 |
| `evaluation/` | 标注加载、检索指标、拒答统计及六组消融 |

`BuiltIndex` 包含 BM25 索引、向量库、`id_to_chunk`、向量维度与加载失败记录。领域模块返回结构化对象；CLI 和 HTTP 层负责展示。配置、文本与数据结构由多个模块共用。

## 配置

`load_config` 的覆盖顺序为：环境变量 > 显式指定的 YAML > Pydantic 模型默认值。不传 YAML 路径时不会自动读取 `configs/default.yaml`。相对路径以进程工作目录为基准。

- 环境变量使用 `RAG__DATA_DIR` 或 `RAG__RETRIEVAL__TOP_K` 这类格式，支持顶层和一层嵌套字段。合法格式中的未知字段会报 `ConfigError`；更深层、空段等不支持的命名被忽略。
- CLI 仅为已暴露的参数提供额外覆盖，例如 `build --root`；并非每个配置项都有命令行开关。
- 检索默认值为 top_k=20、final_k=5、α=0.7，两路召回及加权融合开启，拒答阈值=0.05。要求 `0 < final_k <= top_k`。
- 应用配置默认分块为 heading；`chunk_document` 函数直接调用的默认策略为 fixed。`overlap < chunk_size` 由配置模型校验。
- embedding 默认 hashing、512 维；LLM 默认 none。`snapshot()` 对非空 API key 掩码，其他字段按配置输出。

## 文本、来源与坐标

`normalize_text(text)` 固定按以下顺序处理：

1. CRLF / CR 转为 LF。
2. 删除 U+200B～U+200D、U+FEFF 和 C0/C1 控制字符，保留换行与 tab。
3. 做 NFKC 规范化。
4. 对每行执行 `rstrip()`，再将 tab 替换成一个空格。
5. 将三个及以上连续换行压缩成两个。不对全文执行 `strip()`。

三个分词入口都会调用规范化。`tokenize_terms` 使用 `jieba.cut(..., cut_all=False)`，保留含已列 CJK 范围、ASCII 字母或数字的词元，过滤纯空白/标点；单字和重复项保留。`tokenize_bigrams` 只在连续的已列 CJK 字符之间生成相邻双字组合，不跨空格、标点或英文。`tokenize` 输出全部 terms 后再接全部 bigrams，不代表原文位置顺序。

`load_dir` 递归加载 `.txt/.md/.markdown`，扩展名不区分大小写，跳过相对路径中以点开头的目录和文件，并按相对 POSIX 路径排序。该路径同时作为 `doc_id` 和 `source`；单独调用 `load_file` 而未传 source 时使用文件名。

文件先按 utf-8-sig 解码，失败后回退 GBK；读取/解码错误包装成 `LoadError`，批量加载时记入 `failures`。加载器会剥离开头的 front matter、数量配对的 HTML 注释和独占行的 MDX 标签。标题优先取 front matter 的 title，再取 Markdown 首个匹配标题，最后回退到文件 stem。

加载元数据包含 path、原始字节数 size、ext、encoding 和原始字节 SHA-256 前16位 content_hash。**分块与标注的坐标基准是 `normalize_text(load_file(path).text)`，不能直接用原始文件文本计算偏移。** 上游正文或加载/规范化规则变动后，需要重新核对标注区间。

## 分块

- fixed 按有效长度推进窗口：U+4E00～U+9FFF 字符计 1，其他非空白字符计 1/3，空白不计。`chunk_size` 使用该单位，`overlap` 使用原始字符数，两者单位不同。
- fixed 优先在窗口内最后一个双换行处切分；没有时找单换行，再找 `。！？；`。边界不足目标有效长度的一半时退回硬切。overlap 必须非负且小于 chunk_size。
- heading 按行首 `##` 加空白划分小节。有该类标题时，第一个标题前的正文不单独成块；没有时使用整段非空文本。
- heading 的超长阈值为有效长度400，再切目标300、overlap=0，均是 `heading.py` 内部常量；不会使用配置中的 chunk_size / overlap。
- 配置接受 `recursive`，当前实现将非 heading 策略都交给 fixed；没有独立的递归分块算法。
- 有效长度低于10的块被丢弃，保留块的 ordinal 从0连续编号。块文本严格等于规范化全文的 `[char_start:char_end]`。

chunk_id 格式为 `{doc_id}#{sha256(chunk.text)前8位}@{occurrence}`，occurrence 是同一文档中相同完整文本哈希的出现序号，从1开始。它与文本及文档路径有关，不保证在改正文或改分块后保持不变。

块 metadata 包含 strategy、char_start、char_end、content_hash；最后一项为块文本 SHA-256 的前16位。

## 向量化与索引存储

hashing 将 token 的 SHA-256 映射到向量维度并累加带符号词频；它是字面特征，不是训练出的语义模型。BGE 通过可选依赖 sentence-transformers 生成向量，模型按 model_name 懒加载、进程内缓存；首次使用模型名可能下载文件，离线使用需预先缓存或提供本地路径。

两种实现都输出 L2 归一化向量；空输入或无有效向量时可能为零向量。BGE 的输出维度须与请求 dim 一致。向量检索逐行点积，未使用近似最近邻索引。

embedding provider/model_name 保存在模块全局状态，`build` 与 `load_index` 会调用 configure。`load_index` 优先采用 manifest 中的 provider/model_name，维度取自已加载的向量库。进程中切换另一套索引会改变后续查询的 embedding 实现；当前接口没有按索引隔离模型状态。

```text
index_dir/
├── vectors.npy      float32，形状 (N, dim)
├── ids.json         N 个 chunk_id
├── metadata.json    N 份块元数据
├── manifest.json    version、dim、count、provider、model_name
└── chunks.jsonl     每行一个完整 Chunk
```

前三份向量文件的第 i 行对应同一块。`stores.write` 校验维度、列表长度和 ID 唯一性，先写临时文件再逐个 `os.replace`，随后直接写 manifest；`build` 最后另写并替换 chunks.jsonl。**整套索引不是一个原子事务**，写入中断可能留下新旧文件混合或不完整内容。

`stores.load` 校验向量维度及 vectors/ids/metadata 的行数；当前不比较 manifest.count，不校验文件内容哈希。`load_index` 再检查 chunks 与向量库的 ID 集合相同，并从 chunks 重建 BM25。这些检查不能证明文件字节、所有内容或原始语料版本一致。加载得到的 failures 为空，建库时的坏文件记录未落盘。

## 检索、融合与拒答

`search(query, *, bm25, store, id_to_chunk, dim, retrieval)` 分别运行启用的 BM25 和 dense 通道，各取 top_k；随后直接选择一种排名融合，最多返回 final_k 个块：

- `rerank_enabled=True`：`Σ w_i/(60+rank_i)`；双路的 BM25 权重为配置 α、dense 为 1−α。
- `rerank_enabled=False`：等权 RRF，再截取 final_k。
- 单路加权归一为1；双路都关闭时返回空结果。

`rerank` 没有调用额外模型，也没有在 RRF 之后运行 cross-encoder。直接调用 `rerank` 的 alpha 默认值为0.9；主流水线显式传配置值，默认0.7。

`RetrievalResult` 包含候选、各阶段轨迹和 match_score。match_score 仅在 sparse 通道启用时计算：查询中符合规则且语料未出现的首字母大写英文标识符使其为0；否则计算查询实词在前3个 BM25 结果中的 IDF 加权覆盖率。实词来自 terms、长度至少2、剔除停用词；没有实词时返回 None。

`answer_question` 在结果为空，或阈值大于0且有效 match_score 低于阈值时拒答。关闭 BM25 或没有覆盖率信号时，阈值不能判断是否有答案。覆盖率和英文实体规则不能证明证据足以回答问题。

## 回答与 HTTP

`llm.provider=none` 返回最高分块原文；citations 和 contexts 包含全部最终候选。confidence 搬运第一名的排名融合分数，未经概率校准。拒答时 answer 为空、引用与上下文为空，trace 保留。`openai_compatible` 会抛 NotImplementedError，当前没有远程生成实现。

`create_server(host, port, built, cfg)` 尝试预热 embedding 后构造 ThreadingHTTPServer，由调用方启动 serve_forever。预热失败记录日志，不阻止服务创建。CLI serve 负责加载一次索引，后续请求复用该对象。

| HTTP 路由 | 返回内容 |
|---|---|
| `GET /`、`GET /index.html` | 内置静态检索页面 |
| `GET /healthz` | 服务版本、索引块数、状态 |
| `GET /api/knowledge` | 文档列表及每篇块数 |
| `GET /api/chunks?doc=...` | 指定 doc_id 的全部块，按 ordinal 排序 |
| `POST /ask` | 请求 JSON 含字符串 query，返回 Answer |
| `POST /api/search` | 返回候选原文、排名分、match_score、refused 和检索耗时；不调用回答层 |

合法请求处理成功及拒答都返回200；请求格式错误返回400，未知路径返回404，处理异常记录日志并返回500。PUT、DELETE、PATCH 被显式拒绝为405；其他方法按标准库行为处理。

## 评测与测试边界

`evaluate(built, cfg, qrels, *, ks=...)` 只调用 search，不调用回答层。标准答案是 doc_id 加字符区间；同文档且区间有任何交集就算命中。Recall@k 是前 k 个候选命中的答案区间数占该题答案区间总数的比例；MRR 是首次命中任一答案区间的倒数排名。无答案题不进入两者的平均。

报告同时统计无答案题的正确拒答率和有答案题的误拒率，并按 source 分别汇总有答案题。命中不能证明证据完整或答案正确；source 不等于 dev/test 划分。默认 final_k=5 时，报告中的 @6～10 没有新增候选，不能作为更深召回的成绩。

耗时为检索轨迹各阶段之和。cold_ms 是首个查询的检索阶段耗时，可能包含 BGE 首次加载；不包含进程启动、此前的索引读取及 BM25 重建。warm 统计后续查询，不是 HTTP 端到端延迟。

`run_ablation` 固定六组：baseline、alpha_09、alpha_05、no_rerank、bm25_only、dense_only。各组复用一个索引，仅覆盖 RetrievalConfig；它会从模型默认配置构造各组，不继承任意调用方的完整配置。消融结论需要同时记录代码、标注、语料/索引版本和有效配置。

现有 pytest 覆盖基础实现和接口，未包含真实 BGE 模型的自动回归；当前 CLI eval 测试还存在旧格式夹具，不能仅凭全绿认定评测语义或回答质量已验证。具体待办见 [SUMMARY](SUMMARY.md)。
