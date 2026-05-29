from __future__ import annotations

from datetime import datetime
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.processes.spawn import (
    build_spawn_command_line,
    build_spawn_kwargs,
    build_spawn_log_paths,
    hidden_creationflags,
    launch_cwd_for_roots,
)


class ProcessSpawnHelperTests(unittest.TestCase):
    def test_build_spawn_command_line_preserves_spaced_paths(self) -> None:
        command_line = build_spawn_command_line(["pwsh", "-File", r"C:\Path With Space\pipeline.ps1"])

        self.assertIn("pwsh", command_line)
        self.assertIn("Path With Space", command_line)
        if os.name == "nt":
            self.assertIn('"C:\\Path With Space\\pipeline.ps1"', command_line)

    def test_hidden_creationflags_follow_show_console_flag(self) -> None:
        hidden = hidden_creationflags(False)
        visible = hidden_creationflags(True)

        self.assertEqual(visible, 0)
        if os.name == "nt":
            self.assertIsInstance(hidden, int)
        else:
            self.assertEqual(hidden, 0)

    def test_build_spawn_log_paths_uses_runlogs_stamp_and_pid(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            app_root = Path(td) / "DesktopApp"
            paths = build_spawn_log_paths(
                app_root,
                app_pid=1234,
                now=datetime(2026, 5, 8, 12, 30, 1, 234567),
            )

            self.assertTrue((app_root / "RunLogs").exists())
            self.assertEqual(paths.stdout_log.name, "run_20260508_123001_234567_1234.stdout.log")
            self.assertEqual(paths.stderr_log.name, "run_20260508_123001_234567_1234.stderr.log")

    def test_launch_cwd_prefers_existing_workspace_root(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            app_root = Path(td) / "DesktopApp"
            workspace_root = Path(td) / "Workspace"
            app_root.mkdir()
            self.assertEqual(launch_cwd_for_roots(app_root, workspace_root), app_root)
            workspace_root.mkdir()
            self.assertEqual(launch_cwd_for_roots(app_root, workspace_root), workspace_root)

    def test_build_spawn_kwargs_sets_platform_session_flags(self) -> None:
        kwargs = build_spawn_kwargs(
            launch_cwd=Path("C:/Bundle"),
            environment={"PATH": "x"},
            stdout_handle="stdout",
            stderr_handle="stderr",
            creationflags=123,
        )

        self.assertEqual(kwargs["cwd"], "C:\\Bundle" if os.name == "nt" else "C:/Bundle")
        self.assertEqual(kwargs["env"], {"PATH": "x"})
        self.assertEqual(kwargs["stdout"], "stdout")
        self.assertEqual(kwargs["stderr"], "stderr")
        if os.name == "nt":
            self.assertEqual(kwargs["creationflags"], 123)
            self.assertNotIn("start_new_session", kwargs)
        else:
            self.assertTrue(kwargs["start_new_session"])
            self.assertNotIn("creationflags", kwargs)


if __name__ == "__main__":
    unittest.main()
