# Local generation

使用 CodeGen 350M 对增强 Prompt 进行本地代码补全：

```bash
source draco-sympas/.venv/bin/activate
python draco-sympas/generation/generate_local.py \
  --prompts draco-sympas/artifacts/draco-prompts-sympas.jsonl \
  --output draco-sympas/artifacts/completions.jsonl \
  --limit 1
```

已在 Apple Silicon MPS 上完成 1 条样本推理。模型缓存约 764 MB。批量运行前应先用较小的 `--limit` 评估时间和生成质量。

评测小批量结果：

```bash
python draco-sympas/generation/evaluate_completions.py \
  third_party/draco-upstream/ReccEval/metadata.jsonl \
  draco-sympas/artifacts/completions-10.jsonl
```
