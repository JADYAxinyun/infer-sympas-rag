# 初步评测结果

当前已完成 3 组人工标注用例：

| 场景 | 标注位置数 | Precision | Recall | F1 |
|---|---:|---:|---:|---:|
| 简单数据依赖 | 2 | 1.0000 | 1.0000 | 1.0000 |
| 条件控制依赖 | 3 | 1.0000 | 1.0000 | 1.0000 |
| 跨过程调用摘要 | 3 | 1.0000 | 1.0000 | 1.0000 |
| 合计 | 8 | 1.0000 | 1.0000 | 1.0000 |

运行命令：

```bash
cd /Users/jadya/Documents/GitHub/desktop-tutorial
python3 infer-sympas/tools/evaluate_all.py \
  infer-sympas/evaluation/data_dependency.truth.json \
  infer-sympas/tests/intraprocedural/sympas-out-data/report.json \
  infer-sympas/evaluation/conditional_return.truth.json \
  infer-sympas/tests/control_dependency/sympas-out-cond/report.json \
  infer-sympas/evaluation/call_summary.truth.json \
  infer-sympas/tests/interprocedural/sympas-out-call/report.json
```

## 解读边界

这只是可复现的冒烟评测，不是论文级结论：样本很小、程序很短，尚未覆盖复杂别名、堆对象、异常路径、循环固定点和大型真实项目。因此不能据此宣称整体准确率为 100%。
