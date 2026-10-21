# LEARNING_LOG

> 记录格式参考任务书 §9。每轮追加一条，**失败、误判与返工原因一并记录**，不只记"完成了什么"。
>
> 项目：RAGKit —— 从零手搓的中文技术文档 RAG 系统（不使用 LangChain / LlamaIndex，默认离线可运行）
> 最后更新：2026-10-21
>
> **常驻章节**：`协作协议（常驻）` 与 `贯穿各轮的通用规律` —— 这两节约束"以后怎么干活"，其余章节是逐轮记录。

## 进度总览

| 轮次 | 日期 | 主题 | 用例数（累计） | 结果 |
|---|---|---|---|---|
| 第 0 课 | 2026-09-29 | 环境初始化与可运行骨架 | 3 | 3 passed |
| 第 1 轮 | 2026-10-01 | 领域模型：`Document` / `Chunk` | 17 | 17 passed |
| 第 2 轮 | 2026-10-02 | 嵌套模型：`ScoredChunk` / `Citation` | 23 | 23 passed |
| 第 3 轮 | 2026-10-03 | 列表与可选嵌套：`StageTrace` / `RetrievalTrace` / `Answer` | 39 | 39 passed（经一轮返工） |
| 第 4 轮 | 2026-10-05 | 配置系统：`config.py` + `errors.py` + `configs/default.yaml` | 52 | 52 passed（中途遭遇环境损坏，重建 `.venv` 后通过） |
| 第 5 轮 | 2026-10-07 | 配置：环境变量覆盖 + 深合并 + 密钥脱敏 + 测试隔离 | 64 | 64 passed（污染环境后仍全绿） |
| 第 6 轮 | 2026-10-09 | 文本层：规范化 + 分词（`text/`） | 82 | 82 passed |
| 第 7 轮 | 2026-10-11 | 加载层：`loaders/`（编码回退、坏文件隔离、相对路径坐标系） | 97 | 97 passed |
| 第 8 轮 | 2026-10-11 | 分块层：`chunking/` + 稳定 `chunk_id` | 141 | 141 passed |
| 第 9 轮 | 2026-10-13 | 向量化层：`embeddings/`（Hashing Embedding） | 155 | 155 passed |
| 第 10 轮 | 2026-10-13 | NumPy 向量库：`stores/`（原子落盘、加载校验） | 169 | 169 passed |
| 第 11 轮 | 2026-10-14 | BM25（`retrieval/`） | 180 | 180 passed |
| 第 12 轮 | 2026-10-15 | dense 检索 + RRF 融合（`retrieval/`） | 197 | 197 passed |
| 第 13 轮 | 2026-10-15 | 重排 + trace + 流水线编排（`retrieval/`） | 213 | 213 passed |
| 第 14 轮 | 2026-10-16 | 建库流水线 + 索引加载（`index/`） | 225 | 225 passed |
| 第 15 轮 | 2026-10-16 | 生成层（`generation/`） | 231 | 231 passed |
| 第 16 轮 | 2026-10-16 | CLI（`ragkit build` / `ragkit ask`） | 239 | 239 passed |
| 第 17 轮 | 2026-10-16 | HTTP API + 请求日志（`api/`） | 252 | 252 passed |
| 第 18 轮 | 2026-10-17 | 评测集与指标（`evaluation/`） | 263 | 263 passed |
| 第 19 轮 | 2026-10-17 | 消融实验（`evaluation/ablation.py`） | 267 | 267 passed |
| 第 20 轮 | 2026-10-17 | 落地消融结论（rerank 默认关） | 268 | 268 passed |
| 第 21 轮 | 2026-10-17 | 交付：README 收尾 + 打包（版本 1.0.0） | 268 | 268 passed |
| 第 22 轮 | 2026-10-17 | 总结报告（`SUMMARY.md`）——主线收官 | 268 | 268 passed |
| 第 23 轮 | 2026-10-17 | 加权排名融合落地（`weighted_fuse`，α=0.9 默认） | 272 | 272 passed |
| 第 24 轮 | 2026-10-21 | 语料重建（10 篇 × 10000 字）+ 块级标注 + heading 再切 | 272 | 272 passed |
| 事故 | 2026-10-05 | 「行尾 t 批量删除」事件（详见文末事故记录） | — | 已恢复 |

> **阶段 1 于 2026-10-07 收官**：领域模型（7 个）+ 配置系统（5 个模型）全部完成，64 条测试全绿。
> **阶段 2（TXT / Markdown 部分）于 2026-10-11 收官**：清洗 + 分词 + 加载完成。HTML / PDF 加载器有意推迟，触发信号见 `PROJECT_LAYOUT.md` 债务表。
> **阶段 3 于 2026-10-11 收官**：分块与稳定 `chunk_id` 完成，141 条测试全绿。
> **阶段 4~6 于 2026-10-13~14 收官**：向量化（155）/ 向量库（169）/ BM25（180）。
> **阶段 7 于 2026-10-15 收官**：混合检索 + RRF 融合 + 重排 + trace + 流水线编排（213）。
> **阶段 8 于 2026-10-16 部分完成**：全量 `build` + `load_index`（225）；增量更新为扩展（触发信号：全量重建慢到痛）。
> **阶段 9 于 2026-10-16 收官**：生成层（231）——`build → search → answer_question` 全链路可跑，`RetrievalResult` 的第一个生产消费者就位。
> **阶段 10 于 2026-10-16 收官**：CLI（239）——全链路暴露成 `ragkit build` / `ragkit ask`，jieba stderr 噪声在源头治理（债务 9 消化一半）。
> **阶段 11 于 2026-10-16 收官**：HTTP API（252）——`POST /ask` / `GET /healthz`，索引常驻；系统从此可被程序组合。
> **阶段 12 于 2026-10-17 收官**：评测集与指标（263）——recall@k / MRR / 耗时表；实测基线 recall@1=0.917、MRR=0.958。
> **阶段 13 于 2026-10-17 收官**：消融实验（267，100 篇语料 + 300 条评测）——dense 腿 −0.160、rerank −0.06 负贡献，纯 BM25 最优。
> **阶段 14 于 2026-10-17 收官**：README 收尾 + 打包（版本 1.0.0）。
> **阶段 15 于 2026-10-17 收官**：总结报告（`SUMMARY.md`）——**主线阶段 0~15 全部完成，项目收官**。
> **第 23 轮（2026-10-17）**：加权排名融合落地——`weighted_fuse`（S=α·S1+(1-α)·S2，α=0.9 默认）替代默认 RRF 等权，272 passed。
> ⚠️ **第 6~18 轮的逐轮详情（遇到的问题 / 根因 / 通用知识）尚未补写**，总览里的数字来自当轮实测；第 19 轮已补。

---

## 协作协议（常驻，每轮都按它执行）

> 2026-10-12 确立。此前多数返工，根因都能归到"少问了哪个环节"上。

| # | 环节 | 谁 | 具体做什么 |
|---|---|---|---|
| 1 | **架构定位** | Agent | 固定格式见下节，**缺一步不算讲清** |
| 2 | **必须 vs 扩展** | Agent 列 · 用户裁 | 每条"扩展"必须写明**触发信号**（什么情况下才回来做）；写不出信号的直接不算数 |
| 3 | **决策清单** | Agent 起草 · 用户拍板 | 只收"昂贵 / 不可逆"的决策（数据结构、ID 规则、存储格式、坐标系、错误分类）；其余给默认值直接做 |
| 4 | **实现步骤** | Agent | 按"可独立验证的增量"拆，每步写明验收方式 |
| 5 | **实现** | 用户写核心算法 · Agent 写测试与脚手架 | 关键算法用户要能**手算一遍**（唯一保留的手写要求） |
| 6 | **架构问题** | Agent 问 → 用户先答 → Agent 纠正 | 四类轮换：**边界 / 契约 / 失败 / 演化**，每轮 2~3 题 |
| 7 | **债务留痕** | Agent | 明确写"这一轮故意推迟了什么、什么信号出现时必须回来补" |

### 架构定位的固定格式（三步）

**第一步：这个模块是干什么用的**（先讲用途，再讲接口）

- 问题的由来：没有它，哪一步做不下去？
- **没有它会怎样**（一条条列后果，而不是笼统说"很重要"）
- 它具体解决什么
- **它不解决什么**（划边界、避免期望错位）

**第二步：上游 / 下游写到调用现场**

不许只给抽象类型，必须写到：**谁、在第几阶段、传进来的具体是什么、拿输出后干什么**。推荐用带函数名的调用链：

```text
load_dir(Path("data/raw")) → LoadReport.documents
  └─ chunk_document(doc, chunk_size=400, overlap=50) → list[Chunk]
       └─ embed_text(chunk.text, dim=cfg.embedding.dim)   ←★ 本模块
            └─ list[float]（512 维单位向量）
                 └─ stores 落盘 → data/index/（chunk_id + 向量 + metadata）
```

同时要写明**上游给的"不是"什么**（例：本模块拿到的是字符串，**不是 `Chunk`**）。

**第三步：五问表**

| 问 | 内容 |
|---|---|
| 上游 / 下游 | 具体到函数与阶段 |
| 输入 / 输出 | 具体类型 |
| **不做什么** | 划边界（比"做什么"更重要） |
| 唯一改动理由 | 什么变了才需要动这个模块 |
| 相邻契约 | 挨着哪些已定死的契约（键集合 / 错误类型 / 路径坐标系 / 配置项） |

### "避免过度设计"的判据（2026-10-12 补充）

**不能按"未来会不会用到"判断，要按改动成本判断**：

| 类型 | 例子 | 怎么办 |
|---|---|---|
| 真·过度设计 | 给还不存在的第二个策略写抽象基类、插件注册机制 | 砍掉，等第二个真实实现出现再抽象 |
| **不可逆的基础设施** | `chunk_id` 规则、JSONL / manifest 格式、路径坐标系、错误分类 | **现在定死** |
| 可逆的小东西 | 尾块合并、参数默认值、日志格式 | 推迟（改起来便宜） |

### 三条不可让渡（决定"是否真的理解这个系统"）

1. 每个模块的**对外契约由用户确认**（Agent 只起草候选 + 代价）；
2. 关键算法用户要能**手算一遍**（对着代码推演正确性，不必写代码）；
3. **每轮复盘必须用户自己答** —— 这是唯一能暴露"理解断层"的环节。

### 一条对 Agent 的自我约束

**结论必须基于实测或可复现的推演，不能只靠纸面推演下判断。**
（反例：第 8 轮曾凭推演裁定"边界优先"，并据此要求用户改代码；后来实测证明该裁定错误——正确规则是"触底收尾"。**先复刻规则跑过证据，再下结论。**）

