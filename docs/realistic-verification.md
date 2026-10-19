# Agent 真实场景验证阶段验收（2026-10-19）

## 范围和基线

本轮只完善 Agent。起点为 6c2bd9c；并行对话随后提交 f8b6a80 的 SymPas 核心成果，保留其提交与文件。
本轮不改 SIL/CFG、摘要、SCC、内存/依赖分析、DRaCo 图算法，不修改或删除旧测试。
已有未提交 README、API、旧 Demo、报告及评估文件仍保留，不混入本次提交。
README 仅暂存本轮新增说明。

## 三类样例

[realistic_case](../draco-sympas/examples/realistic_case/README.md)包含未检查返回值、分层错误传播、跨文件调用。
每类都包含源码、显式契约、expected.json、预期 Infer/切片/检索/审查、允许误差和独立行为 oracle。
它们是接近真实场景的人工正例，不是生产缺陷或独立泛化基准。
原始行为 oracle 均退出 1；本地 guard 候选在副本中重查后均退出 0，并包含成功路径检查。

## 实际结果

完整结果见 [机器可读表](realistic-evaluation-results.json)与 [评估说明](evaluation.md)。
最终运行：draco-sympas/artifacts/realistic-evaluation/20261019T150241757954Z/。

- 3 案例 × 5 模式 = 15 次，全部保存规定的七类阶段产物，均命中该案例的规则或 native DEAD_STORE。
- B-E 预期过程和 Checker 调用点快照均找到；状态原样保留，本轮实际为 partial。
- C/D/E 的关键 callee 上下文均命中且实际进入 Prompt，3/3。
- D/E 的 JSON/schema 与原始证据引用验证均通过，3/3；E 三次真实请求均成功，实际 usage 共 15434 tokens。
- E 跨文件模型补丁通过安全检查、临时副本应用、同配置 Infer、规则和行为测试，从退出 1 到退出 0；仍为 partially_verified。
- E 另两份模型补丁的 hunk 计数错误，git apply --check 拒绝，明确为 validation_failed；未篡改或重写原始模型补丁。
- 审查引用验证和候选验证独立，不能把引用正确当作修复正确。
- 未修改输入源码。失败回执、早期实验和不调用 API 的响应重验均独立保留。

## 测试证据与独立路径限制

- 本轮初始工作区默认 pytest：67 passed、23 skipped（实际 Infer/LIVE 未启用）。
- 最终工作区启用真实 Infer 的完整 pytest：106 passed、1 skipped、13 subtests passed。
- 本轮显式 DeepSeek smoke：1 passed in 2.16s。
- 干净暂存快照全量测试：99 passed、1 failed、1 skipped、13 subtests passed。
  失败为既有 infer-sympas/evaluation/test_heap_summary.py::HeapSummaryTest::test_factory_return_and_cross_procedure_memory。
- 对比验证：当前工作树该文件 3 passed；纯 f8b6a80 基线独立快照与本轮暂存快照均为同一项 1 failed、2 passed。
  预期 return_dependencies 为 formal[0], formal[1]，实际只有 formal[0]。
  因此没有把这个既有核心路径/运行上下文敏感问题归为 Agent 引入，也没有删除测试或修改核心来掩盖。
- 干净快照 Agent 测试：70 passed、1 skipped；同一快照的真实 Infer + Mock CLI Demo 成功，候选部分验证。
  这不能称为干净快照全量通过。

主要命令：

```bash
./draco-sympas/.venv/bin/python -m pytest -q
INFER_BIN=/absolute/path/to/infer ./draco-sympas/.venv/bin/python -m pytest -q
INFER_BIN=/absolute/path/to/infer ./draco-sympas/.venv/bin/python -m pytest -q draco-sympas/tests
RUN_DEEPSEEK_LIVE=1 ./draco-sympas/.venv/bin/python -m pytest -q draco-sympas/tests/test_deepseek_live.py
```

本机完整暂存快照日志：/tmp/realistic-stage-staged-verification.json；Agent 单独回执：/tmp/realistic-stage-agent-verification.json。
临时目录不是长期产物；本文件保留准确范围和失败事实，未把它们提升为全新环境完整复现成功。

## 要求逐项核对

| 要求 | 当前可检查依据 |
|---|---|
| 不修改 SymPas/DRaCo 核心 | 暂存文件清单仅 Agent、样例、测试、文档；infer-sympas 和 context/repository.py 不在改动中 |
| 三类独立样例与预期 | 三目录 expected.json、contracts.json、源码、tests/driver.c 和 check.py |
| partial/complete 兼容 | 原样转发 adapter 状态；test_partial_and_complete_slice_compatibility 覆盖两者 |
| 每案例完整流程 | 15 个运行目录的七种产物及 run.json；Mock/DeepSeek 各 3 案例实际运行 |
| 证据可追溯 | 原始 Infer、切片、索引、检索、规则、源码 hash 检查；D/E 各 3/3 |
| 安全候选重验 | repair_validation.py、原始 patch、patch_check/apply、独立 workspace、before/after tests、Infer、规则比较 |
| 五模式与真实指标 | evaluate_realistic.py 和 realistic-evaluation-results.json；A 不含本地规则，B-E native+SymPas，相应混杂条件明确 |
| 十类失败 | test_failure_still_generates_full_agent_report、已有 Provider timeout/重试测试、adapter 状态测试、候选安全/行为/应用失败测试 |
| 预算和检索失败可解释 | dropped、stage_notes、阶段状态；新增预算回归防止大块 SIL 挤掉 callee；完整 SIL 另存 |
| 无默认 API 调用 | 默认 E 为 not_run，LIVE 测试 skip；显式 --live-deepseek / RUN_DEEPSEEK_LIVE 才调用 |
| 文档与 Demo | README、quickstart、architecture、evaluation、limitations 和样例 README |
| 无秘密提交/不覆盖并行修改 | .env 忽略，暂存内容实际密钥及凭据模式扫描；仅按精确文件清单提交，无 reset/强制操作 |

## 当前限制与下一步

仍是研究型 MVP。三个正例不足以证明准确率提升或普遍泛化，所有模式已检测到它们。
候选只支持已声明的返回值 guard 子集；不会执行模型提供的命令，也不承诺自动修复正确。
独立路径下的既有核心堆摘要测试失败需要 SymPas 对话单独处理；本轮保留边界不修改核心。
下一步优先加入独立真实项目与负对照，再扩大行为 oracle；不要用 Mock 或少量正例替代模型质量评估。
