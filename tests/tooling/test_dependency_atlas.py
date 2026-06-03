from __future__ import annotations

import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "dev" / "generate_dependency_atlas.py"


def test_missing_explicit_dot_reports_actionable_error(tmp_path: Path) -> None:
    missing_dot = tmp_path / "missing graphviz dot.exe"

    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--dot", str(missing_dot)],
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    assert result.returncode == 2
    assert "ERROR: Graphviz dot not found at" in result.stderr
    assert "Install Graphviz or pass --dot" in result.stderr
    assert "Traceback" not in result.stderr