---

## 第 0 课：环境初始化与可运行骨架

- **完成日期**：2026-09-29
- **实现内容**：
  - `pyproject.toml`：src 布局（`[tool.setuptools.packages.find] where = ["src"]`）、`[project.scripts] ragkit = "ragkit.cli:main"`、pytest 配置
  - `src/ragkit/__init__.py`：包 docstring + `__version__ = "0.0.1"`
  - `src/ragkit/cli.py`：`argparse`，`main(argv: list[str] | None = None) -> int`，支持 `--version`
  - `tests/test_smoke.py`：3 条冒烟测试
  - `.gitignore`、`README.md`、git 仓库、`.venv`（Python 3.12）
- **测试数量与结果**：3 条，`pytest -q` → 3 passed
- **验收命令**：`pip install -e ".[dev]"`、`pytest -q`、`ragkit --help`、`ragkit --version` 全部通过
- **遇到的问题**：
  1. `cli.py` 模块顶层遗留调试代码 `for path in sys.path: print(path)`，污染 `--help` / `--version` 输出
  2. `README.md` 目录树未放进代码块；缺少 `pip install -e ".[dev]"` 这一步（别人照 README 跑不起来）
  3. `.gitignore` 里的 `.env.*` 会把 `.env.example` 一起忽略掉
- **问题根因**：
  1. 模块顶层代码在 `import` 时执行；导入一个模块不应产生可观察的副作用
  2. Markdown 中单个换行不换行，目录树必须放进代码块
  3. `.gitignore` 是后写覆盖先写，例外规则必须写在通配规则**之后**
- **学到的通用知识**：
  - 包 vs 目录：有 `__init__.py` 才是包；`src/` 只是"放包的抽屉"
  - `import` 查找：遍历 `sys.path` 里的路径，**第一个命中就停**
  - `.pth` 机制：site-packages 里的 `.pth` 每行是一条路径，解释器启动时自动加入 `sys.path`；**editable 安装的产物就是它**（实测内容：项目 `src` 的绝对路径）
  - 分发名 ≠ 导入名：`name` 只影响包管理器；`where` + 目录名决定 `import` 找谁；`[project.scripts]` 决定命令名叫什么、指向哪个模块
  - "改一个名字要同步多处"——包名涉及 `where` / `name` / `[project.scripts]` 三处，只有一处会真报错
  - 测试不证明代码正确，只**锁住已确认的行为**
- **尚未解决的技术债**：`.gitignore` 缺少 `!.env.example` 例外；建立 `.env.example` 时一并补上
- **下一阶段入口条件**：四条验收命令全部通过（已满足）

---

## 第 1 轮：领域模型 `Document` / `Chunk`

- **完成日期**：2026-10-01
- **实现内容**：
  - `src/ragkit/schemas.py`：模块级 `_require_fields`（统一报告缺失字段）、`Document`、`Chunk`，各含 `to_dict` / `from_dict`
  - `tests/test_schemas.py`：往返、键集合、JSON 可序列化、默认值不共享、缺失字段拒绝、参数化校验、新增字段兼容性
  - `Chunk` 新增可选字段 `score_hint: float = 0.0`（用于演练"新增字段如何不破坏旧数据"）
- **测试数量与结果**：新增 14 条，累计 17 条，全部通过
- **遇到的问题**：
  1. `Document` 字段名一度写成 `match_metadata`，与 `Chunk.metadata` 不一致；改名时只改了 `from_dict` 的调用处，漏掉字段声明 → `TypeError: Document.__init__() got an unexpected keyword argument 'metadata'`
  2. `dict[str, any]` 用了小写的 `any`（内置函数），不是 `typing.Any`；**7 条测试全绿**
  3. 缺失字段校验只做了 `text` 一个，其余字段仍抛裸 `KeyError`（`{"text": "x"}` 缺 `doc_id` 时表现为两种不同错误）
  4. `to_dict()` 直接返回 `self.metadata`（引用），导出结果与源对象共享同一个字典
  5. 测试用位置参数构造对象，字段顺序一变就静默错位
  6. 键集合没有断言，契约改名无法被发现
- **问题根因**：
  1. 改名是多点同步操作，手改必然漏；应使用编辑器"重命名符号"并全局搜旧名确认 0 命中
  2. 类型注解**运行时不做检查**，只有编辑器 / 类型检查器才看得见
  3. 校验要么全做要么不做："做一半"比"不做"更糟——调用方会以为有统一异常可捕获
  4. 混淆了两个层面的共享：层一 = 两个实例之间（由 `field(default_factory=...)` 保证）；层二 = 对象与它的导出结果之间（**没有任何保障**）
  5. `to_dict`/`from_dict` 是对称的，往返相等性检验看不出错位
  6. `restored == scored` 只验"对称性"，验不了"契约",也验不了"值本身写错"
- **学到的通用知识**：
  - 数据模型是模块之间的合同，先定模型再写算法
  - `@dataclass` 自动生成 `__init__` / `__repr__` / `__eq__`；**有默认值的字段必须排在无默认值字段之后**
  - 可变默认值陷阱：`= {}` 求值一次并被所有实例共享 → 必须用 `field(default_factory=dict)`；Python 3.11+ 的 `@dataclass` 会直接拒绝可变默认值
  - **roundtrip 的三类盲区**：① 键名被对称改名（靠键集合断言）② 嵌套类型悄悄变化（靠 `isinstance` / `json.dumps`）③ 值本身写错但两侧一致（只能靠"独立期望值"或人工审查）
  - `.get(键, 默认值)` 是**向后兼容**的全部秘密；把新增字段写进必填清单会让旧数据全部读不出来
  - 用 `set(...) == {...}` 锁键集合，不要用列表（顺序无关），也不要写"包含"（对多余内容视而不见）
- **尚未解决的技术债**：`schemas.py` 存在若干行尾空格（W291）；`.env.example` 例外仍未补
- **下一阶段入口条件**：17 条测试通过 + `match_metadata` 全局搜索 0 命中（已满足）

---

## 第 2 轮：嵌套模型 `ScoredChunk` / `Citation`

- **完成日期**：2026-10-02
- **实现内容**：
  - `ScoredChunk`：`chunk: Chunk` / `score: float` / `stage: str` / `sub_scores: dict[str, float]`，`to_dict` 做**递归降级**、`from_dict` 做**递归升格**
  - `Citation`：`index` / `source` / `snippet`（必填）+ `title`（可选）
  - 测试：`test_scored_chunk_roundtrip`（键集合 + JSON + `isinstance` + 往返）、`test_sub_scores_default_is_not_shared`、`test_scored_chunk_from_dict_requires_fields`（参数化）、`test_citation_roundtrip`
- **测试数量与结果**：累计 23 条，全部通过
- **遇到的问题**：
  1. 实验（故意把 `self.chunk.to_dict()` 写成 `self.chunk`）→ `TypeError: argument of type 'Chunk' is not iterable`，**报错位置在 `_require_fields` 的 `name not in data` 那一行**
  2. `test_citation_roundtrip` 从 Document 测试复制粘贴，字段名全部不适用 → `TypeError: Citation.__init__() got an unexpected keyword argument 'doc_id'`
  3. `ScoredChunk` 的键集合断言漏写 `sub_scores`
  4. `assert isinstance(doc.chunk, Chunk)` 断在**原始对象**上 → 恒为真的"安慰剂断言"
  5. 位置参数在上一轮刚改成关键字参数后**又回到**了位置参数
  6. 测试数据写成 `Chunk("chunk_id=chunk-1", ...)`（把键值整体塞进字符串当位置参数）→ **23 条测试全绿，但 `chunk_id` 的值是错的**
- **问题根因**：
  1. 缺陷会被谁先暴露，取决于 `from_dict` 有没有真正处理嵌套；错误位置常常离病灶很远，看堆栈要看最底下那一行
  2. 复制粘贴测试时只改了名字，没改字段
  3. 契约清单靠人记忆维护，必然漏
  4. 断言对象选错 → 测试的"绿"是虚假的
  5. 规则没有一致执行
  6. 对称往返掩盖了"输入侧写错"——测试原则上抓不到自己输入里的错误
- **学到的通用知识**：
  - `to_dict` 必须返回**只含基础类型**的结构；嵌套对象一律调用它自己的 `to_dict`（递归可序列化）
  - `json.dumps` 断言是**不可替代**的：只有它能抓"`to_dict` 塞对象 + `from_dict` 原样塞回"这种"数据从没真正序列化过"的情况
  - **永远为真的断言不是测试**，它给的是虚假安全感
  - 测试可以合并同主题的多条断言（可诊断性够用即可），但**每条断言都要能说清它在防什么**
- **尚未解决的技术债**：`schemas.py` 行尾空格未清（第 70 / 78 / 81 / 91 行）
- **下一阶段入口条件**：23 条测试通过（已满足）

---

## 第 3 轮：列表与可选嵌套 `StageTrace` / `RetrievalTrace` / `Answer`

- **完成日期**：2026-10-03
- **实现内容**：
  - `StageTrace`：`name` / `latency_ms` / `candidate_count`，自带 `to_dict` / `from_dict`（供容器调用）
  - `RetrievalTrace`：`stages: list[StageTrace]` + 方法 `total_latency_ms()`（不设冗余字段）
  - `Answer`：`question` / `answer`（必填）、`citations: list[Citation]`、`refused`、`confidence`、`contexts: list[str]`、`trace: RetrievalTrace | None`；docstring 写明拒答约定与 `trace=None` 的语义
  - 宽容加载策略：`citations` / `contexts` / `stages` 缺失或为 `None` 时按空处理
  - 测试：`test_stage_trace_roundtrip`、`test_retrieval_trace_roundtrip`、`test_stages_default_is_not_shared`、`test_answer_roundtrip`、`test_answer_roundtrip_without_trace`、`test_answer_from_dict_requires_fields`、`test_answer_from_dict_without_optional_fields`
