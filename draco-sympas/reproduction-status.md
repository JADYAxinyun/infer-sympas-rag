# DRaCo 复现状态

已完成官方 DRaCo 上游代码接入和本地预处理：

- 官方仓库：`third_party/draco-upstream/`
- ReccEval 数据集：已解压到上游 `ReccEval/Source_Code/`
- 仓库数量：2635
- 已生成仓库级上下文图：`ReccEval/Graph/`
- 上下文图数量：2635
- 图数据约占 522 MB，属于本地生成产物，不提交到本仓库

预处理命令：

```bash
cd third_party/draco-upstream/src
../../../draco-sympas/.venv/bin/python preprocess.py
```

当前尚未完成模型推理和论文指标复现。下一步是在不下载大型本地代码模型的情况下，先检查 `main.py` 的 Prompt 生成路径，再接入 Infer-SymPas 的 `report.json`。
