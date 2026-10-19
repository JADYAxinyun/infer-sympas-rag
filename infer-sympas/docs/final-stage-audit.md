# SymPas 风格切片阶段验收审计

日期：2026-10-19。本阶段目标是基于真实 Infer SIL/CFG 实现可运行、可测试、
可复现的 SymPas 风格分析器。阶段验收不表示与论文 LLVM-SymPas 完全等价。

## 14 条验收依据

| 原任务要求 | 当前可检查依据 |
|---|---|
| 1 Checker 运行于 SIL/CFG | 固定 Infer 基线上的类型检查、原生构建、正式 SymPas 测试及真实 capture/analyze/report 通过；完整补丁见 patches |
| 2 单函数数据依赖 | symbolic_cases 中 sym_first、sym_field、sym_array 等精确摘要断言及原有过程内回归 |
| 3 控制依赖 | 每个版本化样例显式给出 control_lines；提前返回、switch、条件调用、循环、多返回与无关分支排除均断言 |
| 4 过程摘要生成 | 结构化摘要版本 6 包含唯一过程身份、输入/内存/全局依赖、输出、源码/控制位置、来源与固定点信息 |
| 5 调用者读取并实例化 | SymPasSymbolic 使用 analyze_dependency，按当前调用点替换 formal、pointee、global；换序、多调用点及嵌套回归 |
| 6 多层传播 | sym_top→sym_middle→sym_leaf；ctrl_top→ctrl_middle→ctrl_leaf 验证数据和底层控制来源传播 |
| 7 递归/互递归收敛 | 同步 SCC 从空摘要迭代；报告成员/轮数/状态；定义顺序反转、递归输出、跨文件失效测试通过 |
| 8 指针/结构体边界 | 局部/可能/未知别名、返回指针、结构体指针、折叠字段和数组指针别名测试；额外依赖明确统计 |
| 9 新增测试通过 | 完整工作区与独立暂存快照测试；LIVE 单独跳过，不纳入成功声明 |
| 10 可重复评测 | evaluate_symbolic.py 重新执行真实 Infer，输出预期/实际、逐项断言、缺失/额外依赖、大小、时间、字节数及 SCC 状态 |
| 11 证据位置和状态 | 指令快照含过程、文件、行列、指令身份和事件；结果保持 partial/conservative |
| 12 失败/不支持明确报告 | 非法 C、损坏报告、缺失 Infer、未匹配准则、旧格式反馈；空 manifest 不允许误通过；失败切片保持统一字段 |
| 13 边界文档准确 | acceptance-evidence、reproduction-status、build-and-verify 与本审计相互引用；不声称通用正确性 |
| 14 GitHub 同步 | 功能提交 2f5a996、SCC 提交 f9b124b 均已 push；本收尾审计与测试改动以对应后续提交及远程 hash 回执为准 |

22 类测试场景映射见 `acceptance-evidence.md`。每个版本化样例的源码、命令、
准则、预期数据/控制/摘要、断言与实际输出均可由 manifest 和生成的评测 JSON
追溯；运行命令以仓库根目录为工作目录。所有预期行号只存在于测试 oracle。

## 本次收尾改动

- 未匹配的准则与损坏报告使用完整失败切片结构，位置未知值保留 null。
- 返回值准则尊重文件、行、列过滤，防止选择其他文件的过程。
- 每个样例新增明确控制 oracle；原有 required/excluded 检查继续保留。
- 空清单或无预期清单拒绝执行；缺失 Infer 输出机器可读的 failed 评测。
- 统计断言、失败用例、缺失/额外依赖、总时间、报告字节数和去重后的 SCC 结果。
- 补测数组与指针别名，以及跨三层调用的控制来源传播。

## 可复查结果与命令

当前真实 SIL 评测 95/95 条断言通过，必要依赖缺失 0、保守额外依赖 3；
5 个递归分量均收敛（单递归 3 轮，互递归 4 轮）。最近一轮四个编译单元
总耗时约 1.61 秒、报告约 711 KB，仅是当前小型回归的本机测量。
工作区完整测试 65 passed、1 skipped；独立暂存快照 59 passed、1 skipped，
同一快照重新运行 95 条断言全部通过。跳过项为未授权的 DeepSeek LIVE。
之前已通过的构建、正式测试、16 个旧回归、7 个 smoke 和 Mock E2E
见 `scc-verification.md`。本收尾没有修改 OCaml 分析源码或 Agent Provider。

```bash
INFER_BIN=/path/to/infer ./draco-sympas/.venv/bin/python -m pytest -q draco-sympas/tests infer-sympas/evaluation
INFER_BIN=/path/to/infer python3 infer-sympas/evaluation/evaluate_symbolic.py --output /tmp/sympas-evaluation.json
```

## 部分完成与未完成

控制依赖与别名仍为保守近似；聚合字段/数组元素折叠；未知调用和未知指向
可能保留额外依赖。变量准则定位 SIL 定义快照，finding 变量需要提供变量和
位置；调用链为静态依赖边。尚无任意复杂堆/间接调用/并发/inline assembly/
setjmp-longjmp 等特性的完整专门语义，也未证明与论文完整 LLVM 符号表等价。

没有独立人工参考切片、论文全量数据集或 SDG-IFDS 基线，因此不报告论文
精度、性能倍率、通用 soundness 或生产可用性。

当前只有规则化回归测试，尚未完成基于人工参考切片的完整精度评估。
