# 验收证据与实现边界

本实现运行在 Infer SIL/CFG 和自定义 Checker 上。符号输入、输出参数摘要与
调用点替换参考 SymPas 论文式(1)–(11)，实现定位为 SymPas 风格分析器。
当前不能声称完整复现论文的算法精度、LLVM pass 或实验结果。

## 测试矩阵

| 请求场景 | 自动化证据 |
|---|---|
| 1 单函数数据依赖 | `sym_first`；原有 data_dependency |
| 2 控制依赖 | symbolic_control 的提前返回、switch、条件调用及无关分支排除 |
| 3 一层跨函数 | `sym_swap` |
| 4 多层跨函数 | `sym_top → sym_middle → sym_leaf` |
| 5 多调用点 | `sym_two_calls` 及准则测试排除第二调用的语句来源 |
| 6 全局变量 | `sym_write_global`、`sym_global_entry`、`sym_read_global` |
| 7 循环 | `sym_loop`；原有 loop smoke |
| 8 递归 | `sym_recursive` |
| 9 互递归 | `sym_even`、`sym_odd` |
| 10 指针参数 | `sym_set`、`sym_pointer`；论文 Fig.4 适配调用链 |
| 11 局部别名 | `sym_alias`、`sym_alias_writes`、`sym_may_alias` |
| 12 结构体字段 | `sym_field`、`sym_aggregate_merge`、`sym_struct_pointer_return` |
| 13 数组元素 | `sym_array`；原有 array_dependency |
| 14 未解析调用 | `sym_unknown`、`sym_indirect`（允许明确记录的额外依赖） |
| 15 多返回路径 | `sym_returns`、symbolic_control |
| 16 返回值参与表达式 | `sym_expression` |
| 17 返回值未检查 | `sym_unchecked`；不把切片等同于缺陷判定 |
| 18 无关代码排除 | `sym_two_calls`、`sym_unrelated_flag`、`ctrl_unrelated` |
| 19 嵌套调用 | `sym_nested` |
| 20 多形参 | `sym_first`、`sym_swap` |
| 21 摘要持久化/失效 | test_summary_cache：同一数据库的冷/暖分析及被调用者修改后调用者更新 |
| 22 失败/不支持 | test_analysis_failure、准则未匹配、适配器损坏/旧格式测试 |

源码和预期摘要见 `tests/`、`evaluation/symbolic_cases.json`；运行命令、
实际输出、准则、自动化断言和测量值由 `evaluation/evaluate_symbolic.py`
生成 JSON。控制原始位置来自 SIL；switch 条件可能定位到 case 标签，而非
switch 关键字。所有行号是测试 oracle，分析器不硬编码样例名、变量名或行号。

## 当前证据

已运行固定基线上的类型检查、原生构建、Infer 正式 SymPas 测试；7 个
上游 smoke 通过，8 条旧摘要断言通过（20 个切片 finding）。
项目原有 16 个场景通过。新增准则/增量/失败及别名证据集成测试 12 项通过。
新增摘要及控制位置断言共 42 条；必要依赖均保留，保守用例的额外依赖单列。
完整工作区 Agent 测试 25 项通过，其中包含此前未提交的工作。
仅从本次暂存内容导出的独立快照中，42 条摘要/控制断言、12 项真实 Infer
集成测试和 12 项 Agent 测试全部通过；这组快照检查不依赖未提交的 Agent 改动。

新增评测按 `symbolic_cases.json` 逐条比较符号依赖；精确用例不允许额外依赖，
可能别名、折叠聚合和间接调用用例明确采用 required-subset，并单列缺失及
额外依赖。没有独立人工真值集，不报告泛化 Precision/Recall/F1。

当前只有规则化回归测试，尚未完成基于人工参考切片的完整精度评估。

## 收敛机制

过程内使用 Infer RPO 抽象解释器。摘要版本 6 显式识别当前过程所属的直接调用
SCC，从空摘要启动同步迭代；每轮读取上一轮结果，并合并新增依赖、输出、
指向关系及指令来源，直到整个 SCC 摘要相等。原子均来自有限 SIL/符号集合，
合并只增不减；不展开递归调用栈。未解析的外部调用仍走保守路径。

报告的 `procedure_summary.fixed_point` 记录成员、模式、轮数和收敛状态。
`rec_first` 在 3 轮后稳定；换序互递归 `rec_left/rec_right` 在 4 轮后稳定，
并排除了旧回退引入的无关参数。定义顺序反转结果和轮数一致；递归输出参数
调用者的依赖断言通过。这些是当前抽象域下的固定点证据，不证明与 LLVM
论文完整控制/内存语义等价。

SCC 成员通过 Infer 依赖回调及成员源码依赖记录到持久化失效图。跨文件测试
连续修改两名成员，确认未修改调用者及另一成员的摘要更新。该版本 Infer 的
changed-files 分析只调度指定文件根；跨文件完整复查使用先 incremental
`--invalidate-only`、再 `--continue-analysis` 请求全部已捕获根。

## 已完成的适配能力

- 前向符号依赖、输出参数/全局写入摘要、调用点实参替换和返回指向关系。
- 指令依赖快照、跨过程源码位置、控制位置和静态调用依赖边。
- 返回值、变量定义、调用点、finding 变量定义、返回点、文件行列查询。
- 结构化结果、明确的 partial/conservative 状态，以及失败/旧格式反馈。
- 可重复运行的回归评测和固定基线的完整集成补丁。

## 部分完成与未完成

- 控制依赖以 CFG 后支配关系传播，并保留保守近似；不表示完整路径可行性分析。
- 形参指针可能互为别名；对可能别名、聚合字段/数组和未解析写入使用弱更新。
  可增加额外依赖。尚无对象敏感堆分析、所有函数指针目标解析及任意多级指针模型。
- 指针返回支持指向形参/全局的别名实例化；返回逃逸局部对象、外部未知返回指向
  仍标为未知。`alias_evidence` 区分 confirmed、possible、unresolved。
- 准则查询定位 SIL 定义/指令快照；不支持任意使用位置的完整变量状态。
  finding_variable 需要提供变量/位置，尚未自动适配全部 Infer finding 语义。
- IDT 是 SIL 上的指令快照适配，尚未证明与原论文完整符号表语义等价。
- 目前的 call_chain 是静态依赖边，不是运行时调用轨迹或完整可行路径枚举。
- 未复现论文 66 个程序的评测、SDG-IFDS 对照、性能倍率或完整内存峰值。

GitHub commit/push 必须以实际同步证据为准；补丁存在与本地测试通过均不能
代替远程同步完成。