- **测试数量与结果**：累计 39 条 → **38 passed / 1 failed**（失败：`test_answer_from_dict_without_optional_fields`）
- **遇到的问题**：
  1. `Answer` 漏了 `@dataclass` → `TypeError: Answer() takes no arguments`（4 条 Answer 测试全红）
  2. `Answer.from_dict` 漏了 `@classmethod` → `cls` 不会绑定
  3. `_require_fields` 把**有默认值的字段**当成必填（`stages`；以及 `Answer` 的 `citations` / `refused` / `confidence` / `contexts`）→ 与字段声明自相矛盾，旧数据完全读不出来
  4. 字段改名 `retrieved_traces` → `stages`，测试没跟着改 → `TypeError: ... unexpected keyword argument 'retrieved_traces'`（**同一类坑第三次**）
  5. 测试 `test_answer_from_dict_without_optional_fields` 里把所有可选字段都提供了 → 名不副实，抓不到问题 3
  6. 收尾时 `refused=data["refused"]` / `confidence=data["confidence"]` 仍是硬索引 → `KeyError: 'refused'`（**当前唯一红灯**）
  7. `.get("stages", [])` 遇上 `{"stages": None}` → `TypeError: 'NoneType' object is not iterable`
- **问题根因**：
  1. 装饰器是类/方法的定义部分，漏写不会在 import 时报错，只在调用时才炸
  2. 同上
  3. 可选性有两个真相来源（字段默认值 vs 校验清单），二者不一致
  4. 改名未做全局收尾检查
  5. 测试数据按"实现的胃口"写，而不是按"真实的最坏输入"写
  6. 收紧校验清单时只改了清单，没改函数体
  7. `.get(k, default)` 的默认值**只在"键不存在"时生效**；键存在但值是 `None` 时它如实返回 `None`
- **学到的通用知识**：
  - **列表字段**同样只用 `field(default_factory=list)`；列表里的嵌套要靠列表推导双向处理
  - **"缺失"与"为空"是两种输入**：`.get(k, d)` 挡不住 `None`；判断要用 `is None`，不要用真值判断（`bool(dict()) == bool(list()) == False`）
  - 同一行为在不同场景的正确做法可能相反：`from_dict` 忽略未知键是为了**兼容旧数据**；配置文件的未知键必须**报错**（那是人刚写下的意图）
  - 能算出来的值不要存字段（`total_latency_ms()` 用方法），否则两个来源迟早不一致
  - **"边界校验、内部信任"**：内部数据（`schemas.py`）用 dataclass，外部输入（`config.py`）用 Pydantic
- **尚未解决的技术债**：
  - `Answer.from_dict` 中 `refused` / `confidence` 仍为硬索引（阻塞）
  - `Answer.to_dict` 中 `trace` 用真值判断（应与 `from_dict` 统一为 `is not None`）
  - `Answer.to_dict` 中 `contexts` 返回对象自己的列表引用，而 `citations` 是新列表，前后不一致
  - `schemas.py` 第 70 / 78 / 81 / 91 行行尾空格
- **下一阶段入口条件**：39 条测试全部通过，且三条兼容性命令正常（`from_dict({})`、`from_dict({'stages': None})`、`Answer.from_dict({'question','answer'})`）

---

## 第 4 轮：配置系统 `config.py` / `errors.py` / `configs/default.yaml`

- **完成日期**：2026-10-05
- **实现内容**：
  - `src/ragkit/errors.py`：`RagkitError`（领域异常基类）、`ConfigError`（配置内容非法）
  - `src/ragkit/config.py`：五个 Pydantic 模型 `RetrievalConfig` / `ChunkingConfig` / `EmbeddingConfig` / `LLMConfig` / `AppConfig`，每个都带 `model_config = ConfigDict(extra="forbid")`；跨字段约束用 `@model_validator(mode="after")`；加载函数 `load_config(path: str | Path | None = None) -> AppConfig`
  - `configs/default.yaml`：与模型默认值完全一致的配置模板
  - `tests/test_config.py`：13 条（默认值、文件不存在、YAML 覆盖、空文件、顶层非映射、6 条参数化的非法取值、未知键、往返）
  - `pyproject.toml`：新增运行时依赖 `pyyaml`、`pydantic`
- **测试数量与结果**：新增 13 条，累计 52 条，全部通过（`pytest -q` → 52 passed）
- **遇到的问题**：
  1. 测试文件写了 `from config import ...`（不存在的顶层模块）→ 整份测试文件在**收集阶段**就 ERROR，8 条测试一条都没跑
  2. 五个模型都漏了 `ConfigDict(extra="forbid")`（`ConfigDict` import 了却没用）→ YAML 里写错键名被**静默忽略**，用户以为改生效了，其实还在用默认值
  3. `load_config` 里把 `None` 写成了 `NotImplemented` → 空文件被当成非法配置抛错
  4. `cfg.retrieval.llm.provider` 访问了不存在的属性（`llm` 不在 `RetrievalConfig` 里）
  5. `data.model_validate()` 调在了 dict 上（`model_validate` 是类方法）
  6. `test_invalid_values_rejected` 把 6 个 case 串在一个函数里，且其中两段 YAML 用了 TAB 缩进（YAML 直接抛 ScannerError，根本进不到 Pydantic）
  7. 曾把"文件读取输出里的缩进看起来像 TAB"当成结论（实测文件里是空格），并且引用了**我自己构造的**字符串得到的 `ScannerError` 作为佐证
- **问题根因**：
  1. 导入失败属于"**收集期错误**"，与断言失败（运行期）是两类问题，pytest 分别报 `ERROR` 与 `FAILED`
  2. 允许未知键是 Pydantic 的**默认行为**；配置场景要求"大声报错"，必须显式开启，而且是**逐模型**生效
  3. `NotImplemented` 是运算符重载用的单例，与 `None` 毫无关系——纯笔误
  4. 属性名记错，且类型注解不到位时编辑器帮不上忙
  5. `model_validate` 是类方法
  6. 参数化才能让每个 case 独立执行；YAML 规范禁止用 TAB 缩进
  7. 不可见字符无法靠肉眼判断；**对照实验的结论不能直接当作被测文件的证据**
- **学到的通用知识**：
  - **"边界校验、内部信任"**：内部数据（`schemas.py`）用 dataclass——来源可信、要快；外部输入（`config.py`）用 Pydantic——人写的、会错，需要类型检查与可读错误
  - `model_validator(mode="after")` 的错误 `loc` 是**空的**，所以**消息里必须自己带上字段名和具体数值**（如 `f"final_k ({self.final_k}) 不能大于 top_k ({self.top_k})"`）
  - 参数化用 `pytest.param(..., id="zero-top-k")` 给每个用例起语义化名字；用 `any(field in msg for field in expected_fields)` 处理"报哪个字段都可能"的情况
  - **遇到容易反复踩的结构性坑，换一种写法让它不可能发生**（多行 YAML 缩进 → 单行 flow mapping `"retrieval: {top_k: 0}"`），比"小心别按 Tab"可靠得多
  - 异常分工：路径不对用标准异常 `FileNotFoundError`，内容不对用领域异常 `ConfigError`；包装时 `raise ... from exc` 保留原始堆栈
- **尚未解决的技术债**：`errors.py` 第 8~11 行注释内有 4 个制表符（纯风格，不影响运行）
- **下一阶段入口条件**：52 条测试通过 + 未知键被拦截且消息含字段名 + `default.yaml` 与模型默认值一致（已满足）

---

## 第 5 轮：环境变量覆盖与密钥脱敏（阶段 1 收官轮）

- **完成日期**：2026-10-07
- **实现内容**：
  - `config.py`：模块常量 `ENV_PREFIX = "RAG__"` / `MASK = "******"`；`_deep_merge`（先 `deepcopy` 再递归合并）；`_collect_env_overrides`（支持顶层与一层嵌套，段数 ≥ 3 忽略）；`load_config(path, environ)` 改签名并插入"收集覆盖 + 深合并"两步；`AppConfig.snapshot()`；`LLMConfig.api_key` 加 `Field(repr=False)`
  - `tests/test_config.py`：新增 12 条（覆盖与深合并、类型转换、顶层字段、非法环境变量、未知环境变量、无关变量忽略、段数 ≥ 3 忽略、快照脱敏、JSON 可序列化、其他字段不被改动、repr 不泄漏）；并为既有 11 处 `load_config` 调用补上 `environ={}`
- **测试数量与结果**：新增 12 条，累计 **64 条全部通过**。**测试隔离自证**：在真实环境设 `RAG__RETRIEVAL__TOP_K=99` 后重跑，仍 64 passed
- **遇到的问题**：
  1. 首轮 7 条红灯，**全部是测试侧错误**：环境变量名写成 `RAGKIT_RETRIEVAL_TOP_K`（前缀错 + 少双下划线）；改成 `RAG__RETRIEVAL__TOP__K`（多一个下划线）后又被"段数 ≥ 3 忽略"规则吃掉
  2. `test_env_merges_deeply` 全程**没有注入任何环境变量**（深合并等于没测），却留了一句 `del os.environ[...]` 删不存在的键 → `KeyError`
  3. 把 `RAG__HOMEPAGE` 归入"无关变量"，但它格式合法、字段不存在，按设计应当报错
  4. 三条 snapshot 测试的 YAML 写成 `api_key="..."`（少冒号）→ YAML 把整行当成字符串，Pydantic 报 `model_type`
  5. 四条 snapshot 测试调的是 `appconfig.model_dump()` 而不是 `appconfig.snapshot()` → 测的是"不脱敏的导出"
  6. `test_snapshot_keeps_other_fields` 断言 `chunk_size == "400"`（字符串 vs 整数）
  7. 用 `os.environ` 注入的测试，断言失败后 `del` 不执行 → 变量泄漏给同批其他测试（本次泄漏的刚好是会被忽略的名字，纯属运气）
  8. venv 曾用 IDE 运行时缓存里的 Python 创建（`base_prefix` 指向 `.cache\codex-runtimes\...`），已改用系统 Python 3.12 重建
- **问题根因**：
  1. 命名规则靠手写、没有对照；"多一个下划线"这类错误在运行时表现为**静默忽略**而非报错
  2. 只写了断言，没有真正构造输入
  3. 用例归类错误：把"应当报错"的例子放进了"应当忽略"的用例
  4. YAML 里 `key = value` 不是赋值，是字符串
  5. **测试调用了错误的方法**：想验 A，实际测了 B（第 2 轮 `isinstance(doc.chunk, ...)` 是同一类错误）
  6. 类型不一致的断言在 Python 里直接为假
  7. 清理代码写在断言之后，断言失败就跳过了
  8. 创建 venv 时的 `python` 来自 IDE 运行时，而不是系统安装的解释器
