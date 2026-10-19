# 接近真实场景的人工审查样例

三个案例都是项目构造的正例，不是从生产环境发现的真实缺陷；不能用于估计通用 Precision、Recall 或误报率。
每个目录的 expected.json 是独立预期，contracts.json 是明确标注来源的人工返回值契约。
行为 oracle 位于 tests/driver.c，tests/check.py 负责编译并实际执行；没有用工具预测自动生成真值。

| 样例 | 源码与预期规则调用点 | 预期 Infer | 预期切片 | 关键检索上下文 | 预期行为 |
|---|---|---|---|---|---|
| unchecked_return | job.c:8，run_job 忽略 load_config | native DEAD_STORE；开启 SymPas 后有 SYMPAS_SLICE | run_job 的调用指令快照关联 load_config | job.c 的 load_config | NULL 输入必须报错且不增加 processed |
| error_propagation | pipeline.c:13，handle_request 忽略 flush_state | native DEAD_STORE；SymPas 切片和底层负返回候选 | handle_request 调用 flush_state，底层 persist_state 错误应传播 | pipeline.c 的 flush_state | 负输入向上传播 -2，不能增加 committed |
| cross_file | service.c:4，handle_write 忽略 write_file | native DEAD_STORE；SymPas 切片及 write_file 候选 | 调用点位于 service.c，callee 位于 storage.c | storage.c 的 write_file | NULL 输入传播 -3，不能增加 accepted |

原始程序均编译成功，但行为测试应退出 1；候选加入正确 guard 后应退出 0。
每个 oracle 同时检查失败路径和一次成功路径，仍不等同于穷举验证或语义等价证明。
切片允许 conservative 的额外依赖，状态允许 partial 或输入明确给出的 complete；Agent 不升级原始状态。
返回值准则可能不依赖被忽略的调用；call_sites 只是把 Checker 已有指令快照提供给 Agent，不重算依赖。
模型结论允许 likely/confirmed/uncertain 等差异，但引用和结构必须有效；模型 patch 可以为 null 或被验证拒绝。

## 单案例运行

从仓库根目录执行（使用带当前 Checker 的 Infer）：

```bash
export INFER_BIN=/absolute/path/to/infer
./draco-sympas/.venv/bin/python draco-sympas/cli.py review \
  --repo draco-sympas/examples/realistic_case/cross_file \
  --target-file service.c --target-file storage.c --infer-profile combined \
  --contracts draco-sympas/examples/realistic_case/cross_file/contracts.json \
  --llm-provider mock --test-command-json '["python3","tests/check.py"]'
```

替换 --llm-provider mock 为 --llm-provider deepseek --env-file .env 才调用真实 API。
对另外两个案例分别指定 job.c 或 pipeline.c；不要把 tests/driver.c 当作被审查生产单元。
输出保留 infer.json、slice.json、retrieval.json、context.json、llm_response.json、validation.json、review.md。
旧 slices.json 和 run.json 仍兼容保留。

## 五组对照

```bash
./draco-sympas/.venv/bin/python draco-sympas/evaluation/evaluate_realistic.py
./draco-sympas/.venv/bin/python draco-sympas/evaluation/evaluate_realistic.py \
  --live-deepseek --env-file .env
```

默认只运行 A-D，E 明确为 not_run；开启后每案例一次真实模型调用。
已有原始响应可复查候选而不再调用 API：

```bash
./draco-sympas/.venv/bin/python draco-sympas/evaluation/evaluate_realistic.py \
  --revalidate /absolute/path/to/evaluation-run
```

每次新建目录，不覆盖原始报告或实验。候选仅应用到副本；状态仍为 partially_verified，或明确的 validation_failed / not_verified。
