# SymPas checker

当前实现是一个基于 Infer 的 **SymPas 风格跨过程程序切片原型**，不是论文实现的逐行复刻。

- 入口：`sympas.ml`
- 启用方式：`infer --sympas ...`
- 切片准则：以函数返回变量为起点，在反向 SIL 控制流图中追踪依赖。
- 数据依赖：支持局部变量、表达式、结构体字段、数组下标、指针解引用、多级指针和全局变量。
- 控制信息：记录分支条件、条件变量和相关源代码位置，并使用后支配关系计算控制依赖候选。
- 跨过程：通过 Infer 的 `analyze_dependency` 获取被调用函数摘要，将 `formal[i]` 映射回调用实参，并写回结构化摘要。
- 递归覆盖：测试包含普通调用、递归调用和互递归调用。

## 验证命令

```bash
cd /Users/jadya/Documents/GitHub/desktop-tutorial
make -C /Users/jadya/Documents/GitHub/infer-sympas-infer infer
infer-sympas/tests/run_sympas_tests.sh
```

测试脚本覆盖数据依赖、控制依赖和跨过程摘要，并检查报告中的 `frontier`、切片位置和 `path_conditions`。

## 与论文实现的差距

当前仍未完成论文级的完整路径条件语义、复杂别名/堆对象建模、固定点收敛实验，以及原始数据集上的 Precision/Recall 和性能评估。