- **学到的通用知识**：
  - **覆盖层只提供原始值，校验只在一处**：环境变量永远是字符串，类型转换交给 Pydantic（`bool("false")` 是 `True`，自己转必踩坑）
  - **深合并必须手写**：`dict.update()` 是浅合并，会把整个子字典替换掉，同层其他字段全丢
  - **参数可注入 = 测试可隔离**：`load_config(environ=...)` 与第 0 课的 `main(argv=...)` 是同一个设计；"污染真实环境后必须照旧全绿"是测试可靠性的最低标准
  - **脱敏测试要断言"原文不出现"**，不要断言"等于某个掩码"
  - **`snapshot()` 必须用 `model_dump(mode="json")`**，否则 `Path` 进不了 JSON
  - `monkeypatch.setenv` 比手写 `os.environ` + `del` 安全（测试结束自动回滚，失败也不泄漏）
- **尚未解决的技术债**：`errors.py` 注释里的 4 个制表符；仓库仍无任何提交
- **下一阶段入口条件**：64 条测试全绿 + 隔离自证通过（已满足）

---

## 阶段 1 收官（2026-10-07）

**交付物**：`schemas.py`（7 个领域模型）、`config.py`（5 个配置模型 + YAML 加载 + 环境变量覆盖 + 脱敏）、`errors.py`、`configs/default.yaml`；测试 64 条（冒烟 3 + 模型 36 + 配置 25）。

**任务书验收对照**：

| 任务书要求 | 状态 |
|---|---|
| 用 dataclass / Pydantic 实现模型 | ✅ 7 个领域模型（dataclass）+ 5 个配置模型（Pydantic） |
| `to_dict` / `from_dict` | ✅ 含嵌套、列表、可选嵌套、宽容加载 |
| YAML 配置加载 | ✅ `configs/default.yaml` + `load_config` |
| 环境变量覆盖 `RAG__RETRIEVAL__TOP_K=30` | ✅ 顶层与一层嵌套，递归深合并 |
| 对密钥脱敏输出 | ✅ `snapshot()` + `Field(repr=False)` |
| 测试：序列化往返一致 | ✅ |
| 测试：非法配置被拒绝 | ✅（未知键、跨字段、类型、非法 JSON 结构） |
| 测试：环境变量优先级高于 YAML | ✅ |
| 测试：API Key 不出现在配置快照中 | ✅ |

**复盘问答**：为什么稳定的数据模型比一开始就写检索算法更重要？

- 学员答案：*"稳定的数据模型相当于基础，检索算法是建立在稳定的数据模型上的。"*
- 补充修正：方向对，但"基础"是同义反复，要落到具体代价上——**数据模型决定的是对外契约**：JSONL 的键名、manifest 的字段、API 响应的形状都从它派生，改一个字段名意味着已落盘的索引、评测数据、接口全都要跟着迁移；而**检索算法可以随时替换**（BM25 换向量、RRF 换加权融合），只要它读写的还是同一套模型，外部什么都不用改。**先固定契约，再迭代算法，返工成本差一个数量级。**

---

## 事故记录：2026-10-05「行尾 t 批量删除」事件

- **发生时间**：2026-10-05 09:42–09:52（由文件修改时间推得，十分钟内按批次重写文件）
- **现象**：**凡以 `t` 结尾的行，行尾的 `t` 被删除**，无例外
  - `ordinal: int` → `ordinal: in`；`score: float` → `score: floa`；`index: int` → `index: in`
  - `import pytest` → `import pytes`；`import ragkit` → `import ragki`；`capsys.readouterr().out` → `....ou`
  - `.venv` 内：`import inspect` → `import inspec`；`import ast` → `import as`；`lineno: int` → `lineno: in`
- **影响范围**：
  - `.venv`：1245 个 `.py` 中 **66 个语法损坏**，虚拟环境整体不可用
  - 项目源码：**6 处**（`src/ragkit/schemas.py` 3 处、`tests/test_smoke.py` 3 处）
  - 其余文件（`config.py`、`test_config.py`、`test_schemas.py`、`cli.py`、`errors.py`、`pyproject.toml`、`configs/default.yaml`、三个 `.md`）逐行核对后**未受损**
- **处置过程**：
  1. 先按报告里的清单手工修：项目源码 6 处（成功）+ venv 里 2 处（**打地鼠**：修好 `code.py:4`，又暴露 `code.py:1491`）
  2. 最终选择重建：`Remove-Item -Recurse -Force .venv` → `py -3.12 -m venv .venv` → `pip install -e ".[dev]"`
  3. 重建后复核：site-packages 1006 个 `.py` **0 个损坏**；项目源码 0 语法错误；`pytest -q` → 52 passed
- **根因**：**未查明**。怀疑是某次"文件夹级批量替换"或某个脚本的作用范围覆盖了整个项目目录（含 `.venv`），但至今没有复现，触发源仍未定位。
- **学到的通用知识**：
  1. **不可见字符靠工具判断，不靠眼睛**：空格 vs 制表符、CRLF vs LF、全角 vs 半角——`repr()` 或编辑器"显示空白字符"（VS Code 的 `Render Whitespace`）是唯一可靠的办法。我这次和你这次，都是没做这一步就下了结论。
  2. **"清单"是示例，不是完整清单**：损坏报告里列了 `code.py:4` 和 `typing_extensions.py:8` 两处，修好这两处后 pytest 又卡在 `code.py:1491`。**大范围、可再生的小损坏，重建比修补便宜得多**——这个判断以后在缓存、依赖目录、索引数据上都会用到；只有**不可再生**的东西（自己写的代码、手工标注的评测数据）才值得逐个修。
- **遗留措施**：建议把 `.venv` 加入编辑器的 `search.exclude` 与 `files.watcherExclude`，并避免在项目根执行文件夹级替换；本项目至此仍无任何 git 提交，导致事故时无法用 `git diff` 定位、无法回滚。

---

## 第 12 轮：dense 检索 + RRF 融合（`retrieval/`）

- **完成日期**：2026-10-15
- **实现内容**：
  - `src/ragkit/retrieval/dense.py`：`dense_search(query, store, id_to_chunk, *, dim, top_k)`——`embed_text(query, dim=dim)` → `store.matrix @ q` 点积（两侧向量已归一化，点积即余弦）→ `argsort()[::-1][:top_k]` → `stage="dense"`，`score` 转纯 `float`
  - `src/ragkit/retrieval/fusion.py`：`rrf_fuse(results, *, k=60, top_k)`——按 `chunk_id` 聚合、rank 分累加、`stage="rrf"`
  - `__init__.py` 导出 `BM25Index` / `dense_search` / `rrf_fuse`
  - 统一空 query 行为：BM25 / dense 空 query 均返回 `top_k` 个分数全 0 的块
  - 测试：`test_dense.py`（9 条）、`test_fusion.py`（8 条）
- **测试数量与结果**：新增 17 条，累计 197 条，全部通过（`pytest -q` → 197 passed）
- **遇到的问题**（本轮是"用户写实现、Agent 验收"）：
  1. `fusion.py` 把 `chunk_id` 字符串塞进了 `ScoredChunk.chunk` 字段——key 用 `chunk_id` 去重，但最后 `for chunk, score in fused_scores.items()` 直接把字符串当 `Chunk` 用 → 实测 `type(out[0].chunk)` 是 `str`，下游 `.chunk.text` 会 `AttributeError`
  2. `dense.py` 调 `embed_text(query, dim)` 少了关键字（签名是 `embed_text(text, *, dim)`）→ 一调用就 `TypeError`
  3. dense 空 query 返回全 0 分块、BM25 空 query 返回 `[]`，行为不一致
- **问题根因**：
  1. 聚合时"去重键"与"输出对象"混用同一个变量：key 是 id（只用于去重），却丢了原对象；且 dataclass 默认 `eq=True` 后不可哈希，`Chunk` 不能直接当 dict key，只能以 id 为 key、value 存 `(Chunk, 分数)`
  2. `*` 之后的参数必须关键字传入，位置传会 `TypeError`
  3. 两条腿各自实现了"空输入"语义，没有对齐
- **学到的通用知识**：
  - **`@` 矩阵乘法**：`(N, dim) @ (dim,) → (N,)`，一次算出 N 个块与 query 的点积；因向量已 L2 归一化，点积 = 余弦相似度
  - **`argsort()`** 返回"按值排序的下标"，`[::-1]` 反转降序、`[:top_k]` 取前 k；拿到下标再 `store.ids[idx]` 找回 chunk_id
  - **归一化责任归 embeddings 层**：在"向量诞生处"保证单位向量，store 原样存、dense 只点积；换真模型未归一化会退化成内积、长块虚高
  - **RRF 用 rank 融合**消解了"BM25 无上界 vs dense 0~1"的量纲不可比——不是去改谁，而是用排名
  - **`list[list[ScoredChunk]]` 的接口形状**把"腿的数量"从签名写死变成运行时可变：消融（1 腿）/ 未来加腿都不用改签名
- **尚未解决的技术债**：重排（rerank）与 `RetrievalTrace` 尚未实现（阶段 7 剩余部分）；BM25 空 query 的"全 0 分块"与"query 词全不在语料 → []"仍是两个分支，边界见 `PROJECT_LAYOUT.md`
- **下一阶段入口条件**：197 条测试通过 + 阶段 7 剩余（重排 + trace）启动

---

## 第 13 轮：重排 + trace + 流水线编排（`retrieval/`）

- **完成日期**：2026-10-15
- **实现内容**（用户写核心算法，Agent 写脚手架与测试）：
  - `src/ragkit/retrieval/rerank.py`：`rerank(candidates, query, store, *, dim, final_k)`——dense 余弦精排，`sub_scores["prev"]` 记精排前分数，降序截断到 `final_k`
  - `src/ragkit/retrieval/pipeline.py`：`search(query, *, bm25, store, id_to_chunk, dim, retrieval)`——按开关编排召回→融合→重排，`perf_counter()` 逐阶段计时生成 `RetrievalTrace`
  - `src/ragkit/retrieval/result.py`：`RetrievalResult`（`results` + `trace`）
  - `__init__.py` 导出 `rerank` / `search` / `RetrievalResult`
  - 测试：`test_rerank.py`（8 条）、`test_pipeline.py`（8 条）
- **测试数量与结果**：新增 16 条，累计 213 条，全部通过（`pytest -q` → 213 passed）
- **遇到的问题**：
  1. `test_rerank.py` 用 `monkeypatch.setattr("ragkit.retrieval.rerank.embed_text", ...)` 字符串路径全部 `AttributeError: 'function' object ... has no attribute 'embed_text'`
- **问题根因**：
  1. `__init__.py` 里 `from ragkit.retrieval.rerank import rerank`——**导入名（函数名）与子模块名同名**，`from X import Y` 会把 `ragkit.retrieval.rerank` 这个子模块属性**遮蔽成函数**；字符串路径逐级 `getattr` 到这一步就拿到函数而非模块。而 `pipeline.py` 里同款 `from ...rerank import rerank` 仍能工作，因为它走 `sys.modules`，不查父包属性
