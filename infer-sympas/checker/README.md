# SymPas checker

当前实现是第一阶段的 Infer 内部原型。

- 入口：`sympas.ml`
- 启用方式：`infer --sympas ...`
- 当前功能：遍历 C 函数的 SIL 指令，收集读取到的临时变量，并作为 `SYMPAS_SLICE` 信息报告输出。
- 尚未实现：从 `return` 反向切片、控制依赖、跨函数摘要。

## 验证命令

```bash
/Users/jadya/Documents/GitHub/infer-sympas-infer/infer/bin/infer \
  --sympas --results-dir sympas-out \
  capture -- clang -c data_dependency.c
/Users/jadya/Documents/GitHub/infer-sympas-infer/infer/bin/infer \
  --sympas --results-dir sympas-out analyze
/Users/jadya/Documents/GitHub/infer-sympas-infer/infer/bin/infer \
  --sympas --results-dir sympas-out report
```
