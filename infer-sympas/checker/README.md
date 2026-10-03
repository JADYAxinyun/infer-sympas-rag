# SymPas checker

当前实现是第二阶段的 Infer 内部原型。

- 入口：`sympas.ml`
- 启用方式：`infer --sympas ...`
- 当前功能：以函数返回变量为起点，在反向 SIL 控制流图中追踪数据依赖；处理 `Load` 与局部变量 `Store` 指令。
- 已验证：`return y` 会追踪到参数 `x`；无关的 `unused = 100` 不会进入依赖集合。
- 尚未实现：切片语句位置集合、控制依赖、跨函数摘要、符号条件。

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

预期报告包含：

```text
SymPas backward dependencies of the return value: { x }
```
