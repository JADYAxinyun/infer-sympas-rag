# 跨函数摘要阶段

当前 checker 已能在调用点把实参加入 caller 的切片，但这还不是完整的跨函数分析。

## 目标

为每个 callee 生成一个摘要：

```text
callee 返回值 -> 哪些形参、全局变量和控制条件
```

在 caller 遇到调用时，通过实参与形参的映射实例化摘要：

```text
callee.formal[0] -> caller.a
```

## Infer 接入点

1. 新建 `SymPasDomain`，定义可序列化的 summary 类型。
2. 在 `Payloads` 增加 `sympas` payload field。
3. 将 checker 注册从 `intraprocedural` 改为 `interprocedural`。
4. 在 `Sil.Call` 中调用 `analyze_dependency callee` 获取 summary。
5. 用 actual/formal 映射替换 summary 中的形参。
6. 只有摘要可用时才跨过程传播；不可用时保留当前调用点实参传播作为保守回退。

## 当前验证边界

`tests/interprocedural/call_summary.c` 已验证调用点传播，但尚未声称完成论文意义上的函数摘要。

## 已完成的准备工作

已加入 `SymPasDomain` 摘要类型，支持两类跨函数依赖：`Formal index` 和 `Global name`。下一步是把该类型接入 Infer 的 `Payloads` 数据库字段，再让 checker 返回和消费该摘要。

已将 `SymPas` 摘要字段加入 Infer 的 `PayloadId` 与 `Payloads` 结构，并验证 Infer 可以重新构建。checker 仍暂时保持过程内注册，避免在摘要生成逻辑完成前改变分析调度。
