"""Trusted fixture oracle: error propagation and success behavior, not tool-generated labels."""
from pathlib import Path
import subprocess
import tempfile
root = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='case-runtime-') as tmp:
    binary = str(Path(tmp) / 'test')
    sources = ['service.c', 'storage.c']
    build = subprocess.run(['clang', '-Wall', '-Wextra'] + [str(root / name) for name in sources] + [str(root / 'tests/driver.c'), '-o', binary], capture_output=True, text=True)
    if build.returncode:
        print(build.stderr)
        raise SystemExit(build.returncode)
    result = subprocess.run([binary], timeout=5)
    print('runtime_oracle_exit=' + str(result.returncode))
    raise SystemExit(result.returncode)
