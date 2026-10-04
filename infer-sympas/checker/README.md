# SymPas checker

当前实现是一个**过程内返回值数据依赖切片原型**，不是完整 SymPas 复现。

- 入口：`sympas.ml`
- 启用方式：`infer --sympas ...`
- 当前功能：以函数返回变量为起点，在反向 SIL 控制流图中追踪数据依赖；处理 `Load` 与局部变量 `Store` 指令。
- 已验证：`return y` 会追踪到参数 `x`；同时报告相关 `Store` 的源代码位置（示例中为第 3、4 行）；无关的 `unused = 100` 不会进入切片。
- 尚未实现：控制依赖、跨函数摘要、符号条件。

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
SymPas backward dependencies of the return value:
{frontier={ x }; slice_locations={ line 3, column 5, line 4, column 5 }}
```
