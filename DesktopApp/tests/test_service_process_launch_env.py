from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.processes.launch_env import build_launch_environment, iter_bundled_launch_dirs
from app.processes.lifecycle import ProcessLifecycleServiceMixin


class DummyProcessLaunchEnvService(ProcessLifecycleServiceMixin):
    def __init__(self, app_root: Path, workspace_root: Path) -> None:
        self.app_root = app_root
        self.workspace_root = workspace_root


class ProcessLaunchEnvironmentTests(unittest.TestCase):
    def test_iter_launch_dirs_prefers_existing_bundled_tool_dirs_in_order(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            workspace = Path(td)
            app_root = workspace / "DesktopApp"
            expected = [
                app_root / "Runtime" / "Python",
                workspace / "Pipeline" / "Tools" / "ffmpeg" / "bin",
                workspace / "Pipeline" / "Tools" / "MKVToolNix",
                workspace / "Pipeline" / "PowerShell-7.6.0-win-x64",
            ]
            for path in expected:
                path.mkdir(parents=True)

            self.assertEqual(iter_bundled_launch_dirs(app_root, workspace), expected)

    def test_build_launch_environment_prefixes_existing_path(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            workspace = Path(td)
            app_root = workspace / "DesktopApp"
            python_dir = app_root / "Runtime" / "Python"
            python_dir.mkdir(parents=True)

            env = build_launch_environment(app_root, workspace, {"PATH": "C:\\Windows"})

            self.assertEqual(env["PATH"], str(python_dir) + os.pathsep + "C:\\Windows")

    def test_service_wrappers_match_extracted_launch_env_helpers(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            workspace = Path(td)
            app_root = workspace / "DesktopApp"
            powershell_dir = workspace / "Pipeline" / "PowerShell-7.6.0-win-x64"
            powershell_dir.mkdir(parents=True)
            service = DummyProcessLaunchEnvService(app_root, workspace)

            self.assertEqual(service._iter_bundled_launch_dirs(), iter_bundled_launch_dirs(app_root, workspace))
            self.assertIn(str(powershell_dir), service._build_launch_environment()["PATH"])


if __name__ == "__main__":
    unittest.main()
