"""Run the Phase 4 Python typing boundary check.

The target set is intentionally narrow while the overhaul is in progress:
new app-layer contracts, orchestration, storage, observability, and validation
code. Legacy DesktopApp modules are migrated behind compatibility shims before
they become typing-enforced.
"""

from __future__ import annotations

import argparse
import importlib.util
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_TARGETS = (
    "app/contracts",
    "app/orchestration",
    "app/storage",
    "app/observability",
    "app/validation",
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "targets",
        nargs="*",
        default=list(DEFAULT_TARGETS),
        help="Repo-relative paths to type-check. Defaults to Phase 4 app-layer targets.",
    )
    args = parser.parse_args(argv)

    if importlib.util.find_spec("mypy") is None:
        print(
            "ERROR: mypy is not installed. Install requirements-dev.txt before running typing checks.",
            file=sys.stderr,
        )
        return 2

    command = [
        sys.executable,
        "-m",
        "mypy",
        "--config-file",
        str(REPO_ROOT / "mypy.ini"),
        *args.targets,
    ]
    return subprocess.run(command, cwd=REPO_ROOT).returncode


if __name__ == "__main__":
    raise SystemExit(main())
