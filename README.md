# Infer-SymPas-RAG

An experimental project that adapts symbolic program slicing to the Infer SIL framework and uses the resulting slices to construct task-relevant contexts for code RAG and LLM-based program analysis.

> 当前仓库仍使用原有的 `desktop-tutorial` 远程仓库地址；项目名称和远程仓库名称将在本地原型稳定后再决定是否调整。

## Research Route

```text
Infer SIL
  → Infer-SymPas 程序切片器
  → SymPas 切片作为代码 RAG 上下文
  → LLM 候选错误规格推断
  → 静态事实、编译或测试验证
  → 后续扩展为 Agent 调度闭环
```

## Current Status

**Runnable research MVP**

当前项目已经打通：

```text
Infer/SymPas → program slice → DRaCo context → local LLM → review report
```

已验证跨过程摘要、全局依赖、递归、简单指针别名和聚合内存场景；同时提供本地 API、UI、结构化 JSON 报告和 7 个自动化测试。当前仍是研究型原型，不等同于完整复现论文或生产级代码审查系统。

最近一次本地结果：7 个测试通过；10 个 ReccEval 样本的最小对比实验中，首行相似度从 0.5226 提升到 0.5974。该结果样本量较小，仅作为工程证据。

## Repository Layout

- `infer-sympas/`: Infer 上的 SymPas 复现模块、Checker 设计和切片测试。
- `rag/`: 后续的切片结果读取、源码提取、Prompt 构造和 LLM 调用。
- `agent/`: 后续的检索、切片、推断和验证调度。
- `experiments/`: 配置、评测脚本和实验结果；不提交缓存或大模型权重。
- `docs/`: 路线、架构、复现记录和参考来源。

## Roadmap

- [x] 在 macOS ARM64 上构建 Infer C/C++ 分析支持
- [x] 查看并验证最小 C 程序的 SIL/CFG 相关切片结果
- [x] 注册 SymPas Checker
- [x] 实现过程内后向数据依赖切片
- [x] 加入初步控制依赖
- [x] 加入形式参数/全局变量过程摘要与调用点传播（原型）
- [x] 导出结构化 JSON 切片和统一 finding
- [x] 将切片接入代码 RAG Prompt
- [x] 比较 DRaCo 与 DRaCo + SymPas 上下文
- [x] 接入本地 LLM 解释
- [x] 完成固定工作流 Agent 闭环
- [ ] 增加自动修复并重新运行 Infer 验证
- [ ] 扩大对比实验并记录 Precision/Recall/F1、Token 和延迟
- [ ] 增加自主工具选择和失败重试

## Research Basis

- SymPas: Symbolic Program Slicing
- Facebook Infer static analysis framework
- DRaCo: Dataflow-Guided Retrieval Augmentation for Repository-Level Code Completion
- Interleaving Static Analysis and LLM Prompting

详见 [`docs/references.md`](docs/references.md)。

## Quick Demo

使用带 SymPas Checker 的 Infer 和项目虚拟环境运行端到端 C 代码审查：

```bash
INFER_BIN=/Users/jadya/Documents/GitHub/infer-sympas-infer/infer/bin/infer \
  ./draco-sympas/.venv/bin/python draco-sympas/examples/run_e2e_demo.py
```

结果写入 `draco-sympas/artifacts/e2e-unchecked-return.json`。运行测试：

```bash
./draco-sympas/.venv/bin/python -m pytest -q draco-sympas/tests
```

## Disclaimer

This is an independent reproduction and extension project. It is not an official implementation of the referenced papers.
