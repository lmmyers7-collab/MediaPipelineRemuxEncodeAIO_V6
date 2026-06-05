"""Run a packaged MediaPipeline tool from a source checkout."""

from __future__ import annotations

import runpy
import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: run-python-tool.py <module> [args...]", file=sys.stderr)
        return 2
    repo_root = Path(__file__).resolve().parents[3]
    src_root = repo_root / "src"
    sys.path.insert(0, str(src_root))
    module = sys.argv[1]
    sys.argv = [module, *sys.argv[2:]]
    runpy.run_module(module, run_name="__main__")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
