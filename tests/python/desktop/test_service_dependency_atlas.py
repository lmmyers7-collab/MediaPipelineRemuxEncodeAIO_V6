from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from mediapipeline.tools.paths import find_repo_root

sys.path.insert(0, str(find_repo_root(Path(__file__)) / "src"))

from mediapipeline.core.maintenance.dependency_atlas import DependencyAtlasServiceMixin


class DummyDependencyAtlasService(DependencyAtlasServiceMixin):
    def __init__(self, root: Path) -> None:
        self.workspace_root = root
        self.app_root = root / "apps" / "desktop"
        self.app_root.mkdir(parents=True, exist_ok=True)

    def _build_launch_environment(self) -> dict[str, str]:
        return {
            "PATH": "C:\\Windows",
            "PYTHONPATH": str(self.workspace_root / "existing-pythonpath"),
        }

    def _subprocess_kwargs_hidden(self) -> dict[str, object]:
        return {}

    def kill_process_tree(self, _pid: int) -> None:
        return None


class DependencyAtlasServiceTests(unittest.TestCase):
    def test_generate_dependency_atlas_prefixes_source_pythonpath_for_module_command(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            script = root / "src" / "mediapipeline" / "tools" / "dev" / "generate_dependency_atlas.py"
            script.parent.mkdir(parents=True)
            script.write_text("# generator placeholder\n", encoding="utf-8")
            service = DummyDependencyAtlasService(root)
            captured: dict[str, object] = {}

            def fake_run_capture(args: list[str], **kwargs: object) -> SimpleNamespace:
                captured["args"] = args
                captured["kwargs"] = kwargs
                output_dir = root / "docs/generated/dependency-atlas"
                assets_dir = output_dir / "assets"
                assets_dir.mkdir(parents=True)
                for path in (
                    output_dir / "dependency-atlas.html",
                    output_dir / "dependency-atlas.png",
                    output_dir / "dependency-atlas.svg",
                    assets_dir / "dependency_summary.csv",
                    assets_dir / "dependency_edges.csv",
                    assets_dir / "dependency_module_edges.csv",
                ):
                    path.write_text("generated\n", encoding="utf-8")
                return SimpleNamespace(returncode=0, timed_out=False, stdout="ok", stderr="", kill_message="")

            with patch("mediapipeline.core.maintenance.dependency_atlas.run_capture", fake_run_capture):
                result = service.generate_dependency_atlas(
                    timeout_seconds=600,
                    min_overview_edge_count=4,
                    min_overview_files=2,
                )

        self.assertTrue(result["success"])
        args = captured["args"]
        self.assertIsInstance(args, list)
        self.assertEqual(args[1:3], ["-m", "mediapipeline.tools.dev.generate_dependency_atlas"])
        kwargs = captured["kwargs"]
        self.assertIsInstance(kwargs, dict)
        env = kwargs["env"]
        self.assertIsInstance(env, dict)
        pythonpath_parts = str(env["PYTHONPATH"]).split(os.pathsep)
        self.assertEqual(pythonpath_parts[0], str(root / "src"))
        self.assertIn(str(root / "existing-pythonpath"), pythonpath_parts)


if __name__ == "__main__":
    unittest.main()
