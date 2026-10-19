# 可复现运行

从仓库根目录运行。基础流程仅依赖 Python 3.10+ 标准库；C 索引与语法检查需要 clang。
本地测试需要 pytest；CodeGen 是额外可选功能，才需要 torch/transformers 与模型缓存。

```bash
python3 -m venv draco-sympas/.venv
./draco-sympas/.venv/bin/python -m pip install pytest
```

已有虚拟环境可直接使用，不需要重新创建。真实切片需要按
[infer-sympas 构建说明](../infer-sympas/docs/build-and-verify.md) 准备带 Checker 的 Infer：

```bash
export INFER_BIN=/absolute/path/to/infer
```

## 无网络 Mock / none

以下目录必须不存在；重复运行时改用新目录，或省略 `--output` 自动生成时间目录。
Mock Infer 模式不虚构分析结果：Infer 状态为 mock，切片为 not_analyzed。

```bash
./draco-sympas/.venv/bin/python draco-sympas/cli.py index \
  --repo draco-sympas/examples --output /tmp/review-index.json
./draco-sympas/.venv/bin/python draco-sympas/cli.py review \
  --repo draco-sympas/examples --target-file unchecked_return.c \
  --infer-mode mock --llm-provider mock --output /tmp/review-mock
./draco-sympas/.venv/bin/python draco-sympas/cli.py review \
  --repo draco-sympas/examples --target-file unchecked_return.c \
  --infer-mode off --llm-provider none --output /tmp/review-none
```

## 真实 Infer + Mock LLM 完整接线

```bash
./draco-sympas/.venv/bin/python draco-sympas/cli.py review \
  --repo draco-sympas/examples --target-file unchecked_return.c \
  --infer-mode real --llm-provider mock --output /tmp/review-infer-mock
```

真实 Infer 缺失或失败时保存明确失败状态，CLI 返回非零退出码；不会改用 Mock 冒充成功。
默认 Infer 为 real，默认 LLM 为 none。也可通过 `--infer-bin` 显式指定可执行文件。
多文件可重复提供 `--target-file`，各编译单元一起交给 clang；当前不自动推断项目构建参数。

## DeepSeek（显式网络与费用）

从环境中读取凭据，不会自动加载 `.env`，不打印或记录 API Key。
`.env.example` 仅示意，不可把真实 Key 填入并提交。
模型名称及接口以 [DeepSeek 官方文档](https://api-docs.deepseek.com/) 为准；2026-10-19 核验支持 `deepseek-flash`。

```bash
export DEEPSEEK_API_KEY='your-api-key'
export DEEPSEEK_MODEL='deepseek-flash'
./draco-sympas/.venv/bin/python draco-sympas/cli.py review \
  --repo draco-sympas/examples --target-file unchecked_return.c \
  --llm-provider deepseek --model deepseek-flash
```

请求 `https://api.deepseek.com/chat/completions`，temperature=0，JSON object 输出。
Provider 默认每次请求 30 秒超时，最多重试两次；只重试网络错误、429 与 5xx。
缺 Key 为 configuration_error，401 不重试；HTTP 错误不保存 headers 或潜在敏感错误正文。
成功响应保留 raw_envelope / raw_response / usage；无效 JSON 留下 schema_errors。
local 模式复用 CodeGen，并提供相同证据说明；CodeGen 未经 JSON 指令微调，输出可能无法通过验证。

## Python 与报告接口

```python
import sys
sys.path.insert(0, 'draco-sympas')
from agent import ReviewAgent
result = ReviewAgent().review(
    repo_path='draco-sympas/examples', target_files=['unchecked_return.c'],
    rule='unchecked_return_value', llm_provider='mock', infer_mode='mock',
)
```

```bash
./draco-sympas/.venv/bin/python draco-sympas/cli.py report \
  --input /tmp/review-mock/run.json --format markdown --output /tmp/review-export.md
```

`--diff /path/to/change.diff` 提供 Git Diff；否则读取 `git diff HEAD`。
显式 target 优先，未指定则审查索引支持的仓库文件；diff 用于上下文，不隐式只审查新增行。
旧 `run_pipeline.py`、`examples/run_e2e_demo.py` 与 API 命令仍保留。

## 验证

```bash
./draco-sympas/.venv/bin/python -m pytest -q draco-sympas/tests
INFER_BIN=/absolute/path/to/infer ./draco-sympas/.venv/bin/python -m pytest -q \
  draco-sympas/tests infer-sympas/evaluation/test_query_slice.py \
  infer-sympas/evaluation/test_summary_cache.py
RUN_DEEPSEEK_LIVE=1 ./draco-sympas/.venv/bin/python -m pytest -q \
  draco-sympas/tests/test_deepseek_live.py
```

最后一条才允许调用真实 API，并要求环境中有 Key。默认 pytest 不会调用 DeepSeek。
