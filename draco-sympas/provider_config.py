"""Explicit, non-executable local configuration. Never log file contents."""
import os
from pathlib import Path


def load_env_file(path):
    """Read only DeepSeek settings; existing nonempty environment wins.

    Shell expansion, export commands and arbitrary environment keys are unsupported.
    Returns names only; never credential values or source lines.
    """
    path = Path(path)
    allowed = {'DEEPSEEK_API_KEY', 'DEEPSEEK_MODEL'}
    loaded = []
    for number, line in enumerate(path.read_text().splitlines(), 1):
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        name, separator, value = line.partition('=')
        name, value = name.strip(), value.strip()
        if not separator or name not in allowed:
            raise ValueError(f'Unsupported configuration at line {number}; only DeepSeek settings are allowed')
        if value[:1] in ('"', "'"):
            if len(value) < 2 or value[-1] != value[0]:
                raise ValueError(f'Invalid quoted configuration at line {number}')
            value = value[1:-1]
        if value and not os.environ.get(name):
            os.environ[name] = value
            loaded.append(name)
    return loaded
