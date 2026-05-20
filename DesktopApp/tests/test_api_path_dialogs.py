from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mediapipeline_desktop_app.api import path_dialogs


class PathDialogTests(unittest.TestCase):
    def test_windows_dialog_prefers_windows_powershell_over_pwsh(self) -> None:
        existing = {
            r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe",
            r"C:\Program Files\PowerShell\7\pwsh.exe",
        }

        def fake_exists(path: Path) -> bool:
            return str(path) in existing

        def fake_which(name: str) -> str | None:
            if name == "powershell.exe":
                return r"C:\Path\powershell.exe"
            if name == "pwsh.exe":
                return r"C:\Program Files\PowerShell\7\pwsh.exe"
            return None

        with (
            patch.dict(os.environ, {"SystemRoot": r"C:\Windows"}, clear=False),
            patch.object(path_dialogs.Path, "exists", fake_exists),
            patch("mediapipeline_desktop_app.api.path_dialogs.shutil.which", fake_which),
        ):
            candidates = path_dialogs._windows_powershell_candidates()

        self.assertEqual(candidates[0], r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe")
        self.assertIn(r"C:\Program Files\PowerShell\7\pwsh.exe", candidates)

    def test_select_windows_paths_uses_selected_host_and_parses_payload(self) -> None:
        captured: dict[str, object] = {}

        def fake_run(command: list[str], **_kwargs: object) -> subprocess.CompletedProcess[bytes]:
            captured["command"] = command
            payload = {
                "ok": True,
                "canceled": False,
                "selection_mode": "files",
                "paths": [r"C:\Media\One.mkv", r"C:\Media\Two.mkv"],
                "message": "Selected 2 file(s).",
                "errors": [],
            }
            return subprocess.CompletedProcess(command, 0, stdout=json.dumps(payload).encode("utf-8"), stderr=b"")

        with (
            patch("mediapipeline_desktop_app.api.path_dialogs.sys.platform", "win32"),
            patch(
                "mediapipeline_desktop_app.api.path_dialogs._select_windows_dialog_host",
                return_value=r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe",
            ),
            patch("mediapipeline_desktop_app.api.path_dialogs.subprocess.run", fake_run),
        ):
            result = path_dialogs.select_windows_paths_with_dialog(selection_mode="files", initial_path=r"C:\Media")

        self.assertTrue(result["ok"])
        self.assertEqual(result["paths"], [r"C:\Media\One.mkv", r"C:\Media\Two.mkv"])
        command = captured["command"]
        self.assertIsInstance(command, list)
        self.assertEqual(command[0], r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe")
        self.assertIn("-STA", command)
        self.assertIn("-EncodedCommand", command)

    def test_select_windows_paths_reports_missing_dialog_host(self) -> None:
        with (
            patch("mediapipeline_desktop_app.api.path_dialogs.sys.platform", "win32"),
            patch("mediapipeline_desktop_app.api.path_dialogs._select_windows_dialog_host", return_value=None),
        ):
            result = path_dialogs.select_windows_paths_with_dialog(selection_mode="folder")

        self.assertFalse(result["ok"])
        self.assertEqual(result["selection_mode"], "folder")
        self.assertIn("Windows PowerShell", result["message"])
        self.assertEqual(result["errors"], ["powershell_not_found"])

    def test_select_windows_paths_reports_process_failure_with_host(self) -> None:
        def fake_run(command: list[str], **_kwargs: object) -> subprocess.CompletedProcess[bytes]:
            return subprocess.CompletedProcess(command, 1, stdout=b"", stderr=b"Add-Type failed: not found")

        with (
            patch("mediapipeline_desktop_app.api.path_dialogs.sys.platform", "win32"),
            patch(
                "mediapipeline_desktop_app.api.path_dialogs._select_windows_dialog_host",
                return_value=r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe",
            ),
            patch("mediapipeline_desktop_app.api.path_dialogs.subprocess.run", fake_run),
        ):
            result = path_dialogs.select_windows_paths_with_dialog(selection_mode="files")

        self.assertFalse(result["ok"])
        self.assertIn("powershell.exe", result["message"])
        self.assertEqual(result["errors"], ["Add-Type failed: not found"])


if __name__ == "__main__":
    unittest.main()