- **学到的通用知识**：
  - **`from package.submodule import name` 当 `name` 与子模块同名时，会遮蔽父包上的子模块属性**；`from ... import ...` 语句本身仍正常（走 `sys.modules`），但"字符串路径解析 / 直接 `package.submodule` 访问子模块"会拿到函数。测试 patch 模块属性时改用 `importlib.import_module("...")` 拿真实模块对象更健壮
  - **重排（rerank）是"粗排召回 + 精排排序"的分工**：召回靠 BM25/dense 两条腿，rerank 只在已召回的 top_k 内用连续分数（dense 余弦）重排，不召回新块
  - **trace 是"记录"不是"优化"**：`StageTrace(name/latency_ms/candidate_count)` 逐阶段测时，回答"慢在哪"，为阶段 14 耗时表铺路
- **尚未解决的技术债**：建索引流水线（load → chunk → embed → store → BM25Index）尚未串起，`search` 目前接收"已就绪的 bm25 + store + id_to_chunk"——属阶段 8；BM25 统计仍内存驻留未持久化（债务表 13）
- **下一阶段入口条件**：213 条测试通过 + 阶段 8（建库流水线 / 索引增量）启动

---

## 第 14 轮：建库流水线 + 索引加载（`index/`）

- **完成日期**：2026-10-16
- **拍板的决策**：① chunks 落盘用 **JSONL**（增量追加友好，坏一行只损一块；与 stores 的"整个数组"取舍相反但理由不同）；② BM25 统计**从落盘 chunks 重建**，不新增统计落盘格式（债务 13 消化）；③ `build` / `load_index` 返回 **`BuiltIndex` 容器**（bm25 / store / id_to_chunk / dim / failures），search 的四个散参数从此有唯一打包
- **实现内容**（用户写核心编排，Agent 写脚手架与测试）：
  - `index/assets.py`：`BuiltIndex` dataclass
  - `index/chunks_store.py`：`write_chunks` / `read_chunks`（tmp + os.replace 原子替换；坏行 `ValueError` 带路径与行号）
  - `index/builder.py`：`build(root, cfg)`（load_dir → chunk → embed → stores.write → write_chunks → BM25Index，坏文件进 failures、空语料是合法产物）、`load_index(index_dir)`（stores.load → read_chunks → **id 一致性硬校验** → BM25 重建）
  - 测试：`test_index_build.py`（7 条）、`test_index_load.py`（5 条）
- **测试数量与结果**：新增 12 条，累计 225 条，全部通过（`pytest -q` → 225 passed）
- **遇到的问题**（验收时发现）：
  1. `load_index` 里 id 一致性校验**重复出现两遍**——第二遍是英文消息的复制粘贴残留（功能无害，第二遍必然同样结果）
  2. 三处**借道导入**：`loaders.directory`、`chunking.document`、`stores.vector_store` 直达子模块，绕过包 `__init__` 的公开面
- **问题根因**：
  1. 复制粘贴后忘记删除旧段——与第 2 轮 `test_citation_roundtrip`（复制测试只改名没改字段）同款坑
  2. 直接 import 子模块路径会架空"公开 API"的约定；债务表 4（`chunking/__init__.py` 借道导入）早有此类记录
- **学到的通用知识**：
  - **建库层是"组装线"不是"零件"**：它是唯一把五层串起来的地方；`id_to_chunk` 从此落盘（chunks.jsonl），进程重启不再丢
  - **可再生的数据，重建优于新增落盘格式**（呼应事故记录"重建优于修补"）：BM25 统计可从 chunks + tokenize 推导，就不再造一个统计格式
  - **"谁负责建目录"是隐含依赖**：`stores.write` 会 `makedirs`，`write_chunks` 直接 `open` 不会建——所以 `write` 必须先调；这种依赖要显式注释
  - **硬不变式校验是"非整体原子"的兜底闸**：`load_index` 的 id 集合一致性校验，正好拦住"write 与 write_chunks 之间的半成品索引"（债务 12 的缓解）
  - **空语料是合法产物**：空 store + 空 chunks.jsonl + 空 BM25Index，不报错——"空"是数据事实，不是程序错误（与第 8 轮空文本返回 [] 同一判据）
- **尚未解决的技术债**：增量更新（扩展：全量重建实测慢到痛时回来做）；五文件整体原子性（触发信号：建库中途崩溃实际发生过）；`RetrievalResult` 仍无生产消费者——第一个真实消费者是阶段 9 生成层（`Answer.contexts` / `citations` / `trace` 早已按它的形状设计好）
- **下一阶段入口条件**：225 条测试通过 + 阶段 9（生成层）启动；或增量触发信号出现时回补阶段 8 增量

---

## 第 15 轮：生成层（`generation/`）

- **完成日期**：2026-10-16
- **拍板的决策**：① `provider="none"` **抽取式回答**（`answer` = top1 块原文；不拒答、不占位符）；② `confidence` = `results[0].score` **搬运**（不发明新评分）；③ 拒答判据**只认 `results` 为空**（分数阈值挂扩展，需要评测数据标定）
- **实现内容**（用户写组装核心，Agent 验收修约 + 补测试）：
  - `generation/answer.py`：`answer_question(question, result, *, llm)`——证据→引用（编号从 1 起、顺序同 results）、拒答判定、抽取式回答、`trace` 原样挂载（拒答也挂）、`openai_compatible` fail-fast 抛 `NotImplementedError`
  - `build → search → answer_question` **全链路可跑**；`RetrievalResult` 的第一个生产消费者就位（`Answer.contexts` / `citations` / `trace` 三个第 3 轮就设计好的字段首次被真实填充）
  - 测试：`test_generation.py`（6 条，含端到端与拒答链路）
- **测试数量与结果**：新增 6 条，累计 231 条，全部通过
- **流程偏差记录**：第 14 轮漏执行「环节 6 架构问题」（拆完实现步骤直接进实现）；第 15 轮补上。"问 → 答 → 纠正"是唯一能暴露理解断层的环节，跳过等于放弃检查——本轮它果然拦下了断层（见下）。
- **架构问题三题：断层与纠正**（先答后纠）：
  1. （契约）答"trace=None 只是文字没有约束力"——**两处都错**：docstring 是契约的声明文本、测试是执行法院（不是没有约束力）；且那条约定定义的是 **None 值的语义**（"没有检索轨迹时填 None"），不是"拒答必须 None"——拒答时检索确实发生了，挂 trace 恰恰是**遵守**本义
  2. （失败）答"东西太多，忘了 contexts 和 citations 是什么"——复习后记住：**contexts 给机器**（将来喂 LLM 的纯文本）、**citations 给人**（溯源的结构化引用）；值相同是抽取式的巧合，接真 LLM 后 `answer` 变生成文本、两者立刻分开；**字段语义由消费者定义，不由当前值是否相同决定**
  3. （演化）答"不知道为何传整个 LLMConfig"——记住：将来接 LLM 需要 `model`/`api_key`/`base_url`（全在配置对象里）；**配置对象加字段不破坏签名**（第 1 轮验证过），散参数加一个就是破坏性变更；"配置对象进、领域对象出"是项目一贯模式（`search` 收 `RetrievalConfig`、`build` 收 `AppConfig`）
- **遇到的问题**（验收时发现）：
  1. **误导入**：`from tkinter import N`、`from numpy import r_`——IDE 自动补全对短前缀（`N`、`r_`）极敏感，回车即导入 GUI 库常量与 numpy 索引对象
  2. **`trace=None`（两处）**：问题 1 的断层**原样长进了代码**——拒答与正常分支都写成 None，丢掉"为什么拒"的诊断能力
  3. **`confidence=1.0` 硬编码**：违背决策 2，应搬运 `results[0].score`
  4. `NotImplementedError` 无消息；注释把抽取式说成"占位的 Answer"（它不是占位，是拍板行为）
- **问题根因**：
  1. import 区不逐行过目，自动补全的误导入就溜进去了
  2~3. **契约刚拍板、断层未消除时就写代码，断层会原样长进代码里**——这正是「先答后纠」环节存在的根本理由，本轮问题 2 就是活例
- **学到的通用知识**：
  - **配置是人的意图，违背意图的静默降级是最贵的失败**：`openai_compatible` 是合法配置但未实现 → 当场 `NotImplementedError`，绝不静默走抽取式（第 4 轮 `extra="forbid"` 同款判据）；`ValueError` 说"你的值不合法"、`NotImplementedError` 说"值合法但行为未到"，责任归属不同
  - **读约定要分清"值语义"和"强制规则"**："trace=None 表示没有轨迹"定义 None 的含义，不等于"拒答必须抹掉轨迹"
  - **看似冗余的字段，往往是两个消费者各需要一份**（contexts 给 LLM、citations 给人）
  - **签名对未来封闭、行为在内部开放**：传整个配置对象，将来扩展只动函数内部分支体（把 `raise` 换成真实调用），调用点零改动
- **尚未解决的技术债**：`openai_compatible` 真实生成（扩展：拿到密钥 + 网络可用时）；拒答分数阈值（评测数据标定后）；snippet / answer 截断（真实语料超长时）
- **下一阶段入口条件**：231 条测试通过 + 阶段 10（CLI / API）启动

---

## 第 16 轮：CLI（`ragkit build` / `ragkit ask`）

- **完成日期**：2026-10-16
- **拍板的决策**：① 拒答退出码 = **0**（拒答是业务正常结果，不是程序错误；shell 脚本不该把"没查到"当崩溃）；② build 语料目录默认 `cfg.data_dir`、`--root` 显式覆盖（配置给默认、参数给覆盖，与 `load_config` 优先级体系同构）；③ jieba 噪声在 **`text/tokenize` 源头层**治理（所有入口一次受益）——债务表 9 的触发信号"做 CLI 时"已到，本轮消化一半（噪声消除；P95 冷/热污染留阶段 14）
- **分工调整（记入协议执行记录）**：CLI 全程是壳、无核心算法——协议"用户写核心算法"在**无算法可写的轮次**不适用，参照第 0 课先例由 Agent 写全部实现 + 测试，用户验收 + 答架构问题
- **实现内容**：
  - `cli.py`：`main(argv, environ=None) -> int`（environ 参数化 = 第 5 轮"参数可注入 = 测试可隔离"在 CLI 的延续，向后兼容）；`build` / `ask` 子命令；**领域层延迟 import**（`--version` / `--help` 秒回，不触发 jieba / numpy 加载）
  - `text/tokenize.py`：模块加载时 `jieba.setLogLevel(WARNING)`（实测子进程 stderr 完全干净）
  - 测试：`test_cli.py`（8 条：build 统计与坏文件、ask 回答与引用、拒答=0、索引缺失提示、配置/语料错误=1、环境隔离、降噪断言）
