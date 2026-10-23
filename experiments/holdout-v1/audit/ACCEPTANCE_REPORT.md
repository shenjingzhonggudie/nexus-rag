# rag-holdout 验收报告（最终验收运行）

- 运行时间：2026-10-23 13:20–13:30（GMT+8）
- 代码：`80b6aea3da638057db4e531f05e5bedde14f956c`（工作区干净，运行前后无代码修改）
- 题集：`sealed/qrels.test.json`（v1.0.0，62 条主集；SHA-256 与 manifest 核对一致）
- 配置：首次运行前预登记的两个固定配置（见 `freeze_check.md` 第五节与 `frozen_configs/`）；
  运行后未追加候选、未改阈值、未依据分数删题
- 项目代码与 sealed 标签：**未修改**。本目录新增文件为本验收产出
- 重试记录：配置 A 首次运行失败（HF hub 联网校验模型，代理 502）；
  置 `HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1` 后成功（模型本已本地缓存，快照 7999e1d3）。
  属运行环境修复，不涉及查看成绩调参。配置 B 一次成功。

---

## 一、汇总指标（口径按 sealed/manifest.json 的 eval_protocol）

### 配置 A：bge + 加权排名融合（α=0.7，refuse_threshold=0.05）

| 指标 | 数值 |
|---|---|
| 可回答题数量 | 42（direct 29 / paraphrase 5 / cross_doc 5 / multi_block 3） |
| recall@5（可回答题） | **0.964** |
| MRR（可回答题） | **0.893** |
| recall@1 / @3 | 0.738 / 0.952 |
| 误拒 | **0 / 42** |
| 无答案正确拒答 | **0 / 20**（全部误答） |
| 全集 recall@5 / MRR（eval 原始输出，62 条口径） | 0.964 / 0.893 |
| 分类型（可回答题） | direct @1=0.828 @5=1.000 MRR=0.902；paraphrase @1=0.800 @5=1.000 MRR=0.900；cross_doc @1=0.300 @5=0.700 MRR=0.767；multi_block @1=0.500 @5=1.000 MRR=1.000 |

### 配置 B：hashing + 等权 RRF（refuse_threshold=0.05）

| 指标 | 数值 |
|---|---|
| 可回答题数量 | 42 |
| recall@5（可回答题） | **0.929** |
| MRR（可回答题） | **0.831** |
| recall@1 / @3 | 0.667 / 0.905 |
| 误拒 | **0 / 42** |
| 无答案正确拒答 | **0 / 20**（全部误答） |
| 分类型（可回答题） | direct @1=0.724 @5=1.000 MRR=0.842；paraphrase @1=0.800 @5=1.000 MRR=0.900；cross_doc @1=0.300 @5=0.400 MRR=0.600；multi_block @1=0.500 @5=1.000 MRR=1.000 |

### 对比结论（两个预登记配置之间的固定比较）
- 配置 A 在可回答题上全面占优：recall@5 +0.035、MRR +0.062，差距主要来自 cross_doc（@5 0.700 vs 0.400）。
- 两者误拒均为 0；无答案拒答均为 0/20——**拒答机制在 holdout 上完全失效**（详见第二节）。

## 二、无答案拒答（按封存预定子类，正确拒答数/总数）

两个配置完全相同：**所有子类均为 0**。全部 20 条无答案题的 match_score 最低 0.367、
最高 1.000，远高于阈值 0.05，实词覆盖判据未触发任何拒答。

| 子类 | A | B |
|---|---|---|
| 缺失默认值 | 0/8 | 0/8 |
| 缺失取值建议 | 0/2 | 0/2 |
| 缺失作用范围说明 / 反向规则 / 服务端上限 / 版本门槛 / 监控手段 / 迁移步骤 / 部署细节 / 配置项名 / 重试策略 / 非 Babel 链路配置（各 1 条） | 0/10 | 0/10 |

注意：`sealed/manifest.json` 的 counts 中另有 challenges 4 条（no_answer_binary/纠错类），
其格式不在 `eval --qrels` 入口支持范围内，本次验收未运行；如需覆盖需另行评估入口。

## 三、耗时与运行环境

| | 配置 A | 配置 B |
|---|---|---|
| 冷启动 | 31 188 ms（含 bge 模型加载） | 34 ms |
| 热启动 P50 / P95 | 38.4 / 57.2 ms | 17.2 / 40.4 ms |

环境：Windows（win32），项目 venv Python 3.12.10，ragkit 1.0.0，
torch==2.14.1、sentence-transformers==6.1.0、transformers==5.20.2、numpy==2.5.4、
jieba==0.42.1、pydantic==2.13.5、PyYAML==6.0.3（完整 freeze 见 freeze_check.md 第二节）。

