# SymPas 测试矩阵

测试入口是 `run_sympas_tests.sh`。脚本使用构建后的自定义 Infer，对每个 C 文件执行 capture、analyze 和 report，并检查关键输出。

| 类别 | 覆盖内容 | 数量 |
|---|---|---:|
| 数据依赖 | 局部变量、字段、数组、全局变量、指针、堆字段、别名、多级指针 | 8 |
| 控制依赖 | 条件返回、嵌套条件、循环返回、无关分支 | 4 |
| 跨过程 | 普通调用、递归、互递归 | 3 |

## 运行

```bash
cd /Users/jadya/Documents/GitHub/desktop-tutorial
infer-sympas/tests/run_sympas_tests.sh
```

脚本会检查 `frontier`、`slice_locations`、`path_conditions`、控制位置和跨过程摘要。测试产生的 `sympas-out-ci/` 是临时 Infer 结果，不应提交到 Git。
