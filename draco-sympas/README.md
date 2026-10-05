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
