# 增量开发前现状检查（2026-10-19）

工作目录：`/Users/jadya/Documents/GitHub/desktop-tutorial`。
检查时分支 main，远程 origin 为 `https://github.com/JADYAxinyun/infer-sympas-rag.git`。
根目录及 draco-sympas 未发现额外 AGENTS.md；保留用户给出的精准修改、保护既有成果要求。
检查时存在大量既有未提交修改，先保存 tracked diff 与 untracked 清单，未重置工作区。
开发过程中出现新的 Checker 提交 `2f5a996`，本次集成基于它继续，不回退其源码。

| 模块 | 当前状态 | 原有功能 | 缺失/无法验证 | 基线测试 | 本次处理 |
|---|---|---|---|---|---|
| Infer | 已实现并实际运行 | capture/analyze、报告归一化、契约候选 | 完整命令日志、超时、旧报告隔离 | 真实 fixture TP=4 FP=0 FN=0 | 扩展 runner，复用 adapter |
| SymPas | 已实现，保留 partial | SIL 结构化切片、摘要、调用传播 | 非完整论文精度，需消费为稳定证据 | 结构化适配测试通过，真实 Checker 可运行 | 复用 Checker，不重写 |
| DRaCo | 上游与 Prompt 增强存在 | 固定 submodule、离线 ReccEval 上下文 | 无统一 review 图检索入口；未复跑完整上游实验 | 旧实验属历史记录 | 增加窄范围 AST 图与路径检索 |
| Context Builder | 有旧 Prompt 生成 | 原始报告解释提示 | 缺统一编号、hash、预算和去重 | 无统一 Builder 测试 | 新增连接层 |
| LLM | 本地 CodeGen 接口已实现 | 可选解释、token usage | 无 DeepSeek/Mock Provider；本轮不下载运行模型 | 运行前未验证本地模型 | 扩展可选 Provider |
| Validator | 有规则和修复再查 | 本地返回值规则、受控候选修复 | 缺 JSON schema 与证据引用检查 | 原有测试通过 | 补 fail-closed 检查 |
| Orchestrator | Demo/API 固定流程 | 规则、可选 Infer/LLM、报告 | 缺统一 review 接口与中间产物目录 | 旧 Demo 发现 1 条规则问题 | 增量编排原有模块 |
| CLI | 脚本/API 已实现 | run_pipeline、Demo、API | 无统一 index/review/report 命令 | 旧 Demo 实际成功 | 新增兼容脚本入口 |
| Tests | 自动测试/评估存在 | 规则、报告、修复、切片、评估 | 缺 Provider/Builder/引用测试 | **25 passed** | 保留并补集成与异常路径 |

基线命令：

```bash
./draco-sympas/.venv/bin/python -m pytest -q draco-sympas/tests
INFER_BIN=/Users/jadya/Documents/GitHub/infer-sympas-infer/infer/bin/infer \
  ./draco-sympas/.venv/bin/python draco-sympas/evaluation/evaluate_infer_e2e.py
```

旧 Demo 默认关闭 Infer/LLM，实际生成 1 条 finding，修复候选规则再查可运行。
运行 Demo 时备份并恢复三个既有输出文件，将本轮基线结果复制至独立临时目录。
真实 fixture 的旧评估脚本使用其默认 `artifacts/evaluation/infer_candidate_e2e_results.json`，
因此该文件更新为本轮基线复查结果；之后新增 Agent 与评估结果均写入新目录。
旧样本结果不用于证明 DeepSeek 效果、完整切片正确性或真实项目泛化。