- **测试数量与结果**：新增 8 条，累计 239 条，全部通过；真实 CLI 手测符合预期（乱码仅为控制台 GBK 显示）
- **遇到的问题**（写测试前自查发现）：
  1. `stores.load` 对"**索引目录整体不存在**"抛的是 `StoreCorruptError`（manifest 打不开被包装成损坏），不是 `FileNotFoundError`——CLI 的错误分支与提示语必须与之对应：`FileNotFoundError` 只对应 chunks.jsonl 缺失的**半成品**，`StoreCorruptError`（⊂ `RagkitError`）对应"不存在或损坏"，提示"先运行 ragkit build"
- **架构问题三题：断层与纠正**（先答后纠，2026-10-16）：
  1. （边界）答"没输入时可以用默认值，直接读会炸"——**事实错误**：`sys.argv` / `os.environ` 永远存在，不存在"没输入"的场景。真正的问题是**测试时它们不是你的**（pytest 下 argv 是 pytest 的参数、environ 是真实环境，可能残留用户设过的 `RAG__*` 变量）。模式名：**参数可注入 = 测试可隔离**（第 5 轮原话），判据：**污染真实环境后照旧全绿**。三次出现：第 0 课 `main(argv)` → 第 5 轮 `load_config(environ)` → 本轮 `main(environ)`
  2. （失败）答"用户看不懂"——方向对但只是四分之一，补全**三类读者**：用户要**行动指引**（"请先运行 ragkit build"，堆栈给不出下一步）；开发者要堆栈（**没丢**——绕过 CLI 直接调 Python，`raise ... from` 异常链一直保留）；shell 脚本要**退出码**（堆栈是噪声）。分层：领域异常机器可分类 → **每个表现层各自翻译**（CLI=文本+退出码；API=状态码+JSON 错误体）
  3. （演化）答"完全不会"——记结论：CLI 的格式化 API **不能也不需要**复用；两者共享的不是格式化函数，是 **`Answer` 结构化契约**。原则：**领域层输出结构化对象，表现层各自翻译**。防的坏诱惑：把格式化下沉进领域层（generation 返回格式化字符串）——评测要 recall@k、API 要字段、消融要分数，全被锁死在一种格式上。"第三处格式化"= 阶段 13~14 评测报告（指标→表格），同款翻译。**看似重复的格式化，是两个消费者各需要一份**（第 15 轮 contexts/citations 判据在表现层的再现）
- **学到的通用知识**：
  - **CLI 薄壳三件事**：解析参数、调领域函数、格式化输出；零业务判断（阈值、排序、过滤都不进 CLI）——判断标准：cli.py 里不该 import numpy / jieba
  - **退出码语义是契约**：0 = 成功（含拒答）、1 = 运行错误、2 = 用法错误（argparse 自带）——拒答是检索的正常业务结果，把它当错误会让调用方脚本误判崩溃
  - **异常分支要对着领域层的真实行为写**：想当然认为"目录不存在 → FileNotFoundError"，实际 stores.load 的契约是"manifest 缺失即损坏"——先读契约再写 except 分支
  - **噪声源头治理优于逐入口治理**：所有入口都经过分词层，在那里一次 `setLogLevel`，CLI / API / 评测全部受益
- **尚未解决的技术债**：jieba 首次加载约 1.8 秒仍在（P95 冷/热区分留阶段 14 评测）；`--json` 机器可读输出、交互式 REPL 挂扩展（触发信号见 PROJECT_LAYOUT）
- **下一阶段入口条件**：239 条测试通过 + 阶段 11（API + 日志方案）启动

---

## 第 17 轮：HTTP API + 请求日志（`api/`）

- **完成日期**：2026-10-16
- **拍板的决策**：① **标准库 `http.server`**（零新依赖、"离线可运行"贯彻到底、单端点手搓 <150 行学 HTTP 翻译层的本质；FastAPI 迁移挂扩展）；② 端点 `POST /ask {"query"}`，**拒答也是 200**（`refused: true` 表达，与 CLI 拒答=退出码 0 同语义）；③ **启动时索引常驻**、变更需重启（热更新挂扩展）
- **分工**：同第 16 轮先例（壳轮次，无核心算法），Agent 写全部实现与测试
- **实现内容**：
  - `api/server.py`：**壳芯分离**——`_answer_payload`（search → answer_question → `to_dict()`）纯函数芯，handler 只做 HTTP 细节；错误翻译表（400/404/405/500，500 不泄堆栈）；每请求一行结构化日志
  - `cli.py`：`ragkit serve [--host] [--port]` 子命令——启动加载索引、`Ctrl+C` 退出码 0；**库只 getLogger、应用侧（serve）才 basicConfig**（日志格式归调用方，库不越界）
  - 测试：`test_api.py`（12 条，**真服务器集成**：ThreadingHTTPServer 起线程 + urllib 打真请求，port=0 随机分配）；`test_cli.py` 补 serve 无索引分支（9 条）
- **测试数量与结果**：新增 13 条，累计 252 条，全部通过
- **遇到的问题**（自查发现）：
  1. `do_POST` 的日志引用 `raw` 变量时先写了 `len(raw) if "raw" in dir() else 0`——`dir()` 检查局部变量不可靠且丑；改为**提前初始化 `raw = b""`**
  2. 更新文档测试表时 `test_cli.py` 行**重复插入**（搜索确认后删旧行）——清单操作再次证明"清单是示例"
- **学到的通用知识**：
  - **壳芯分离**：HTTP 处理逻辑抽成纯函数可直调单测；handler 依赖 socket/线程，测它要先构造一堆东西——**把可测的抽出来，把不好测的做薄**
  - **库只 getLogger、应用才 basicConfig**——库配置日志格式会越界剥夺调用方的自由（同"归一化归 embeddings 层"的责任归属判据：谁的事谁做）
  - **索引常驻是 API 相对 CLI 的本质优势**：CLI 每个 ask 付 ~1.8s 冷启动，API 只付一次（第 16 轮 REPL 扩展的触发信号在 API 天然解决）
  - **真服务器集成测试用 port=0**：系统随机分配端口，测试之间互不冲突、不碰真实端口
- **架构问题三题：断层与纠正**（先答后纠，2026-10-17）：
  1. （契约）答"这是约定，网页都这样"——**约定不是理由，要说出机制**：404 是**资源层**失败（端点/路径不存在），拒答是**业务层**成功（资源在、请求合法、处理完成、结果=没查到）。拒答用 404 会造成**语义污染**（同一个码既可能"路由错"又可能"没答案"，监控无法分类）；`refused` 作为结果字段让机器精确分类。HTTP 状态码描述传输层，`refused` 描述业务结果——正交两层，与 CLI 拒答=退出码 0 同判据
  2. （失败）答"do_POST 报错、_answer_payload 回答，功能不同"——**按功能分组是表象，动因是可测试性**：`_answer_payload` 零环境依赖可直调单测；do_POST 里的逻辑要测必须先构造 socket 三件套 + mock rfile/wfile。拆分判据：**依赖少的抽出来直测，依赖 socket 的做薄到不值得测逻辑**（只跑集成）——可测性驱动的结构，与第 0 课"参数可注入"同一原则
  3. （演化）答"HTTP 吧，不清楚"——**错，走领域层直调**：评测要 recall@k 的精确 chunk_id 对齐 + 排名 + 各腿分数，`/ask` 返回的 Answer 只有 citations，**没有 chunk_id / score / 各腿候选**（翻译中丢了中间产物）。评测的对象是**检索算法**不是 HTTP 翻译层；HTTP 正确性已由 test_api 集成测试锁住。分层延续：评测脚本是又一个消费者，消费 `RetrievalResult`，API 消费 `Answer`——各消费各的层，共享"领域层输出结构化对象"
- **尚未解决的技术债**：ThreadingHTTPServer 并发未压测（触发信号：实测撑不住）；无鉴权（公网暴露前必加）；索引热更新、FastAPI 迁移挂扩展
- **下一阶段入口条件**：252 条测试通过 + 阶段 12~13（评测集与指标）启动

---

## 第 18 轮：评测集与指标（`evaluation/`）

- **完成日期**：2026-10-17
- **拍板的决策**：① **手写评测集**（12 条 query，可控可复现，规模够消融的"相对退化"对比）；② **文档级评测单元**（`doc_id` 标注，`chunk_id` 是派生量随 chunk_size 失效）；③ 我生成 10 篇示例中文技术文档作语料
- **分工**：**恢复"用户写核心"**——`metrics.py`（`recall_at_k` / `mrr` 纯函数，有手算要求）由用户写；`qrels.py` / `report.py` / 语料 / 评测集 / 测试由 Agent 写
- **实现内容**：
  - `evaluation/metrics.py`：`recall_at_k` / `mrr`
  - `evaluation/qrels.py`：`Qrel`（frozen，relevant 为 frozenset）/ `load_qrels`（校验）
  - `evaluation/report.py`：`evaluate` + `_dedup_doc_ids`（一个文档多块只算一次）+ `LatencyStats`（冷/热耗时表）
  - `data/raw/`（10 篇语料）+ `data/eval/qrels.json`（12 条评测集）
  - 测试：`test_metrics.py`（8）、`test_evaluation.py`（3）
- **测试数量与结果**：新增 11 条，累计 263 条，全部通过；真实评测基线：recall@1=0.917、recall@3=1.0、MRR=0.958、热检索 P50≈1.5ms
- **遇到的问题**（验收时发现）：
  1. `metrics.py` 的 `k<=0` 校验放在 `relevant` 空判断**之后**——`recall_at_k([], set(), 0)` 会返回 0.0 而非 `ValueError`。参数非法是调用方 bug，必须无条件先报（"参数校验最先"），已改到最前
  2. 耗时表"冷启动"语义偏差：实测发现 `evaluate` 的"首查冷启动"只有 4ms——因为 `built` 在 build 时已加载 jieba，真正的 1.8s 冷启动在 build/load_index 层，不属检索耗时。已修正注释与契约（"冷启动"= 进程内首查；jieba 冷启动归建库层）
  3. 补 `ragkit eval` 时实测 recall **全 0**，而 `demo_evaluate.py` 是 0.917——根因是 `data_dir` 默认值 `Path("data")` 指向**数据根**，`ragkit build` 索引后 doc_id 带上 `raw/` 前缀（`raw/容器冷启动优化.md`），与评测集标注（`容器冷启动优化.md`）对不上；demo 显式 `build(data/raw)` 规避了这个坑。修复：默认值改 `Path("data/raw")`、docstring 澄清为"原始语料目录"
