# Infer-SymPas 核心复现审计

日期：2026-10-19。授权发布基线：`6c2bd9cf4d4d573b8d83d1c45ce9c6b6a6317cdf`。
本轮只增量修改 SymPas，不扩展 Agent，不修改论文。实现摘要版本 9。

## 验收逐项核对

| 要求 | 当前证据 | 结论 |
|---|---|---|
| 1 SIL/CFG | SymPasSymbolic 在真实 OneInstrPerNode CFG 上运行；Infer 类型检查、原生构建与正式 SymPas 测试通过 | 已实现 |
| 2 切片准则 | query_slice.py 选择 Checker 指令/变量快照，准则记录过程与文件行列 | 已实现验证子集 |
| 3 数据依赖 | 赋值覆盖、表达式、多来源、返回值、全局、指针/聚合的规则与参考断言 | 标量子集一致；内存保守 |
| 4 控制依赖 | symbolic_control 的 switch、提前返回、条件调用、多返回与无关分支排除；程序点保留路径控制 | 保守适配，有定位证据 |
| 5 结构化摘要 | Formal/Global/Pointee/Heap、逐输出 dependencies/aliases、Source、唯一过程身份、版本与固定点状态 | 已实现 |
| 6 调用点实例化 | 调用前快照替换输入、输出及别名；换序、嵌套、多调用点、多层传播 | 已实现验证子集 |
| 7 SCC 固定点 | 同步整分量迭代，有限符号/位置域；5 个 SCC 在 3/4 轮收敛，定义顺序反转与跨文件缓存测试 | 已实现验证子集 |
| 8 基础别名 | 局部/形参/返回/输出指针；确认、可能、未知证据 | 已实现，复杂别名保守 |
| 9 指针/字段/数组/堆 | 独立分配点、工厂指针、指针输出、字段/数组整体折叠；heap_summary 三项集成测试 | 已实现基础场景；非对象敏感 |
| 10 内存读写 | 已知目标读写；可能别名弱更新；未知读取包含已追踪内存；指针写回保留别名 | 保守近似，未知外部状态无完整保证 |
| 11 递归/循环/多调用点 | 规则回归、SCC 与参考集合均覆盖 | 已验证 |
| 12 六类查询 | return_value、variable、call_site、finding_variable、return_point、file_location；程序点覆盖前后、路径与缺失变量 | 已验证，位置为 after_instruction |
| 13 结构化输出 | SYMPAS_SLICE、准则、依赖、摘要、静态调用边、位置、alias_evidence、partial/conservative | 已实现；不是运行时调用栈 |
| 14 参考评测 | 9 个预先推导源码语句参考；每例 missing/extra、Precision/Recall/F1、大小、耗时、输出字节 | 已完成构造参考评测；无独立人工 ground truth |
| 15 论文语义对照 | core-semantics-matrix.md 按式(1)–(11)、SCC 与别名假设核对原文 | 已完成四类边界说明 |
| 16 回归与审计 | 工作区 89 passed、1 skipped、13 subtests passed；95 条规则断言、16 个旧场景、7 个 smoke、8 条旧摘要断言；独立发布快照另记 | 工作区通过；发布证据见下节 |

## 本次变更及阶段证据

- A：预先推导参考与比较器，记录 8/9 红色基线，而不是改参考掩盖错误。
- B：分配点堆、工厂返回/跨函数读写、指针值输出别名、未知读写保守处理。
- C：每条 SIL 指令后的变量状态快照及六类查询兼容，带控制来源。
- D：空参考拒绝、不支持准则拒绝、执行失败结构化反馈；完整语义对照与发布审计。

中间结果在 `evaluation/core-results/stage-a.json`、`stage-b.json`、
`stage-b-alias.json`、`stage-c.json`；这些是历史实测，不随当前结果改写。
新源码/参考的行号只用作测试 oracle，分析器不硬编码样例名称或行号。

当前参考微平均（仅按标记语句投影）：TP=26、额外=1、缺失=0；
Precision=26/27、Recall=1、F1=52/53，9/9 满足各自 exact/conservative 标准。
唯一额外为数组初始化。总切片语句计数 27（跨样例累加，不是全项目唯一行数）。
这些指标不能称为通用 soundness、论文精度或独立人工评测。

当前规则评测 95/95，缺失 0、保守额外 2；五个 SCC 收敛。
程序点快照会扩大摘要：本机最近规则评测输出约 1.45 MB、用时约 1.49 秒；
参考评测输出约 277 KB、用时约 0.60 秒。仅为小型构造回归的本机测量。

## 复现命令

在仓库根目录设置带本项目 Checker 的 `INFER_BIN`，Python 使用已安装测试依赖的环境：

```bash
INFER_BIN=/path/to/infer python -m pytest -q draco-sympas/tests infer-sympas/evaluation
python3 infer-sympas/evaluation/evaluate_symbolic.py --output /tmp/sympas-core-rules.json
python3 infer-sympas/evaluation/evaluate_reference_slices.py --output /tmp/sympas-core-reference.json
bash infer-sympas/tests/run_sympas_tests.sh
```

Infer fork：`make -j 4 -C infer/src check`、`make -j 4`、
`make -C infer/tests/codetoanalyze/c/sympas`、
`./examples/sympas/run_smoke_tests.sh`、`python3 examples/sympas/evaluate_smoke.py`。
固定 Infer 基线为 717ee0b36c，版本 v1.3.0；macOS arm64。
完整集成补丁通过临时 Git index 的固定基线正向应用与当前源码反向应用检查。

## 发布隔离与剩余边界

仅纳入 infer-sympas 的源码、补丁、fixtures、评测、阶段记录和文档。
Agent/Demo 的已有脏改动、旧 report.txt、未跟踪 Agent 评测均不纳入。
LIVE 模型调用本轮保持禁用；Mock 与真实 Infer + Mock 的回归包含在完整测试中。
独立发布快照：83 passed、1 skipped、13 subtests passed，95/95 规则断言、
9/9 参考比较通过。工作区多出的 6 个测试属于未跟踪 Agent 评测，不纳入发布。
快照 CLI Mock 与真实 Infer + Mock 均为 1 条 finding、LLM ok；前者切片
not_analyzed、后者 partial，整体均 partially_verified，没有把 Mock 当完整验证。
run/prompt JSON 存在，main.c/config.c 与基线字节一致。
拟提交文件的常见凭据特征、本地用户路径、缓存/密钥路径及大文件检查未发现问题，
diff --check 通过。实测回执见 `evaluation/core-results/stage-d.json`。
GitHub 同步以实际提交和远程 hash 为准，不将本地测试当作 push 证据。

复杂对象敏感堆、完整间接调用目标、未追踪外部全局副作用、逃逸栈地址、
并发/异常控制、完整 LLVM 命名值表与第4节前向切片未完整实现。
LLVM basicaa/gvn、论文全量数据集、SDG-IFDS 对照、独立人工参考及论文性能倍率
无法由当前证据验证。这些不被测试通过所替代，结果仍为 partial/conservative。

本项目已实现并验证 Infer SIL/CFG 上的 SymPas 风格核心反向切片闭环；
尚不能称为 LLVM-SymPas 的完整等价复现。当前只有规则化回归测试，尚未完成
基于人工参考切片的完整精度评估。
