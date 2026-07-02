"""Run conservative Ruff lint checks without formatting or fixing code."""

from __future__ import annotations

import argparse
import importlib.util
import subprocess
import sys
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root


REPO_ROOT = find_repo_root(Path(__file__))
DEFAULT_TARGETS = ("src", "tests")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "targets",
        nargs="*",
        default=list(DEFAULT_TARGETS),
        help="Repo-relative paths to lint. Defaults to src and tests.",
    )
    args = parser.parse_args(argv)

    if importlib.util.find_spec("ruff") is None:
        print(
            "ERROR: Ruff is not installed. Install requirements/dev.txt before running Python lint checks.",
            file=sys.stderr,
        )
        return 2

    command = [
        sys.executable,
        "-m",
        "ruff",
        "check",
        "--config",
        "pyproject.toml",
        *args.targets,
    ]
    return subprocess.run(command, cwd=REPO_ROOT).returncode


if __name__ == "__main__":
    raise SystemExit(main())
