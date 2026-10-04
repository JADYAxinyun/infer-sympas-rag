# SymPas 复现状态

本项目当前是基于 Infer 的 **SymPas 风格跨过程程序切片原型**，不是论文实现的逐行复刻。

## 已实现

- 以函数返回值为切片准则的反向数据依赖分析
- 局部变量、临时变量和表达式依赖
- 结构体字段、数组下标、指针解引用与多级指针
- 全局变量依赖
- 调用点依赖与被调用函数摘要传播
- 递归调用回归测试
- 基于后支配关系的控制依赖候选定位
- 将切片结果转换为 Infer 的结构化摘要并写回跨过程分析

## 当前测试覆盖

测试脚本：`infer-sympas/tests/run_sympas_tests.sh`

- 8 个数据依赖场景
- 4 个控制依赖场景
- 2 个跨过程场景（普通调用、递归调用）

## 与完整 SymPas 仍有差距

1. 控制依赖仍采用保守近似，尚未覆盖论文中的全部路径条件语义。
2. 递归和循环调用尚未用论文级固定点实验充分验证。
3. 复杂别名、堆对象和异常路径仍需要更多系统测试。
4. 尚未复现论文数据集、人工标注、Precision/Recall 和性能评估。

## 验证命令

```bash
cd /Users/jadya/Documents/GitHub/desktop-tutorial
make -C /Users/jadya/Documents/GitHub/infer-sympas-infer infer
infer-sympas/tests/run_sympas_tests.sh
```
