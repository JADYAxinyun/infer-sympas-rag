# 证据增强型代码审查 Agent 架构

这是在原有 Infer 适配器、返回值规则、切片与本地模型 Demo 上增加统一编排的研究型 MVP。
不等同于完整 SymPas 或 DRaCo 论文复现，也不是生产级或完全自动修复系统。

```text
仓库 / Git Diff（上下文）
  → 现有 Infer runner → 现有 normalize_report → 真实 SIL 切片 / 契约候选
  → 现有 review_source（unchecked_return_value）
  → 仓库 AST 关系索引 → 可解释路径检索
  → Context Builder（证据编号、去重、排序、预算、hash）
  → none / mock / local CodeGen / DeepSeek
  → JSON schema 与证据引用检查
  → 独立的本地规则判断
  → 分离的候选文件 → 规则再查 / clang 语法检查 / 可选 Infer 再查
  → run.json / review.md / 全部中间记录
```

| 证据标签 | 来源 | 可以说明什么 |
|---|---|---|
| INFER_FACT | 实际 Infer report.json | 分析器实际输出的事实或候选，包含原始 issue |
| SYMPAS_SLICE | Infer/SIL Checker 的结构化 JSON | 保守依赖、控制位置、过程摘要及调用边；不是漏洞证明 |
| DRACO_CONTEXT | Python AST / clang AST 索引 | 相关仓库代码、关系路径及静态名称匹配 |
| RULE_FACT | 原有返回值规则 | 五行窗口内未找到检查；包含 manual / infer_candidate 契约来源 |

LLM 的 `confirmed` 只保留为模型意见，不会覆盖规则或验证状态。
`SYMPAS_SLICE` 与契约候选即使在 Infer issue 列表中，也不会自动当作缺陷。

## 复用与新增

- 复用 `draco-sympas/infer_adapter.py`、`review.py`、`contracts.py`、`repair.py`、`llm_service.py`。
- 扩展 `infer_runner.py`，保存命令、退出码、stdout/stderr、原始报告，拒绝旧 report 目录；增加超时和 SymPas 选项，旧调用签名仍可用。
- `agent.py` 是已有 Demo/API 能力的统一编排入口；旧 Demo、API、Prompt pipeline 保留。
- `context/repository.py` 提供关系图；没有复制或修改 DRaCo 上游。
- `context/builder.py` 组织已有分析结果；没有在 Python 中伪造 C/SIL 切片。
- `providers.py` 使用标准库调用 DeepSeek 的 OpenAI 兼容 Chat Completions 协议，避免为基础流程安装 SDK；原有本地 CodeGen 可选。
- `validation.py` 验证结构、引用和源码位置；`cli.py` 暴露 index/review/report。

## 索引与检索边界

Python 支持 AST 中的 ASSIGNS、REFERS、TYPEOF、INHERITS、AS、CALLS。
C/C++ 使用 clang AST 中的调用、引用、变量初始化与类型注解；不声称支持 C 的继承或别名语法。
图记录 unresolved / unique / ambiguous，路径最多扩展三跳并可反向遍历。
同名函数优先同文件，否则保留多目标候选；这不是可靠的链接器符号解析。
Python 模块级 import、动态绑定、C 函数指针及跨语言行为尚未解析。
每个关系都保留源码行、符号和所属过程；不是仅靠文本相似度生成关系。
text 模式另用符号词集合重合排序，明确标为 TEXT_SIMILARITY。

## 运行记录

每次创建新目录，禁止覆盖已有 run：

- `index.json`：节点、边、文件 hash、解析诊断与限制。
- `evidence.json`：完整证据注册表，包括原始 Infer issue 和 Checker 切片。
- `retrieval.json`：查询、命中节点、关系路径、距离、检索状态。
- `context.json` / `prompt.json`：实际提示、保留/丢弃记录、预算及 context hash。
- `infer/`：真实 Infer 原始产物；`run.json` 同时保存命令与原始响应。
- `candidate-*.c` / `infer-after-*`：候选与独立复查产物，不修改仓库源码。
- `review.md`：可阅读报告。

预算按序列化 messages 的 UTF-8 字节数保守控制，包含系统说明和角色字段；
它是 token 上界估算，不是 DeepSeek tokenizer 或计费 token。
整条证据超预算时丢弃并记录原因；diff 按 Unicode 字符截断；完整记录始终保留在 evidence.json。
模型返回的实际 usage 单独保存；none/mock 不填充虚构 usage。
