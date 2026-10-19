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

## 二轮 Agent 验收（2026-10-19）

基线：`c89c01e`（本地与 origin/main 当时一致）。本轮只修改 Agent、配置入口、测试与文档，
没有修改 infer-sympas 的核心算法、SIL/CFG、摘要、SCC 或依赖实现。
其他对话在共享工作区产生的 Checker、文档、补丁与测试修改均留在其原位，未纳入本轮暂存。

### 实际补齐

- 新增 SymPasAdapter → SliceResult，兼容 analysis_status/status，保留 raw_slice 和 partial。
- 原始引用对照：Infer report、Checker slice、索引、检索记录、本地规则与源码 hash。
- 拒绝已知 ID 的内容篡改、未知 ID、无效位置、源码变化及只有切片/上下文却确认缺陷的模型结论。
- 传输成功和 JSON/schema 成功分开为 llm.status / llm.parse_status；原始响应保留。
- Markdown 直接展示 Infer、SymPas、DRaCo、slice_status、模型引用、验证及候选复查。
- 新增被跟踪的跨文件 examples/agent_demo；原有 Demo/API 不改写。
- --env-file 显式加载本机 DeepSeek 配置；仅 live 显式开启时测试读取根目录 .env。
- pytest.ini 只收集项目测试，避免执行 third_party/ReccEval 中作为数据的第三方测试。

### 验证与回执

1. 初始 Agent 测试：46 passed、2 skipped；初始根目录 pytest 误收集第三方测试而失败。
2. 修正收集后默认离线测试通过；带真实 Infer 的当轮完整工作区测试：81 passed、1 skipped、9 subtests passed。
3. **本次仅暂存内容的独立快照：71 passed、1 skipped**，不依赖其他对话未提交文件。
4. 同一独立快照：真实 Infer + Mock、none 均成功；缺 Key 的 deepseek 明确返回 configuration_error，CLI 退出码 2。
5. 当前跨文件真实 Infer + Mock Demo：4 条分析器输出记录（切片/候选不是漏洞），2 个 partial 切片，2 个检索片段，1 条本地规则 finding。
6. 模型引用 9 个实际证据 ID，9 项原始产物/来源检查全部通过；evidence.status=verified，整体仍为 partially_verified。
7. JSON、Markdown、slices.json、rules.json、Prompt 与全部中间产物正常生成；候选修复不应用到源代码。
8. 真实 DeepSeek 已按用户授权调用，**FAILED / HTTP 401**。这不是 NOT_RUN，也不是成功。
   `.env` 已被读取，Python 与 curl 的官方只读 /models 认证探测均失败；服务端归类 authentication_error / invalid_key。
   不把本地格式正常解释为服务端认证成功；不保存密钥或 Authorization headers。

已执行命令：

```bash
./draco-sympas/.venv/bin/python -m pytest -q
INFER_BIN=/absolute/path/to/infer ./draco-sympas/.venv/bin/python -m pytest -q
INFER_BIN=/absolute/path/to/infer ./draco-sympas/.venv/bin/python draco-sympas/cli.py review \
  --repo draco-sympas/examples/agent_demo --llm-provider mock
./draco-sympas/.venv/bin/python draco-sympas/cli.py review \
  --repo draco-sympas/examples/agent_demo --infer-mode off --llm-provider none
RUN_DEEPSEEK_LIVE=1 ./draco-sympas/.venv/bin/python -m pytest -q \
  draco-sympas/tests/test_deepseek_live.py
```

本机回执：

- `artifacts/agent/20261019T075655348831Z/`：本轮真实 Infer + Mock 完整报告。
- `artifacts/agent/20261019T075658166756Z/`：none 模式。
- `artifacts/deepseek-live-20261019-01/test_live_deepseek_json0/deepseek-receipt.json`：真实 API 的 401 失败回执，不含 Key。
- `/tmp/agent-followup-staged-verification.json`：独立暂存快照、测试及 CLI 退出码记录。

上述 artifacts 路径均相对于 draco-sympas/，默认被 Git 忽略；本记录持久化范围与结论。
下一步先解决 DeepSeek 服务端认证，再显式运行 live smoke 和 DeepSeek 全链路；
当前完成的是可验证的 Mock 闭环与真实 API 失败路径，不宣称真实模型效果或完整 SymPas 复现。

### 最新真实 DeepSeek 成功回执（同日更新）

用户替换并保存新的官方 Key 后，认证成功；前述 401 记录保留为历史失败路径。
本节是当前最新 API 状态：**LIVE PASSED**。

- 官方只读 /models：HTTP 200，可用模型含 deepseek-flash。
- 显式 RUN_DEEPSEEK_LIVE=1 测试：**1 passed in 2.28s**，一次请求成功。
- Smoke 原始响应与 usage 已保存；实际 usage 为输入 258、输出 244、总计 502 tokens。
- 真实 Infer + DeepSeek 全链路：Infer ok，slice_status partial，LLM ok，parse_status ok。
- 模型结论 likely，引用 5 条实际证据；原始产物/源码验证 verified，errors=[]。
- 整体 validation 仍为 partially_verified；真实 API 成功不提升切片精度或候选修复证据级别。
- 全链路实际 usage：输入 4201、输出 4569（含 reasoning 4154）、总计 8770 tokens。
- 本轮 API smoke 与全链路合计记录 9272 tokens；不是费用估算或一般性能指标。
- Key 留在本机 .env，被 Git 忽略；未进入命令参数、报告、提交或日志。

本机产物：

- `draco-sympas/artifacts/deepseek-live-20261019T080228273846Z/test_live_deepseek_json0/deepseek-receipt.json`
- `draco-sympas/artifacts/agent/20261019T080244484138Z/run.json`
- `draco-sympas/artifacts/agent/20261019T080244484138Z/review.md`

可复现命令：

```bash
RUN_DEEPSEEK_LIVE=1 ./draco-sympas/.venv/bin/python -m pytest -q draco-sympas/tests/test_deepseek_live.py
INFER_BIN=/absolute/path/to/infer ./draco-sympas/.venv/bin/python draco-sympas/cli.py review \
  --repo draco-sympas/examples/agent_demo --env-file .env --llm-provider deepseek
```

不再需要为当前 Key 继续认证排障；后续扩大独立真实项目标签及行为验证。
