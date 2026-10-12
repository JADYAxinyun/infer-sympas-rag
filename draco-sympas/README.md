# DRaCo + SymPas

本目录用于维护 DRaCo 与当前 Infer-SymPas 原型的集成工作。

## 上游代码

DRaCo 通过 Git submodule 固定在：

```text
third_party/draco-upstream/
```

初始化或更新：

```bash
git submodule update --init --recursive
```

## 一键运行

```bash
python draco-sympas/run_pipeline.py
```

## 端到端代码审查演示

使用一个 C 返回值未检查样例运行“切片 → 规则审查 → 本地 LLM 解释”，需要使用项目虚拟环境：

```bash
INFER_BIN=/Users/jadya/Documents/GitHub/infer-sympas-infer/infer/bin/infer \
  ./draco-sympas/.venv/bin/python draco-sympas/examples/run_e2e_demo.py
```

报告会写入 `draco-sympas/artifacts/e2e-unchecked-return.json`。该演示中的 Infer 验证结果仍需通过
`INFER_BIN` 指向带有 SymPas Checker 的 Infer 构建；如果不设置，则尝试使用 PATH 中的 `infer`。

报告同时保留原始分析字段，并提供稳定的 `structured_report` 字段：`problem`、`evidence`、`slice`、
`llm_explanation`、`suggestion` 和 `verification`，便于 UI 展示和后续评测。

## 最小 API 演示

当前先提供无第三方依赖的切片 API，方便后续接入 UI：

```bash
python draco-sympas/api_server.py
curl http://127.0.0.1:8765/health
curl -X POST http://127.0.0.1:8765/slice \\
  -H 'Content-Type: application/json' \\
  -d '{"source":"def f(x):\\n    y = x + 1\\n    return y"}'
```

浏览器演示界面：启动服务后访问 `http://127.0.0.1:8765/`。

## 第一条审查规则

当前闭环优先验证“函数返回值是否被检查”：系统报告问题行、被调用函数、返回值变量和修复建议。运行测试：

```bash
python -m pytest draco-sympas/tests/test_review.py
```

统一分析接口：`POST /analyze`。请求体至少包含 `source`，也可附加 `infer_report`；返回切片、审查和 Infer 三部分结果。

该命令要求先生成 `artifacts/draco-prompts.jsonl`，然后自动生成 SymPas 增强 Prompt。

## 当前状态

- 已接入 DRaCo 官方仓库作为上游依赖；
- 不修改 DRaCo 原始代码，通过适配器生成增强 Prompt；
- 已完成 ReccEval 的 Python 程序切片上下文注入，并保留原始代码前缀作为 Prompt 末尾，避免模型继续生成静态事实；
- 集成实验比较 `DRaCo` 与 `SymPas Slice + DRaCo`，当前本地 CodeGen 仅完成小样本流程验证，指标仍待正式评估。

## 目录规划

```text
 draco-sympas/
 ├── adapter/       # SymPas JSON 到 DRaCo 上下文的转换
 ├── context/       # 切片与检索结果合并
 ├── experiments/   # 对比实验
 └── README.md
```
