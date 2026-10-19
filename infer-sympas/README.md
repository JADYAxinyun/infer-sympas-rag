# Infer-SymPas

基于 Infer SIL/CFG 的 SymPas 风格跨过程切片实现，参考 Zhang (JCST 2021)
的符号输入、过程输出摘要和调用点替换。当前仍是研究原型，边界见验收文档。

- `checker/SymPasSymbolic.ml`：前向符号依赖、输出内存和返回指向关系。
- `checker/sympas.ml`：Checker 入口、反向兼容报告和结构化证据。
- `checker/SymPasDomain.*`：持久化过程摘要与语句来源。
- `query_slice.py`：在 SIL 指令快照上选择六类准则。
- `evaluation/`：预期摘要、控制位置、准则和缓存失效回归。
- `patches/sympas-sil-symbolic.patch`：从固定 Infer 上游构建的完整补丁。

## 构建与验证

按 [构建与验证](docs/build-and-verify.md) 准备带本项目 Checker 的 Infer，
在项目根目录设置 `INFER_BIN` 后运行：

```bash
bash infer-sympas/tests/run_sympas_tests.sh
python3 infer-sympas/evaluation/evaluate_symbolic.py --output /tmp/sympas-results.json
python3 -m unittest discover -s infer-sympas/evaluation -p 'test_*.py' -v
```

`SYMPAS_SLICE` 的 qualifier 保留旧报告并附带 `sympas_json`。结构化证据包含
准则、形参/内存/全局依赖、输出摘要、指令快照、控制与源码位置、静态调用依赖边、
别名证据，以及 `partial` / `conservative` 状态。Python 仅组织 Checker 证据，
不以 Python AST 代替 Infer 分析。

## 证据与边界

见 [验收证据](docs/acceptance-evidence.md)、
[阶段验收审计](docs/final-stage-audit.md)、
[论文算法映射](docs/paper-algorithm-mapping.md) 和
[当前复现状态](docs/reproduction-status.md)。

当前只有规则化回归测试，尚未完成基于人工参考切片的完整精度评估。
