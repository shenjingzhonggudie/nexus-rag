# 能力边界与待办

当前命令、有效配置和实测数据统一见 [README](../README.md)；模块接口与数据约束见 [PROJECT_LAYOUT](PROJECT_LAYOUT.md)，标注维护见 [data/README](../data/README.md)。本页仅记录尚未解决的边界。

## 当前边界

- 已实现文本/Markdown 加载、分块、BM25、hashing/BGE 向量检索、排名融合、可选 cross-encoder、原文抽取、引用、HTTP/CLI 和检索评测。embedding 与 reranker 均为可选模型，离线运行依赖各自本地文件。
- `fusion.py` 负责加权或等权 RRF，`rerank.py` 负责 query-document 模型打分。每路召回 top_k、融合去重取 top_k、可选重排后取 final_k；重排默认启用且仅加载本地文件。公开仓库不包含权重，新机器须安装 `[rerank]` 并下载模型，或显式关闭重排。启用失败明确报错；原始 logit 可负且不是概率，拒答 match_score 仍由独立 BM25 信号计算。旧 retrieval.rerank_enabled 只迁移融合方式并警告，不修改模型开关；模型由独立的 rerank.enabled 控制。
- `llm.provider=none` 返回第一名块原文；`openai_compatible` 尚未实现。
- 拒答依靠英文标识符与词语覆盖率规则，难以区分“主题相关”和“证据足够”。开发集45道无答案题全来自internal，external没有无答案题，尚不能判断external来源的拒答表现。
- v2按回答要点的必要证据覆盖判分，每段须严格超过50%；Recall/MRR衡量检索覆盖，未验证最终回答正确性。证据标注由AI辅助逐题核对，尚无独立人工验收。开发集已参与反馈，不能作为未见问题上的独立结论；历史盲测原档不变，固定输出的v2重评另存于 `experiments/holdout-evidence-v2/`。
- 索引逐文件写入，缺少整库事务及完整性哈希校验。embedding 使用进程全局状态，当前接口不支持多模型索引间的独立状态。

## 已知待办

| 项目 | 当前问题与下一步 |
|---|---|
| 标注工具坐标 | `section_index.py`、`gen_queries.py`、`build_skeleton.py` 直接规范化原始文件，与建库前的加载清洗不一致；其偏移不能直接用作当前标注，需要统一处理链 |
| 模型回归 | 2026-10-26已完成真实BGE reranker的同版本开关对照，详见README与实验归档；本机CPU每查约11秒，拒答未改善。pytest/CI仍不包含预训练模型质量回归，尚无新独立题集验收；六组旧消融均关闭真实重排，不能代替此次模型开关对照 |
| 证据与拒答 | 固定人工核验样本，检查返回证据是否足以回答；在开发集上调整规则，再用未参与选择的新题评估 |
| 评测输出 | 默认 final_k=5，当前仍输出 @6～10；应限制展示范围或显式区分粗召回与最终候选指标 |
| 样本构成 | multi_block仅16/248（6.5%），cross_doc仅5/248（2.0%）；多块、跨文档及external无答案拒答均需更多独立样本验收，当前multi_block配比偏差会使strict检查失败 |
| 分块配置 | heading 使用内部400/300/0常量，配置中的 chunk_size/overlap 不生效；recursive 暂走 fixed，需要明确实现或限制配置 |

生成模型、增量索引、新文件格式和服务部署能力仍需各自实现与验证；重排的证据排序收益与CPU开销已有本机观测，尚需在新题和实际使用中检验。是否增加这些功能，应由具体使用需求和测量结果决定。

## 文档维护

README 维护当前配置和一次明确环境下的实测数据，避免多处复制成绩。PROJECT_LAYOUT 维护当前行为；LEARNING_LOG 和历史任务书保留过程记录，其旧实现与旧数字不能直接当作当前状态。修改正文、加载或规范化规则后，标注字符坐标需重新核验。
