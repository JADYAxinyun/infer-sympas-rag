# Agent 集成验收记录（2026-10-19）

## 本轮新增

统一 ReviewAgent.review、index/review/report CLI、Python/clang AST 关系索引与可解释路径检索、
证据 Context Builder、DeepSeek/Mock/none/local Provider、JSON/引用验证、独立候选复查、四组 smoke 对比。
原有 Infer adapter、契约策略、返回值规则、候选修复与本地 CodeGen 得到复用。
未重写 Infer/SymPas Checker 或 DRaCo 上游；旧 API/Demo/报告能力保留。

本次提交纳入现有未提交实现中的必要依赖：contracts.py、review.py、infer_adapter.py、
llm_service.py 及相应测试；这些是原有成果的接入，不计作本轮从零新增功能。
README 仅暂存本轮新增入口说明，保留工作区原有大段 README 修改。
其他既有实验、API、报告等修改继续留在工作区，未混入本次提交。

## 验证结果

- 实施前原有测试：25 passed。
- 当前完整工作区：58 passed、1 skipped；其中包含尚未纳入本次提交的旧评估/报告测试。
- **仅暂存内容的干净快照：52 passed、1 skipped**。这是本次可发布内容的验证结果。
- 干净快照中的真实 Infer + Mock LLM：Infer ok、1 条规则 finding、LLM JSON ok、引用检查通过、整体 partially_verified。
- 干净快照中的 Mock Infer + Mock LLM：Infer mock、切片 not_analyzed、1 条规则 finding、JSON ok。
- 干净快照中的 none：Infer/LLM not_run，规则仍可执行；模型验证 not_verified。
- 干净快照中的 index 与 Markdown report 导出成功。
- 四组评估：4 案例 × 4 模式；结果和指标边界见 [evaluation.md](evaluation.md)。
- 默认离线测试、真实 Infer 集成与 SIL 切片准则/摘要缓存回归均通过。
- DeepSeek HTTP 模拟测试通过；真实 API **NOT_RUN**，因环境无 DEEPSEEK_API_KEY；没有真实 API 成功声明。
- 本地 CodeGen 未运行，保留可选能力；不宣称其严格 JSON 成功率。
- 暂存文件检查未发现凭据特征、.env、缓存、构建产物或超过 1 MiB 的文件；git diff --cached --check 通过。

验证命令：

```bash
INFER_BIN=/absolute/path/to/infer ./draco-sympas/.venv/bin/python -m pytest -q \
  draco-sympas/tests infer-sympas/evaluation/test_query_slice.py \
  infer-sympas/evaluation/test_summary_cache.py
```

干净快照由 git write-tree + git archive 导出，使用同一项目虚拟环境和真实 Infer，
不复制工作区未暂存文件，因此证明发布内容不依赖未提交的评估脚本或报告修改。
保留本机回执：`/tmp/infer-agent-staged-verification.json`；其中有 snapshot、tree、命令、退出码和输出。
临时快照不是长期制品，持久化的测试范围与结果以本记录为准。

## 当前证据级别

可运行、可测试、可演示的研究型 MVP。候选修复仅部分验证，源码仓库不自动应用修复。
SymPas 保留 partial，DRaCo 图为窄范围静态关系实现；没有通用精度或生产级声明。
后续优先进行一次显式 DeepSeek smoke，再扩充独立真实项目与人工标签；不能用 Mock 成功代替真实模型效果。
