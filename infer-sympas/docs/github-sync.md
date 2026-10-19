# GitHub 同步证据

日期：2026-10-19。

- 仓库：https://github.com/JADYAxinyun/infer-sympas-rag
- 分支：`main`
- 实现提交：`2f5a99622a10db146b9c33fcb9134f819419ef06`
- 信息：`feat: add symbolic SIL output summaries and slice regression evidence`
- push 回执：`987f559..2f5a996 main -> main`
- push 后 `git ls-remote origin refs/heads/main` 返回相同完整实现提交 hash。

实现提交包含 23 个相关文件：Checker/Domain/Symbolic 源码、完整 Infer 集成
补丁、准则查询、结构化适配器、C 样例、摘要/控制 manifest、集成测试、
可重复评测脚本及构建/验收文档。可用 `git show --stat 2f5a996` 查看完整清单。

提交前导出暂存内容到独立目录，验证 42 条摘要/控制断言、12 项真实 Infer
集成测试、12 项 Agent 测试通过。Infer 源码构建、类型检查、正式 SymPas
测试、7 个 smoke、8 条旧摘要断言及原有 16 个项目回归也已通过。

构建补丁以固定上游 commit 为基线，正向 cached apply 检查和当前源码
反向 apply 检查均通过；打包的 OCaml 核心源码与已构建源文件 SHA256 相同。
尚未在全新机器重装全部编译依赖或复现论文完整数据集。

未将工作区原有 Agent/Demo 改动、模型、缓存、运行日志、原始论文或本地
绝对路径配置加入实现提交。`infer_adapter.py` 只暂存本次结构化切片改动，
原有返回值契约候选处理改动仍保留在工作区。

同步完成不改变证据等级：实现仍标 `partial` / `conservative`，限制以
`acceptance-evidence.md` 为准。
