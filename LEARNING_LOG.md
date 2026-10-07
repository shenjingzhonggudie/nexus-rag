# LEARNING_LOG

> 记录格式参考任务书 §9。每轮追加一条，**失败、误判与返工原因一并记录**，不只记"完成了什么"。
>
> 项目：RAGKit —— 从零手搓的中文技术文档 RAG 系统（不使用 LangChain / LlamaIndex，默认离线可运行）
> 最后更新：2026-10-07

## 进度总览

| 轮次 | 日期 | 主题 | 用例数（累计） | 结果 |
|---|---|---|---|---|
| 第 0 课 | 2026-09-29 | 环境初始化与可运行骨架 | 3 | 3 passed |
| 第 1 轮 | 2026-10-01 | 领域模型：`Document` / `Chunk` | 17 | 17 passed |
| 第 2 轮 | 2026-10-02 | 嵌套模型：`ScoredChunk` / `Citation` | 23 | 23 passed |
| 第 3 轮 | 2026-10-03 | 列表与可选嵌套：`StageTrace` / `RetrievalTrace` / `Answer` | 39 | 39 passed（经一轮返工） |
| 第 4 轮 | 2026-10-05 | 配置系统：`config.py` + `errors.py` + `configs/default.yaml` | 52 | 52 passed（中途遭遇环境损坏，重建 `.venv` 后通过） |
| 第 5 轮 | 2026-10-07 | 配置：环境变量覆盖 + 深合并 + 密钥脱敏 + 测试隔离 | 64 | 64 passed（污染环境后仍全绿） |
| 事故 | 2026-10-05 | 「行尾 t 批量删除」事件（详见文末事故记录） | — | 已恢复 |

> **阶段 1 于 2026-10-07 收官**：领域模型（7 个）+ 配置系统（5 个模型）全部完成，64 条测试全绿。

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

## 贯穿各轮的通用规律（每条都至少撞过一次）

1. **改名是多点同步**——改完必须全局搜索旧名，确认 0 命中（已撞 3 次：`cli.py`、`test_schemas.py`、`retrieved_traces`）
2. **可变默认值只用 `default_factory`**——dict 与 list 各撞一次
3. **roundtrip 只验对称性**——契约靠键集合，类型靠 `isinstance`，值靠独立期望值
4. **可选性只有一个真相来源**——字段有没有默认值；`_require_fields` 必须与它一致
5. **`in` / `is None` / 真值判断是三件事**——`.get(k, d)` 挡不住 `None`，`if x` 挡不住空 `{}`
6. **不可见字符靠工具判断，不靠眼睛**——空格 vs 制表符、CRLF vs LF、全角 vs 半角，一律用 `repr()` 或"显示空白字符"确认；对照实验的结论不能当成被测文件的证据
7. **清单是示例，不是完整清单**——大面积、可再生的小损坏，**重建优于修补**；只有不可再生的东西（自己写的代码、手工标注的评测数据）才值得逐个修
