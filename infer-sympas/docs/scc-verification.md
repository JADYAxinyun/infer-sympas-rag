# SCC 增量检查

授权基线：`1670243d2b8bcbd2990f6373bd0642fa236bf55f`，2026-10-19。

本轮 9 个核心文件为 4 个 OCaml 源文件、摘要 manifest、摘要缓存测试、
SCC 固定点测试以及两个递归 C 样例。另同步完整构建补丁及当前验收说明。
原有 README、API、Demo、报告等 7 个已跟踪改动与未跟踪旧评测材料不纳入提交。

## Diff 检查

- SCC 从底元素同步迭代，合并单调增加的有限符号集合，整分量稳定才返回。
- 报告摘要版本 6，导出 SCC 成员、轮数及状态；非递归过程标记 acyclic。
- 源码依赖支持 SCC 成员跨文件修改后的缓存失效；不改动 Agent/Provider 接口。
- 核心源码与构建补丁一起更新；补丁通过固定 Infer 基线正向和当前源码反向检查。
- 仅暂存 SCC 内容；不纳入 API Key、.env、缓存、运行日志、模型或本地路径配置。

## 验证范围

完整项目测试包含 `draco-sympas/tests` 与 `infer-sympas/evaluation`；真实 Infer
集成测试显式设置 `INFER_BIN`。DeepSeek LIVE 不属于本次授权，保持未运行。
Mock 端到端显式指定 Mock Infer 与 Mock LLM，并检查 JSON、证据来源、报告和
源码未修改；另验证真实 Infer + Mock LLM 的兼容性。

SIL 评测共 47 条摘要/控制断言；SCC 新样例覆盖无关参数排除、形参换序、
定义顺序反转、递归输出参数。缓存测试在三个 C 编译单元间连续修改两个成员。
原有 16 个项目回归、7 个 smoke、8 条旧摘要断言以及 Infer 构建/正式测试继续验证。

## 本次执行结果

- 工作区完整项目测试：61 passed、1 skipped。
- 仅暂存内容导出的独立快照：55 passed、1 skipped（DeepSeek LIVE 未运行）。
- 47 条摘要/控制断言全部通过，必要依赖缺失 0；原有 16 个回归场景通过。
- Infer 类型检查、原生构建、正式 SymPas 测试、7 个 smoke 和 8 条旧摘要断言通过。
- 独立快照 CLI Mock Infer + Mock LLM：1 条 finding、Infer mock、LLM ok、
  slice not_analyzed、整体 partially_verified，prompt/run JSON 存在。
- 独立快照 CLI 真实 Infer + Mock LLM：1 条 finding、Infer ok、LLM ok、
  SIL slice partial、整体 partially_verified；输入源码字节不变。
- 原有 9 个已跟踪 diff 与本次暂存内容的常见凭据特征检查通过；暂存文件无
  .env、缓存、产物、超过 1 MiB 的文件或本地绝对路径配置；diff --check 通过。

执行命令：

```bash
INFER_BIN=/path/to/infer ./draco-sympas/.venv/bin/python -m pytest -q draco-sympas/tests infer-sympas/evaluation
INFER_BIN=/path/to/infer python3 infer-sympas/evaluation/evaluate_symbolic.py
python draco-sympas/cli.py review --repo /path/to/fixture --target-file main.c --infer-mode mock --llm-provider mock --output /path/to/new-run
```

CLI 输出目录必须是新目录。
此实现仍标记 partial/conservative，未宣称完整论文复现。
