# 从固定 Infer 基线构建与验证

本仓库的 `checker/` 是可审阅源码副本；完整集成补丁为
`patches/sympas-sil-symbolic.patch`。旧的 `initial-sympas-prototype.patch`
保留用于历史比较，不要叠加应用两个补丁。

固定上游：`facebook/infer`，commit
`717ee0b36c3c3575b0bd8e9bf65f2fa3dddb0871`。
完整补丁包含 Checker 注册、Payload、IssueType、OCaml 分析模块和上游 smoke。
补丁已通过该基线的临时 Git index 正向检查，以及当前工作树反向检查；
当前源码构建通过。尚未在全新机器重新安装全部编译依赖。

## 构建

在本项目根目录记录 `SYMPAS_PROJECT`，在独立 Infer checkout 应用补丁：

```bash
SYMPAS_PROJECT="$PWD"
git clone https://github.com/facebook/infer.git infer-build
cd infer-build
git checkout 717ee0b36c3c3575b0bd8e9bf65f2fa3dddb0871
git apply --check "$SYMPAS_PROJECT/infer-sympas/patches/sympas-sil-symbolic.patch"
git apply "$SYMPAS_PROJECT/infer-sympas/patches/sympas-sil-symbolic.patch"
```

按该固定版本的上游安装说明准备编译器、opam 和 Clang plugin 依赖；
首次构建使用上游 `build-infer.sh` 的平台选项。在已完成依赖安装的环境：

```bash
eval "$(opam env)"
make -j 4 -C infer/src check
make -j 4
make -C infer/tests/codetoanalyze/c/sympas
./examples/sympas/run_smoke_tests.sh
python3 examples/sympas/evaluate_smoke.py
```

2026-10-19 本地验证环境：Darwin 25.5.0 arm64、Apple clang 21.0.0、
OCaml 5.4.1、opam 2.6.0；二进制自报 `Infer version v1.3.0-717ee0b36c`。
此版本字符串仅标识上游基线，不能单独证明加载了本项目修改；验证
`sympas_json`、`instruction_slices`、`procedure_summary.outputs` 才能确认能力。

## 项目回归

```bash
export INFER_BIN="$PWD/infer/bin/infer"
cd "$SYMPAS_PROJECT"
bash infer-sympas/tests/run_sympas_tests.sh
python3 infer-sympas/evaluation/evaluate_symbolic.py --output /tmp/sympas-results.json
python3 -m unittest discover -s infer-sympas/evaluation -p 'test_*.py' -v
```

测试输出保留在独立临时目录，不覆盖旧的分析结果。评测 JSON 包含源码、
命令、准则、预期/实际摘要、缺失/额外依赖、切片大小、运行时间和报告字节数。
递归用例的超时是失败；成功终止不是对任意程序的递归精度证明。

## 准则查询

先以 `infer --sympas-only --results-dir /tmp/sympas-example -- clang -c example.c`
生成报告，再查询：

```bash
python3 infer-sympas/query_slice.py /tmp/sympas-example/report.json --type return_value --procedure check
python3 infer-sympas/query_slice.py /tmp/sympas-example/report.json --type variable --procedure check --variable result
python3 infer-sympas/query_slice.py /tmp/sympas-example/report.json --type call_site --procedure check --line 10
python3 infer-sympas/query_slice.py /tmp/sympas-example/report.json --type finding_variable --procedure check --variable result --line 10
python3 infer-sympas/query_slice.py /tmp/sympas-example/report.json --type return_point --procedure check --line 14
python3 infer-sympas/query_slice.py /tmp/sympas-example/report.json --type file_location --procedure check --file example.c --line 10 --column 17
```

行号和变量名来自待分析程序，不应照搬示例。变量准则定位定义点；同一行
多个 SIL 指令返回多个结果，列号可进一步定位。无法匹配时返回 `unsupported`
并以状态码 2 退出。`finding_variable` 需要调用者提供 finding 的变量和位置，
尚未从所有 Infer finding 自动恢复目标变量。

当前只有规则化回归测试，尚未完成基于人工参考切片的完整精度评估。
