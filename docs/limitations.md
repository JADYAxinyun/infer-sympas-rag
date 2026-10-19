# 当前实际范围与限制

- 研究型 MVP、Infer/SymPas 风格程序分析、DRaCo 风格仓库检索；不声称完整论文复现。
- 当前只围绕原有 unchecked_return_value 规则形成闭环；没有批量新增未经验证的规则。
- Infer SIL Checker 的状态为 partial / conservative。没有结构化 Checker 输出时切片为 not_analyzed，旧格式会留下 unsupported 诊断；Python 不补造依赖。
- 输入、局部定义传播、控制依赖、过程摘要、调用点实例化、跨过程输出传播由已有 Checker 提供；别名、聚合字段、间接调用和路径精度有限，见 infer-sympas 文档。
- 返回值规则仍使用五行窗口和有限正则，会有误报与漏报；未知函数不报告，除非具有显式契约或 medium Infer 候选。
- 默认函数契约来自人工 Demo 策略；整型返回不等于错误码。infer_candidate 需人工确认，不提升成正式 API 契约。
- AST 图支持有限静态语法。C/C++ 缺 clang、头文件或构建标志时返回诊断；TYPEOF 只提取类型注解。Python 模块导入绑定、动态分派、C 函数指针没有完整解析。
- 原版 DRaCo 的上游子模块与 Prompt 增强流程保留；新图是窄范围接入实现，不宣称复现完整 repository dataflow analysis。
- review 默认直接 clang 编译明确文件，不自动推断构建系统、宏、include 路径或链接配置。
- Diff 是上下文，默认不构成改动行过滤器；需要精确范围时明确指定 target_files。
- 本地 CodeGen 可被调用，但可能不遵循 JSON 格式；解析失败不会伪装成成功判断。本轮未运行本地模型。
- DeepSeek 可配置；HTTP 模拟测试不等于真实 API 成功。没有 Key 时 live 验证保持 NOT_RUN。
- JSON/引用验证只能检查结构、已提供 ID、来源以及源码文件/行号，不能证明模型推理正确或输入代码安全。
- 预算用 UTF-8 字节数保守估算，可能明显少用真实上下文窗口。实际计费 token 仅使用 API usage，不能由此估算替代。
- 候选修复使用原有 negative_return_check 策略，生成独立文件，不应用模型 patch。它可能不符合函数返回类型、清理职责或实际 API 契约。
- 修复状态 verified 保留给充分验证；本流程即使规则下降、clang 通过、Infer 再查成功，仍只标 partially_verified，因为尚无语义等价或运行时测试证明。
- 切片和契约候选不是漏洞，不能通过 Infer 总 issue 数下降宣称修复正确。
- 四组评估仅为 prototype smoke evaluation，4 个构造案例，LLM 使用 Mock；不代表大型真实项目、真实模型效果或泛化准确率。
