from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from mediapipeline.tools.dev import generate_dependency_atlas
from mediapipeline.tools.paths import find_repo_root


REPO_ROOT = find_repo_root(Path(__file__))
SCRIPT_PATH = REPO_ROOT / "src" / "mediapipeline" / "tools" / "dev" / "generate_dependency_atlas.py"


def _write(path: Path, text: str = "") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _patch_atlas_output_paths(repo_root: Path) -> dict[str, object]:
    output_root = repo_root / "docs" / "generated" / "dependency-atlas"
    asset_root = output_root / "assets"
    values: dict[str, object] = {
        "REPO_ROOT": repo_root,
        "OUTPUT_ROOT": output_root,
        "ROOT_HTML": output_root / "dependency-atlas.html",
        "ROOT_PNG": output_root / "dependency-atlas.png",
        "ROOT_SVG": output_root / "dependency-atlas.svg",
        "ROOT_DOT": output_root / "dependency-atlas.dot",
        "ASSET_ROOT": asset_root,
        "LEGACY_ASSET_ROOT": repo_root / "docs" / "generated" / "dependency-atlas_assets",
    }
    original = {name: getattr(generate_dependency_atlas, name) for name in values}
    for name, value in values.items():
        setattr(generate_dependency_atlas, name, value)
    return original


class DependencyAtlasCleanupTests(unittest.TestCase):
    def test_clean_outputs_preserves_unowned_matching_root_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            original = _patch_atlas_output_paths(repo_root)
            try:
                output_root = generate_dependency_atlas.OUTPUT_ROOT
                asset_root = generate_dependency_atlas.ASSET_ROOT
                legacy_asset_root = generate_dependency_atlas.LEGACY_ASSET_ROOT

                _write(asset_root / "dependency_detail_old.svg", "owned detail")
                _write(asset_root / "dependency_summary.csv", "owned csv")
                _write(output_root / "docs" / "generated" / "dependency-atlas.html", "nested")
                _write(legacy_asset_root / "dependency_detail_old.svg", "legacy")

                exact_legacy = repo_root / "python_dependencies.png"
                exact_legacy.write_bytes(b"legacy atlas png")
                marked_legacy = repo_root / "V6_dependency_domains.svg"
                _write(marked_legacy, "<svg><text>Python dependency atlas</text></svg>")
                unrelated_png = repo_root / "notes_python_dependencies.png"
                unrelated_png.write_bytes(b"operator notes")
                unrelated_svg = repo_root / "notes_dependency_domains.svg"
                _write(unrelated_svg, "<svg><text>Business dependency domains</text></svg>")

                generate_dependency_atlas.clean_outputs()

                self.assertFalse(exact_legacy.exists())
                self.assertFalse(marked_legacy.exists())
                self.assertTrue(unrelated_png.exists())
                self.assertTrue(unrelated_svg.exists())
                self.assertFalse((asset_root / "dependency_detail_old.svg").exists())
                self.assertFalse((asset_root / "dependency_summary.csv").exists())
                self.assertFalse((output_root / "docs").exists())
                self.assertFalse(legacy_asset_root.exists())
            finally:
                for name, value in original.items():
                    setattr(generate_dependency_atlas, name, value)


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
        capture_output=True,
    )

    assert result.returncode == 2
    assert "ERROR: Graphviz dot not found at" in result.stderr
    assert "Install Graphviz or pass --dot" in result.stderr
    assert "Traceback" not in result.stderr