## 四、预定人工子集证据充分性核对（12 条，独立报告，不与区间命中混算）

子集为封存时固定的分层样本（含 4 条无答案题）。判定标准：top-5 返回证据合并后
是否**足以回答所问**（以题面为准，无答案题以"证据不含所问信息"为正确形态）。

| 题号 | 类型 | 配置 A | 配置 B | 依据要点 |
|---|---|---|---|---|
| h_0003 | paraphrase | ✅ 足够 | ✅ 足够 | 证据含 Unknown 标记、驱逐等待 5 分钟、巡检周期 5 秒 |
| h_0011 | multi_block | ✅ 足够 | ✅ 足够 | containerLogMaxSize(10Mi)/containerLogMaxFiles(5)、Linux journald 与 /var/log、Windows 路径均在证据中 |
| h_0021 | direct | ✅ 足够 | ✅ 足够 | 公式 connections=(core_count×2)+effective_spindle_count；明确 core_count 为物理核心数、与超线程无关 |
| h_0030 | cross_doc | ✅ 足够 | ❌ **不足** | A 的 top-5 含隐式类型转换文档（varchar 主键与数字比较→索引失效）；**B 未返回该文档**，5 条证据均不能解释该现象 |
| h_0044 | direct | ✅ 足够 | ✅ 足够 | delay 默认 200ms、timeout 默认 Infinity 均在原文中明示 |
| h_0046 | cross_doc | ✅ 足够 | ✅ 足够 | suspensible 默认行为、加载状态由 Suspense 管理、suspensible:false 自管加载，均在证据中 |
| h_0059 | direct | ✅ 足够 | ✅ 足够 | Babel `overrides` 目录级覆盖原文命中 |
| h_0062 | direct | ✅ 足够 | ✅ 足够 | Next.js 与"全栈框架不需要服务器"（CSR/SPA/SSG→CDN）均在证据中（与 gold 区间内容一致） |
| h_0013 | no_answer | ❌ 证据不含所问参数默认值（语料本缺失），系统未拒答 | 同 A | 正确行为应为拒答 |
| h_0032 | no_answer | ❌ 证据提及 tidb_idle_transaction_timeout 但无默认值；给出的是 wait_timeout 28800 秒（易误导） | 同 A | 正确行为应为拒答 |
| h_0053 | no_answer | ❌ 证据仅含反向规则（PascalCase 注册→kebab 引用），所问方向语料缺失 | 同 A | 正确行为应为拒答 |
| h_0068 | no_answer | ❌ 证据无"监控采用进度"具体方法 | 同 A | 正确行为应为拒答 |

**小结**：可回答题证据充分率 A 8/8，B 7/8（B 的 h_0030 证据不足）；无答案题 4 条在两配置下
返回的均为"看似相关但答不了"的证据且未拒答。该核对与区间命中相互独立：
如 B 的 h_0030 区间未命中（recall 口径）与证据不足判定一致，但 A 中也有
区间命中而本表单独确认的条目（如 h_0044、h_0062）。

## 五、能力边界声明（抽取式）

当前系统 `llm.provider=none`，为**抽取式/检索层**验收。本报告所有指标只衡量
检索召回、排序与拒答触发，**不构成**对生成模型忠实性、纠错能力、部分回答能力的评测结论。
无答案题"误答 0/20"的含义是**未触发拒答**（检索层未识别证据不充分），
不是生成层给出了错误答案——该层尚未存在，亦未评测。

## 六、产物清单（全部位于 rag-holdout/audit/）

| 文件 | 内容 |
|---|---|
| `freeze_check.md` | 冻结状态核查 + 配置预登记（先于运行写入） |
| `frozen_configs/configA.bge.weighted.yaml` | 配置 A 固定配置 |
| `frozen_configs/configB.hashing.rrf.yaml` | 配置 B 固定配置 |
| `eval.configA.bge.weighted.json` | 配置 A 完整逐题结果（62 条） |
| `eval.configB.hashing.rrf.json` | 配置 B 完整逐题结果（62 条） |
| `human_subset_evidence.json` | 人工子集 12 题 × 2 配置的 top-5 证据原文 |
| `ACCEPTANCE_REPORT.md` | 本报告 |

原开发报告（项目内 reports/eval.json）未被覆盖。

## 七、后续使用约束（预登记）

本测试集自本次验收起**已进入开发反馈循环**：本次失败案例（尤其无答案 0/20 拒答失效、
B 配置 cross_doc 缺口）若用于修改系统，则该集上的任何后续成绩只能作为**回归表现**解读；
下一轮独立结论必须使用新的、未接触过的测试题。
