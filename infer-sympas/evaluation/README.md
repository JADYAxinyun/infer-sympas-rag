# Evaluation labels

`ground_truth.template.json` 是人工标注模板，不是预填的实验结果。正式评测时，为每个函数复制一份并由人工确认：

- 哪些语句必须进入返回值切片；
- 哪些分支条件控制切片结果；
- 每条语句属于数据依赖还是控制依赖；
- 是否存在无法从源码确定的边界情况。

标注完成后，才能计算 Precision、Recall 和 F1。