- **架构问题三题：断层与纠正**（先答后纠，2026-10-17）：
  1. （契约）答"文档 id 需去重"——**偏了**：那是 retrieved 侧的去重，不是 `relevant` 用 set 的理由。set 的理由是**"相关"是无序的成员关系**（0/1 相关，不分等级），set 向调用方承诺"无顺序、无重复"，list 会误导"有序/可重复"；去重只是附带效果。**数据结构第一要义是表达语义，其次才是效率**
  2. （边界）答"命中/总相关数、relevant 空返回 0.0"——对但没触及题眼：relevant 空返回 0.0 而非"跳过"，是因为**数据缺陷要大声暴露**（拉低平均引起注意），静默跳过会掩盖"标注缺失"；且 load_qrels 已拦、函数内是防御兜底
  3. （演化）答"不去重会被某一篇文章干扰"——对但答的是"为什么要去重"（evaluate 职责），不是"为什么收 id 序列"。收 `list[str]` 的理由是**最小依赖**：指标不关心 ScoredChunk 的 score/stage/trace，只认有序序列 → 可直测、可复用（换 chunk 级评测/换检索实现都不改指标函数）
- **学到的通用知识**：
  - **set 表达无序成员关系，list 暗示有序可重复**——选数据结构先看它向调用方承诺了什么语义
  - **参数校验最先（fail-fast），数据事实之后**——k<=0 是调用方 bug 必须无条件报，relevant 空是数据事实之后处理
  - **指标函数收"id 序列"不收领域对象**——最小依赖换来可测性 + 可复用性（与第 16 轮"参数可注入"、第 17 轮"壳芯分离"同一原则的不同侧面）
  - **冷启动归属要分清**：jieba ~1.8s 属建库层（build/load_index），检索各阶段的热耗时才进评测耗时表
  - **相对路径的基准（root）是契约的一部分**：doc_id 是相对 build root 的 POSIX 路径（第 7 轮定的"source 相对 root"），root 一变 doc_id 全变、评测标注与索引对不上——`data_dir` 必须指向语料目录本身，不是它的父目录
- **尚未解决的技术债**：nDCG（分级相关度）、统计显著性检验（配对 t 检验）、自动调参网格搜索——均挂扩展（触发信号见 PROJECT_LAYOUT）
- **下一阶段入口条件**：263 条测试通过 + 阶段 13~14（消融实验：关腿对比，用同一套 qrels）启动

---

## 第 19 轮：消融实验（`evaluation/ablation.py`）

- **完成日期**：2026-10-17
- **拍板的决策**：① 4 组单变量对照（baseline / 只 BM25 / 只 dense / 关 rerank，单腿组同时关 rerank 隔离变量）；② 打印 + 落盘 `reports/ablation.json`；③ **结果解读交用户**（协议"每轮复盘必须用户自己答"）
- **数据扩充（用户要求，两次加码）**：语料最终 **100 篇**（20 正 + 80 误导，`scripts/generate_corpus.py` 程序化生成）、评测集 **300 条** query；recall@k 默认改 **1~10 全量**
- **实现内容**：`evaluation/ablation.py`（`run_ablation` + `VARIANTS` 契约）、`test_ablation.py`（2 条）、`demo_ablation.py`、`scripts/corpus_data.py` + `scripts/generate_corpus.py`（语料/评测集生成）
- **测试数量与结果**：新增 2 条，累计 267 条，全部通过
- **消融结果**（100 条评测集）：

| 组 | recall@1 | MRR |
|---|---|---|
| baseline（全开） | 0.833 | 0.899 |
| **bm25_only** | **0.910** | **0.950** |
| dense_only | 0.833 | 0.899 |
| **no_rerank** | **0.910** | **0.948** |

  边际贡献（手写自然语言 query，300 条 0 重复）：dense 腿 **−0.08**、rerank **−0.08**，**纯 BM25 与 no_rerank 打平最优（0.910）**；`baseline == dense_only` 再次印证 rerank 用 dense 一票否决

- **query 从模板合成改为手写（用户指出的关键缺陷）**：
  1. 旧版 query 用"概念词 × 3 个问句模板"生成（如"冷启动是什么"），与文档词汇高度重叠，等于让检索器做字面填空，指标虚高且不能迁移到真实场景
  2. 改进：300 条 query 全部手写成自然语言（每主题 15 条，措辞多样、带场景、刻意不照搬概念词），0 重复
  3. 结果：手写 query 让 dense 的负贡献从 −0.02 回升到 −0.08——**模板合成 query 会高估 dense（词汇重叠高），手写自然 query 才暴露 dense 字面级的真实弱点**；BM25 的词项匹配（罕见词 idf）在任何 query 形式下都稳定
  4. 教训：**评测集必须用接近真实提问的自然语言，合成 query 测不出真实检索能力**——这是评测数据质量的核心，比规模更重要
- **遇到的问题**（程序化生成时发现）：
  1. distractor 标题与 core 标题**重复**（如"限流与熔断"既是主题 8 的正文档、又是别的主题的误导文档）→ 生成脚本按标题写文件，误导模板**覆盖了正文档**，语料从 100 篇骤减到 43 篇。修复：把所有 distractor 改成**全局唯一**标题（避开 20 个 core，80 个 distractor 互不重复）——**程序化批量生成数据时，标识符唯一性必须先于生成校验**
- **关键转折**：12 条时（无误导）所有组 0.917~1.0（**天花板效应**，组件贡献显示 0）；扩到 100 篇语料（含 80 误导）+ 300 条 query 后，dense/rerank 的负贡献才现形——**评测集太简单会让消融失效**
- **解读三题的断层与纠正**（先答后纠）：
  1. 答"因为有误导语料"——只答了导火索，没答根因：hashing 字面级、不懂语义、不区分词重要性；误导语料只是把弱点放大
  2. 答"误导文档对向量影响更大"——直觉对，机制是：误导与正文档共享高频词，hashing 里高频词与罕见词**等权**，BM25 的 idf 压低高频词、抬高罕见词
  3. 答"都不该关，都有应用场景"——**没读数据**：当前 hashing 实现下 dense/rerank 是负资产、纯 BM25 最优；混淆了"概念价值"（真 embedding 的 dense 有用）与"当前实现价值"（hashing dense 是负资产）。落点：当前默认关 dense+rerank，换真模型再评估再开
- **学到的通用知识**：
  - **消融是"避免过度设计"的裁判**：第 4 轮说"不能按未来会不会用到判断"，现在有了量化手段——dense 腿和 rerank 是"无数据证明先建"的典型，消融证明它们是负资产
  - **评测集的天花板效应**：太简单的评测集测不出组件差异（所有组满分），加误导文档 + 扩样本才能让"相对退化"现形
  - **hashing 字面级的边界兑现**：它把高频词当相似信号，在主题相邻的语料上分不清——第 9 轮"字面级替身"的定位，现在兑现成数据（负贡献）
- **尚未解决的技术债**：换真 embedding（openai/bge）后重估 dense 腿与 rerank；统计显著性检验（100 条结论未做检验）
- **下一阶段入口条件**：267 条测试通过 + 阶段 14~15（交付：README / 打包 / 总结报告）

---

## 第 20 轮：落地消融结论（rerank 默认关）

- **完成日期**：2026-10-17
- **拍板的决策**：① `rerank_enabled` 默认值 `True → False`（数据证明 dense 余弦精排稳定负贡献，默认跑着已知更差的配置是错的）；② **不实现 weighted fusion**（α 最优值依赖数据集：data 上 0.78、data2 上 1.0，没有普适的 α，实现它是过度设计）；③ 保留 data2 作为第二套评测集（证明结论跨领域稳定）
- **改动**：
  - `config.py` + `default.yaml`：`rerank_enabled` 默认 `False`
  - 测试更新：6 个依赖旧默认的测试显式传 `rerank_enabled=True`（它们测的是"rerank 开启时"的契约）；新增 `test_rerank_disabled_by_default` 锁定新默认
  - 测试数量：268 passed（+1）
- **遇到的问题**：改默认值后全量测试两度在 `test_api.py` 偶发失败（一次 `test_request_logged` 的 caplog 捕获、一次 `test_wrong_method_returns_405` 的 `ConnectionAbortedError`），但**单独跑 test_api.py 12 条稳定通过**——这是线程服务器 + urllib 的时序 flaky，与本次改动无关（两次失败的是不同测试，且错误类型不同）
- **学到的通用知识**：
  - **默认配置要和数据结论一致**：消融证明 rerank 负贡献后，还让默认值开着，等于"交付一个已知更差的默认行为"——默认值是契约的一部分，必须反映最优选择
  - **测试锁的是契约，默认值变了测试要跟着变**：6 个测试失败不是测试错了，是它们锁的"默认 rerank 开"这个旧契约被我们改了——显式传参区分"测 rerank 功能"和"测默认行为"
  - **"α 依赖数据集"意味着不该写成固定配置**：一个换了数据集就要重新调参的机制，做成代码是过度设计——这正是第 4 轮判据"不能按未来会不会用到判断"的又一实例
- **尚未解决的技术债**：换真 embedding 后重估 dense 腿与 rerank；统计显著性检验；README 收尾、打包、总结报告（阶段 14 剩余）
- **下一阶段入口条件**：268 条测试通过 + 阶段 14 剩余（README / 打包）+ 阶段 15（总结报告）

---

## 第 21 轮：交付——README 收尾 + 打包（版本 1.0.0）

- **完成日期**：2026-10-17
- **实现内容**（Agent 写，交付轮次无核心算法）：
  - `README.md` **整体重写**：从第 0 课骨架（还写着"当前版本不能问答"）更新为完整现状——四命令详解（build/ask/serve/eval + 退出码约定）、架构分层、评测与消融结论、两套评测语料（data 后端 / data2 ML）、扩展路线图
  - `pyproject.toml`：版本 `0.0.1 → 1.0.0`、`description` 更新、加 `readme = "README.md"`（打包时包含 README）
  - `src/ragkit/__init__.py`：`__version__ = "1.0.0"`
