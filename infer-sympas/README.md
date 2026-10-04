# Infer-SymPas

这是一个将 SymPas 的核心思想适配到 Infer SIL 的实验性实现：以函数返回值为切片准则，反向追踪数据依赖、路径条件和控制位置，并通过 Infer 的跨过程摘要继续传播。

> 当前定位：SymPas 风格的 Infer 原型，不声称是论文实现的逐行复刻。

## 目录

- `checker/`：OCaml checker、抽象域和控制依赖模块。
- `configs/`：实验配置说明。
- `tests/`：数据依赖、控制依赖和跨过程测试。
- `docs/`：跨过程摘要设计与复现状态。
- `patches/`：从 Infer 源码构建该原型所需的补丁记录。

## 快速验证

```bash
cd /Users/jadya/Documents/GitHub/desktop-tutorial
make -C /Users/jadya/Documents/GitHub/infer-sympas-infer infer
infer-sympas/tests/run_sympas_tests.sh
```

## 输出内容

报告中的 `SYMPAS_SLICE` 会包含：

- `frontier`：返回值依赖到的变量；
- `slice_locations`：相关赋值、调用和分支位置；
- `path_conditions`：切片过程中遇到的分支条件；
- `candidate summary`：可供调用者使用的 `formal[i]` 摘要；
- `precise control locations`：基于后支配关系或保守回退得到的控制位置。

## 当前边界

完整论文复现还需要更严格的路径条件语义、复杂别名与堆对象建模、固定点收敛实验，以及论文数据集上的 Precision/Recall 和性能评估。详见 [`docs/reproduction-status.md`](docs/reproduction-status.md)。
