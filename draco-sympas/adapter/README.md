# SymPas → DRaCo 适配器

适配器读取 Infer `report.json` 和 DRaCo Prompt JSONL，按文件名匹配后追加 `dependency frontier`、`path conditions`、`callee summary` 静态事实。

```bash
python draco-sympas/adapter/sympas_to_draco.py \
  draco-sympas/artifacts/draco-prompts.jsonl \
  path/to/sympas/report.json \
  draco-sympas/artifacts/draco-prompts-sympas.jsonl
```

当前版本验证格式和拼接流程；由于 ReccEval 是 Python、Infer-SymPas 测试主要是 C，跨语言样本对应仍需后续处理。
