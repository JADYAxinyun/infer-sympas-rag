# DRaCo 环境状态

已在 Apple Silicon macOS 上创建并验证独立环境：

- Python 3.10.22
- PyTorch 2.14.1
- Transformers 4.33.3
- Tree-sitter 0.26.0
- Tree-sitter Python 0.25.0
- tiktoken 0.14.0
- MPS 可用：`True`

激活环境：

```bash
source draco-sympas/.venv/bin/activate
```

安装依赖：

```bash
pip install -r third_party/draco-upstream/requirements.txt
```

当前只验证了依赖导入和 MPS 可用性，尚未下载代码生成模型或运行完整 ReccEval。
