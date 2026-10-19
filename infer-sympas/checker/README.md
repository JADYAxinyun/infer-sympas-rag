# SymPas SIL Checker

这里保存可审阅的 OCaml 源码副本。构建需要使用完整集成补丁，不能只复制
单个 `sympas.ml`；见 [构建与验证](../docs/build-and-verify.md)。

- `sympas.ml`：入口、兼容的返回值反向切片及 JSON 输出。
- `SymPasSymbolic.ml`：前向符号依赖、指令快照、调用点实例化、输出内存和返回别名。
- `SymPasDomain.*`：形参值、形参内存、全局依赖、来源和过程输出摘要。
- `SymPasControlDependence.*`：CFG 后支配关系，用于限定控制影响。

持久化摘要由 Infer Payloads 保存；调用通过 `analyze_dependency` 请求摘要。
简单局部别名可确定；形参可能别名、多个目标、折叠字段/数组和未知写入采用
保守近似。递归及互递归用例有终止/依赖断言，尚未证明论文 SCC 最小固定点语义。

本实现保留 `partial` / `conservative` 状态，完整限制见
[验收证据](../docs/acceptance-evidence.md)。