- **测试数量与结果**：268 条，全部通过；`--version` 输出 `ragkit 1.0.0`
- **遇到的问题**（环境层面，非代码）：
  1. `pip install -e ".[dev]"` 报 `Failed to build ... when installing build dependencies`——**离线环境**下 pip 隔离构建要联网下载 setuptools（SSL 失败），装不了
  2. `--no-build-isolation` 报 `Cannot import setuptools.build_meta`——venv 里**根本没有 setuptools**（之前一直用隔离构建，setuptools 只进临时隔离环境、不装进 venv）
  3. 后果：`pip list` 显示旧元数据 `ragkit 0.0.1`，而 `--version` 输出 `1.0.0`（editable 安装读源码，版本号直接生效）——元数据与源码版本**不一致**
- **问题根因与判断**：不一致的根源是**离线 + editable 安装**：editable 安装只写路径映射，`__init__.py` 改了版本号立即生效（`--version` 正确），但 pip 的 dist-info 元数据要重新 `pip install` 才刷新，而重新 install 又卡在"离线装不了 setuptools"。**不影响功能**（import / --version / 测试全对），联网后 `pip install -e` 一次即恢复
- **学到的通用知识**：
  - **editable 安装的两套版本号**：`--version` 读源码 `__version__`（改即生效），`pip list` 读 dist-info 元数据（要重装才刷新）——升版本后离线环境会短暂不一致，但无害
  - **离线环境 pip install 的三层陷阱**：默认隔离构建要联网下载 build 依赖 → `--no-build-isolation` 要 venv 里有 setuptools → venv 里没有（因为从来都是隔离构建）。离线交付时 README 的安装步骤要注明"需联网装 build 依赖，或预装 setuptools"
  - **README 是交付的"门面"，不是后补**：第 0 课写完就再没更新，到交付时已严重失真（还写着"不能问答"）——文档和代码一样有"腐化"问题，应随里程碑同步更新
- **尚未解决的技术债**：`pip install` 离线不可用（联网后刷新元数据即可）；阶段 15 总结报告
- **下一阶段入口条件**：268 条测试通过 + 阶段 15（总结报告）启动

---

## 第 22 轮：总结报告（`SUMMARY.md`）——主线收官

- **完成日期**：2026-10-17
- **实现内容**（Agent 写，收官轮次）：
  - `SUMMARY.md`：全项目总结报告——项目定位、九层架构全景、核心指标与消融结论、关键设计决策、踩坑规律、技术债与演进方向
  - **顺带修正 README 数据错误**：上一轮写 README 时消融表误用了过时的模板 query 数据（0.687/0.710），应改为手写 query 的最新数据（0.833/0.910，边际贡献 dense −0.08 / rerank −0.08）
- **测试数量与结果**：268 条，全部通过（本轮无代码改动，仅文档）
- **遇到的问题**：写 README 时消融表用了旧数据（模板 query 的 0.687 而非手写 query 的 0.833）——**交付文档里的数字必须逐项核对最新实测**，记忆里的"上一次的数字"可能是过时版本
- **学到的通用知识**：
  - **交付文档的数据要追溯来源**：README/SUMMARY 里的指标，必须来自最近一次实测（手写 query 后重跑的那次），而不是记忆里更早的某次；数据有过多次迭代（12 条→100 条模板→300 条手写），每次都在变
  - **总结报告是"提炼"不是"罗列"**：从 PROJECT_LAYOUT（契约详尽）与 LEARNING_LOG（逐轮流水账）里提炼出"架构全景 + 硬结论 + 规律 + 演进方向"，让读者五分钟看懂项目价值，而不是翻遍两份文档
- **尚未解决的技术债**：真 embedding / cross-encoder / openai_compatible / 增量更新 / HTML-PDF / FastAPI 迁移 / 鉴权——全部挂触发信号，见 SUMMARY 与 PROJECT_LAYOUT
- **收官状态**：主线阶段 0~15 全部完成；扩展项按触发信号随时插入

---

## 第 23 轮：加权排名融合落地（`weighted_fuse`）

- **完成日期**：2026-10-17
- **需求**：把默认融合从 RRF 等权改为**加权排名融合** S(d) = α·S1(d) + (1-α)·S2(d)，α 默认 0.9；不接真 embedding
- **实现内容**（Agent 写，无核心算法争议）：
  - `fusion.py`：新增 `weighted_fuse(results, *, alpha, k, top_k)`——第一腿（BM25）权重 α、第二腿（dense）权重 1-α；单腿退化（权重归一化为 1）；>2 腿退化为等权
  - `config.py`：`fusion` 默认 `"rrf" → "weighted"`、新增 `fusion_alpha=0.9`（`ge=0, le=1`）
  - `pipeline.py`：融合阶段按 `retrieval.fusion` 选 `rrf_fuse` 或 `weighted_fuse`
  - `default.yaml`：`fusion: weighted` + `fusion_alpha: 0.9`
  - `__init__.py` 导出 `weighted_fuse`；`test_fusion.py` 补 4 条加权契约、`test_config.py` 更新默认值断言
- **测试数量与结果**：新增 4 条，累计 272 条，全部通过
- **实测**：weighted α=0.9 → recall@1=0.903、MRR=0.945（此前 baseline 全开 RRF+rerank 是 0.833；纯 BM25 是 0.910）
- **关键判断**：α=0.9 的 recall@1=0.903 **精确复现了此前 α 扫描里 α=0.9 的结果（0.903）**——印证加权融合实现正确。但 0.903 并非 data 上的最优点（最优 α≈0.78~0.80 得 0.923，纯 BM25 得 0.913）；α=0.9 是**保守安全值**（两个数据集都接近最优、偏 BM25），dense 的 0.1 权重引入了它少量负贡献，故略低于纯 BM25
- **学到的通用知识**：
  - **加权融合是"给 BM25 的 idf 优势让路、只给 dense 留一个边角"**：α=0.9 把 hashing dense 压到 0.1 权重，既保留它那点互补价值、又不让它主导——这是消融"dense 负贡献"结论在融合权重上的落地
  - **落地一个"依赖数据集的参数"要选保守值**：α 最优值随语料漂移（data 0.78 / data2 1.0），默认 0.9 不是任何数据集的最优，但处处接近最优、且偏稳——比"写死最优值"更经得起换语料
- **尚未解决的技术债**：真 embedding / cross-encoder / openai_compatible / 增量更新 / HTML-PDF / FastAPI 迁移 / 鉴权——挂触发信号（用户明确暂不接真 embedding）
- **下一阶段入口条件**：扩展项按触发信号随时插入

---

## 第 24 轮：语料重建 + 块级标注 + heading 再切

- **完成日期**：2026-10-21
- **需求（用户四条指令）**：① 删除两次实验（`data`/`data2`）及中间文件；② 重写语料，正/误导文档长度相当、每篇 10000 字；③ 评测改**块级标注**（标出答案 `##` 小节）；④ 加入改写类 query（不照搬概念词）与无答案 query（测拒答）
- **实现内容**（Agent 写）：
  - 删除 `data`、`data2`、`reports`、旧生成脚本；`heading.py` 实现按 `##` 切分，超长小节（>400 字）用 `fixed`（chunk_size=300）再切，拆出 `iter_heading_sections`（原始小节区间）/ `iter_heading_spans`（再切后块区间）
  - `chunk_size` 默认 400 → 300（`document.py` + `config.py` + `default.yaml` + 3 处测试断言）
  - 评测块级化：`qrels.py` 的 `relevant` 改 chunk_id + 允许空列表；`report.py` 提取 chunk_id（不再按 doc_id 去重）
  - 语料 10 篇（2 主题 × 1 正 + 4 误导），每篇约 10000 字、`##` 小节长度起伏（短 ~100 / 长 ~1300）；25 条 query（direct 10 / paraphrase 9 / no_answer 6）
  - 生成脚本 `corpus_data_01/02.py` + `generate_corpus.py`：块级标注 = 答案小节的全部块
- **测试数量与结果**：272 条，全部通过
- **遇到的问题（关键 bug）**：heading 再切后，`generate_corpus.py` 仍假设「每个 `##` 小节 = 一个 chunk，块索引 = 小节序号」，用 `core_ids[answer_section]` 取答案块——超长小节被再切后块数 > 小节数，索引全错位，recall@1 从 0.36 崩到 0.16。**修复**：改用 `iter_heading_sections` 拿到原始小节区间，按 `char_start` 把 chunk 归到所属小节，`relevant` = 答案小节的全部块
- **实测**：块级标注下 recall@1=0.25、MRR=0.457；消融 `baseline == dense_only`（rerank 用 dense 余弦一票否决，规律跨语料稳定），no_rerank（等权 RRF）MRR 最高 0.477
- **学到的通用知识**：
  - **标注粒度决定任务难度**：文档级标注测"在 N 篇里选对主题"（易，0.9），块级标注测"在 M 块里精确命中答案小节"（难，0.25）——跨粒度比较绝对数字没有意义，粒度升级本身就是让检索任务更真实
  - **隐式假设要随分块逻辑显式校验**：「小节序号 = 块索引」在"每个小节一个块"时成立，一旦引入"超长小节再切"，这个假设就静默失效——程序化生成 + 标注时，标识符/索引的对应关系必须先于生成校验（呼应第 19 轮的"标识符唯一性先校验"）
  - **块级标注下答案是一对多**：超长小节被切成多块，`relevant` 要覆盖全部块，评测语义是"命中答案小节的块比例"而不是"命中唯一块"
- **尚未解决的技术债**：真 embedding / cross-encoder / openai_compatible / 增量更新 / HTML-PDF / FastAPI 迁移 / 鉴权；块级评测的统计显著性（25 条 query 样本太小）
- **下一阶段入口条件**：扩展项按触发信号随时插入

---

## 贯穿各轮的通用规律（每条都至少撞过一次）

1. **改名是多点同步**——改完必须全局搜索旧名，确认 0 命中（已撞 3 次：`cli.py`、`test_schemas.py`、`retrieved_traces`）
2. **可变默认值只用 `default_factory`**——dict 与 list 各撞一次
3. **roundtrip 只验对称性**——契约靠键集合，类型靠 `isinstance`，值靠独立期望值
4. **可选性只有一个真相来源**——字段有没有默认值；`_require_fields` 必须与它一致
5. **`in` / `is None` / 真值判断是三件事**——`.get(k, d)` 挡不住 `None`，`if x` 挡不住空 `{}`
6. **不可见字符靠工具判断，不靠眼睛**——空格 vs 制表符、CRLF vs LF、全角 vs 半角，一律用 `repr()` 或"显示空白字符"确认；对照实验的结论不能当成被测文件的证据
7. **清单是示例，不是完整清单**——大面积、可再生的小损坏，**重建优于修补**；只有不可再生的东西（自己写的代码、手工标注的评测数据）才值得逐个修
