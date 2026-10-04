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

该命令要求先生成 `artifacts/draco-prompts.jsonl`，然后自动生成 SymPas 增强 Prompt。

## 当前状态

- 已接入 DRaCo 官方仓库作为上游依赖；
- 尚未修改 DRaCo 原始代码；
- 下一步实现 `sympas_adapter`，把 Infer 的 `report.json` 转换为 DRaCo 可消费的代码上下文；
- 集成实验将比较 `DRaCo` 与 `SymPas Slice + DRaCo`。

## 目录规划

```text
 draco-sympas/
 ├── adapter/       # SymPas JSON 到 DRaCo 上下文的转换
 ├── context/       # 切片与检索结果合并
 ├── experiments/   # 对比实验
 └── README.md
```
