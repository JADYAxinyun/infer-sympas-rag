# 证据增强型代码审查 Agent 架构

这是在原有 Infer 适配器、返回值规则、切片与本地模型 Demo 上增加统一编排的研究型 MVP。
不等同于完整 SymPas 或 DRaCo 论文复现，也不是生产级或完全自动修复系统。

```text
仓库 / Git Diff（上下文）
  → 现有 Infer runner → normalize_report → SymPasAdapter → SliceResult / 契约候选
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

## Agent 侧稳定 SliceResult

`draco-sympas/sympas_adapter.py` 仅转换字段，不重算 SIL/CFG、SCC、摘要或依赖。
读取 `analysis_status` 或兼容的 `status`，保留 partial / unsupported / failed / not_analyzed，
未知状态为 not_analyzed；原始值保存在 raw_slice，原始新增字段继续保留。
当前真实 Checker 返回 partial，Agent 不将其升级为完整 SymPas。

## 原始产物和源文件验证

验证时只允许模型引用实际送入 Prompt 的 ID，使用未投影的原始注册表作对照。
Infer finding 回查本轮 report.json，切片通过 SymPasAdapter 与原始 Checker JSON 逐项对照；
DRaCo 片段同时匹配 index.json 与 retrieval.json，规则匹配 rules.json。
所有引用必须有有效文件/行号，并与索引时的源码 hash 一致；原始 slice、检索和规则各自保存。
未提供原始产物只能部分验证；无引用时不标 verified。
只有上下文或切片、没有规则/缺陷事实时，不接受 confirmed/likely，要求 evidence_insufficient。
这些是来源和完整性检查，仍不能证明模型推理或候选修复的语义正确性。

## 接近真实场景的样例和候选验证

`examples/realistic_case/` 的三类构造案例各自包含源码、契约、expected.json 和独立行为 oracle。
它们用于 small-scale prototype evaluation，不作为真实生产缺陷或普遍泛化证据。

`repair_validation.py` 读取来源明确的候选 unified diff，检查目标范围和窄范围返回值 guard 语法，
拒绝路径逃逸、新增/删除/重命名文件、二进制/模式修改、测试和配置修改、任意新增调用。
随后复制仓库到独立工作区，排除秘密文件、缓存、模型和符号链接；测试子进程不继承 API Key。
只执行用户显式提供的测试 argv，shell=False，不执行模型给出的命令。
在副本中记录原规则/行为结果，再 git apply --check/apply、语法检查、同配置 Infer、规则和行为复查。
补丁不适用、重查失败或 oracle 不通过都返回 validation_failed；不应用到输入仓库。
即便有限测试全部通过仍只标 partially_verified，不把候选提升为普遍正确的修复。

阶段产物包括 infer.json、slice.json、retrieval.json、context.json、llm_response.json、validation.json、review.md；
兼容保留 index、rules、slices、evidence、prompt、run 等旧文件。
context 太小、无切片、无检索、模型超时/缺 Key/非法 JSON、引用错误和修复失败均记录阶段状态与原因。
子目录 review 仅收集该目录的 Git Diff，不带入共享仓库中其他项目的改动。

五模式配置：A 仅 native Infer；B native Infer + SymPas + 本地规则；C 增加关系检索；D 增加 Mock；E 显式增加 DeepSeek。
A 不使用切片或本地规则，B-E 使用相同 native+SymPas Checker 配置；不能把 A/B 差异仅归因于切片。

Context Builder 对每类证据先保留一个代表，按规则调用点优先切片、按 callee 优先仓库代码，随后补齐其余记录。
Prompt 中省去重复的 SIL 指令文本，但保留来源位置、符号、控制/数据依赖和调用点；原始文本完整保存在证据文件中。
检索命中与真正进入 Prompt 分别计量；无法装载的记录必须留下 dropped 原因。
审查验证与 candidate_validation_status 独立记录，候选失败时 CLI 返回非零并仍写完整报告。
