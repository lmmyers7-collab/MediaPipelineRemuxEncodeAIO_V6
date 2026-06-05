"""Run the Phase 4 Python typing boundary check.

The target set is intentionally narrow while the overhaul is in progress:
backend contracts, orchestration, storage, observability, and validation code.
Desktop-facing modules are migrated behind compatibility shims before they
become typing-enforced.
"""

from __future__ import annotations

import argparse
import importlib.util
import subprocess
import sys
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root


REPO_ROOT = find_repo_root(Path(__file__))
DEFAULT_TARGETS = (
    "src/mediapipeline/contracts",
    "src/mediapipeline/core/orchestration",
    "src/mediapipeline/core/storage",
    "src/mediapipeline/core/observability",
    "src/mediapipeline/core/validation",
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "targets",
        nargs="*",
        default=list(DEFAULT_TARGETS),
        help="Repo-relative paths to type-check. Defaults to Phase 4 backend targets.",
    )
    args = parser.parse_args(argv)

    if importlib.util.find_spec("mypy") is None:
        print(
            "ERROR: mypy is not installed. Install requirements/dev.txt before running typing checks.",
            file=sys.stderr,
        )
        return 2

    command = [
        sys.executable,
        "-m",
        "mypy",
        "--config-file",
        str(REPO_ROOT / "pyproject.toml"),
        *args.targets,
    ]
    return subprocess.run(command, cwd=REPO_ROOT).returncode


if __name__ == "__main__":
    raise SystemExit(main())
