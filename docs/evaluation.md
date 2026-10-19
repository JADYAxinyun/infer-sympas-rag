# Prototype smoke evaluation

本轮运行日期：2026-10-19。4 个构造 C 案例 × 4 模式，共 16 次运行；不使用真实 LLM。
案例包含：人工契约未检查、人工契约已检查、未知数值 API、未知负返回值 API。
源码由评估脚本显式构造，不以工具结果自动生成标签；真值仍只是作者设定。

```bash
INFER_BIN=/absolute/path/to/infer \
  ./draco-sympas/.venv/bin/python draco-sympas/evaluation/evaluate_agent.py
```

默认新建带时间戳目录；`--output` 可指定不存在的目录。
每个案例/模式保留独立 run、完整原始 Infer 报告、Prompt 和检索轨迹；不覆盖历史评估。

| 模式 | 程序分析 | 检索 | LLM |
|---|---|---|---|
| A_text | 无 Infer/SIL 切片；保留相同本地规则 | 函数源码符号与查询的词集合重合 | Mock |
| B_relations | 无 Infer/SIL 切片；保留相同本地规则 | AST 程序关系 | Mock |
| C_infer_slice | 真实 Infer/SIL + 本地规则 | 关闭 | none |
| D_full_mock | 真实 Infer/SIL + 本地规则 | AST 程序关系 | Mock |

## 本轮结果

记录目录：`draco-sympas/artifacts/agent-evaluation/20261019T070018356714Z/`。

| 模式 | 错误报告 | 漏报 | 相关上下文命中率 | JSON 解析成功率 | 平均耗时 ms |
|---|---:|---:|---:|---:|---:|
| A_text | 0 | 1 | 1.00 | 1.00 | 71.20 |
| B_relations | 0 | 1 | 1.00 | 1.00 | 64.92 |
| C_infer_slice | 0 | 0 | 不适用 | 不适用 | 996.36 |
| D_full_mock | 0 | 0 | 1.00 | 1.00 | 1085.44 |

在这个极小仓库中，文本检索和关系检索都命中了被调用函数，不能据此宣称关系检索质量优于文本检索。
A/B 漏报来自没有显式契约的未知负返回值 API；C/D 命中来自 Infer medium 候选，仍需人工确认契约。
这些结果不证明真实项目缺陷检测能力，也没有测量 DeepSeek 的语义判断准确率。

## 指标定义

- evidence_coverage：实际 Prompt 保留的证据条数 / 注册证据条数。本轮均为 1；这只是装载比例，不是语义证据完整性。
- related_context_hit：从 caller.c 发起的查询是否取回 helper.c 中标注的被调用函数。排除 helper 检索到自身的情况。
- false_reports / missed_reports：规则输出数量与构造案例标签比较，不能当作真实缺陷真值基准。
- evidence_insufficient：成功解析模型响应中该状态的比例。A/B 为 0.75，D 为 0.50；C 为 null。Mock 的比例由规则是否有输出决定，不代表模型能力。
- json_parse_success：成功解析并符合 schema 的响应 / 实际返回的模型响应。C 未运行 LLM，分母为空记 null。
- rule_validation_pass：有候选修复时，规则发现数是否下降；本轮可用候选均下降。无候选记 null。不能解释为修复正确率。
- elapsed_ms：本机端到端耗时，包括索引、分析、候选复查；仅为单次 smoke 时间。
- token_usage：Mock/none 为 null；prompt_token_upper_bound 为单独记录的字节上界，绝非实际计费 token。
- api_status：四组均为 not_run。真实 API 单独显式测试，不混入离线对比。

## 测试边界

本轮在当前工作树通过原有测试、新增单元与集成测试，以及真实 SIL 准则/摘要缓存测试。
DeepSeek 使用 HTTP 模拟测试覆盖 Key 缺失、请求格式、超时、重试、401、畸形响应及原始响应保存。
真实 DeepSeek 测试由于未配置 Key 保持 NOT_RUN，默认 pytest 会跳过；显式开启命令见 quickstart。
本地 CodeGen 本轮未下载或运行。

## 三类接近真实场景的五组验证（2026-10-19）

本轮为 **small-scale prototype evaluation**：3 个构造正例 × 5 个模式，共 15 次。
源码、独立预期和行为 oracle 见 [样例说明](../draco-sympas/examples/realistic_case/README.md)。
完整机器可读汇总见 [realistic-evaluation-results.json](realistic-evaluation-results.json)。

| 模式 | 实际发现 | 预期切片 | 关键上下文实际入 Prompt | JSON/引用有效 | 候选结果 |
|---|---:|---:|---:|---:|---|
| A Infer only | 3/3 | 不运行 | 不运行 | 不运行 | 不生成 |
| B Infer + SymPas + 本地规则 | 3/3 | 3/3 | 不运行 | 不运行 | 本地候选 3/3 部分验证 |
| C 再加 DRaCo | 3/3 | 3/3 | 3/3 | 不运行 | 本地候选 3/3 部分验证 |
| D 再加 Mock | 3/3 | 3/3 | 3/3 | 3/3 | 本地候选 3/3 部分验证 |
| E 再加 DeepSeek | 3/3 | 3/3 | 3/3 | 3/3 | 模型候选 1 个部分验证，2 个应用失败 |

A 的发现是 native Infer DEAD_STORE，不等于已独立证明 API 错误契约。
B-E 同时使用 native Infer 和 SymPas，并启用同一显式本地契约规则。
全部模式已命中这三个简单正例，因此没有证据表明添加 LLM 提高了检测准确率。
A/B 还涉及规则策略差异，不能把差异单独归因于切片。不存在普遍泛化或论文级结论。

最终运行目录：`draco-sympas/artifacts/realistic-evaluation/20261019T150241757954Z/`。
E 三次真实调用均成功，JSON 和引用都有效，共计 15434 个实际 API tokens。
跨文件模型补丁通过应用、同配置 Infer、规则及行为复查，行为退出码从 1 变为 0；仍为 partially_verified。
另外两个模型补丁的 hunk 计数错误，被 git apply --check 拒绝，标为 validation_failed；不静默修正模型文本。
审查引用验证与候选验证分列，不能用引用有效替代修复成功。

### 复现

```bash
export INFER_BIN=/absolute/path/to/infer
./draco-sympas/.venv/bin/python draco-sympas/evaluation/evaluate_realistic.py
./draco-sympas/.venv/bin/python draco-sympas/evaluation/evaluate_realistic.py \
  --live-deepseek --env-file .env
```

默认 A-D 执行，E 为 not_run；--live-deepseek 显式开启费用和网络。
对已有 E 响应重验补丁（不会重新调用 API或覆盖原始报告）：

```bash
./draco-sympas/.venv/bin/python draco-sympas/evaluation/evaluate_realistic.py \
  --revalidate /absolute/path/to/evaluation-run
```

每行记录检测、切片、检索命中、Prompt 实际装载、引用、JSON、审查/候选验证、耗时、API 状态和真实 usage。
各阶段产物按运行目录保存，模型波动可能改变结论或 patch，不能把固定一次结果当作恒定指标。
早期运行和失败回执保留；最终结果修复了预算挤掉关键上下文的问题。
