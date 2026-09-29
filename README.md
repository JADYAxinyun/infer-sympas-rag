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

**Planning / environment preparation**

目前已建立项目骨架和最小测试用例，尚未完成自定义 Infer Checker、SymPas 算法复现或实验结果。

## Repository Layout

- `infer-sympas/`: Infer 上的 SymPas 复现模块、Checker 设计和切片测试。
- `rag/`: 后续的切片结果读取、源码提取、Prompt 构造和 LLM 调用。
- `agent/`: 后续的检索、切片、推断和验证调度。
- `experiments/`: 配置、评测脚本和实验结果；不提交缓存或大模型权重。
- `docs/`: 路线、架构、复现记录和参考来源。

## Roadmap

- [ ] 在 macOS ARM64 上构建 Infer C/C++ 分析支持
- [ ] 查看最小 C 程序的 SIL 与 CFG
- [ ] 注册空的 SymPas Checker
- [ ] 实现过程内后向数据依赖切片
- [ ] 加入控制依赖
- [ ] 加入过程摘要与调用点实例化
- [ ] 导出结构化 JSON 切片
- [ ] 将切片接入代码 RAG Prompt
- [ ] 比较完整函数、固定窗口和 SymPas 切片上下文
- [ ] 加入 LLM 候选规格验证
- [ ] 扩展为 Agent 调度闭环

## Research Basis

- SymPas: Symbolic Program Slicing
- Facebook Infer static analysis framework
- DRaCo: Dataflow-Guided Retrieval Augmentation for Repository-Level Code Completion
- Interleaving Static Analysis and LLM Prompting

详见 [`docs/references.md`](docs/references.md)。

## Disclaimer

This is an independent reproduction and extension project. It is not an official implementation of the referenced papers.
