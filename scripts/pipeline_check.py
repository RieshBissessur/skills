#!/usr/bin/env python3
"""The single pipeline command used by CI, both hooks, and by hand.

1. Compile every Python script in the repository.
2. Run the full test suite in tests/.

Run from anywhere: python3 scripts/pipeline_check.py
Exit: 0 when everything passes, otherwise the failing command's exit code.
"""

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def main():
    scripts = sorted((REPO / "plugins").glob("**/scripts/*.py"))
    scripts += sorted((REPO / "scripts").glob("*.py"))

    compile_proc = subprocess.run(
        [sys.executable, "-m", "py_compile", *map(str, scripts)],
        cwd=REPO,
    )
    if compile_proc.returncode:
        return compile_proc.returncode

    test_proc = subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-s", "tests"],
        cwd=REPO,
    )
    return test_proc.returncode


if __name__ == "__main__":
    sys.exit(main())
