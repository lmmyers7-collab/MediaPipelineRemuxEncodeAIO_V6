from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from mediapipeline.tools.dev import generate_dependency_atlas
from mediapipeline.tools.paths import find_repo_root


REPO_ROOT = find_repo_root(Path(__file__))
SCRIPT_PATH = REPO_ROOT / "src" / "mediapipeline" / "tools" / "dev" / "generate_dependency_atlas.py"


def _write(path: Path, text: str = "") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_collect_data_resolves_current_namespace_import_edges(tmp_path: Path) -> None:
    package_root = tmp_path / "src" / "mediapipeline" / "core"
    _write(package_root / "__init__.py")
    _write(package_root / "api" / "__init__.py")
    _write(
        package_root / "api" / "routes.py",
        "from mediapipeline.core.config import load\nfrom ..shared import utils\n",
    )
    _write(package_root / "config" / "__init__.py")
    _write(package_root / "config" / "load.py")
    _write(package_root / "shared" / "__init__.py")
    _write(package_root / "shared" / "utils.py")

    data = generate_dependency_atlas.collect_data((("mediapipeline.core", package_root),))

    assert ("mediapipeline.core.api.routes", "mediapipeline.core.config.load") in data.module_edges
    assert ("mediapipeline.core.api.routes", "mediapipeline.core.shared.utils") in data.module_edges
    assert data.category_edges[("core/api", "core/config")] == 1
    assert data.category_edges[("core/api", "core/shared")] == 1


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
