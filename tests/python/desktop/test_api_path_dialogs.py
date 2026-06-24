from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root
from unittest.mock import patch

REPO_ROOT = find_repo_root(Path(__file__))
SRC_ROOT = REPO_ROOT / "src"
sys.path.insert(0, str(SRC_ROOT))

from mediapipeline.desktop.api import path_dialogs


class PathDialogTests(unittest.TestCase):
    def test_core_command_modules_import_before_desktop_api_server_export(self) -> None:
        script = (
            "import mediapipeline.core.api.commands_process\n"
            "import mediapipeline.core.api.commands_rename\n"
            "import mediapipeline.core.api.commands_settings\n"
            "from mediapipeline.desktop.api import LocalApiServer\n"
            "print(LocalApiServer.__name__)\n"
        )
        env = dict(os.environ)
        env["PYTHONPATH"] = str(SRC_ROOT)

        result = subprocess.run(
            [sys.executable, "-c", script],
            cwd=REPO_ROOT,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "LocalApiServer")

    def test_windows_dialog_prefers_pwsh_over_windows_powershell(self) -> None:
        """PowerShell 7+ wins because only it exposes Microsoft.Win32.OpenFolderDialog
        (the modern Windows Explorer-style folder picker). Windows PowerShell 5.1
        falls back to the legacy FolderBrowserDialog tree, which we are trying to
        avoid in the Rename workbench."""
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
            patch("mediapipeline.desktop.api.path_dialogs.shutil.which", fake_which),
            patch("mediapipeline.desktop.api.path_dialogs._bundled_pwsh_candidates", return_value=[]),
        ):
            candidates = path_dialogs._windows_powershell_candidates()

        # pwsh 7 must win.
        self.assertEqual(candidates[0], r"C:\Program Files\PowerShell\7\pwsh.exe")
        # Windows PowerShell remains a fallback for bare machines.
        self.assertIn(r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe", candidates)

    def test_windows_dialog_prefers_bundled_pwsh_over_system_pwsh(self) -> None:
        """The repo-bundled pwsh in ops/pipeline/runtime/PowerShell-7.6.0-win-x64 should win
        over any system pwsh.exe so the operator does not need pwsh installed."""
        bundled = r"C:\Repo\ops\pipeline\runtime\PowerShell-7.6.0-win-x64\pwsh.exe"
        system_pwsh = r"C:\Program Files\PowerShell\7\pwsh.exe"
        existing = {bundled, system_pwsh}

        def fake_exists(path: Path) -> bool:
            return str(path) in existing

        def fake_which(name: str) -> str | None:
            return system_pwsh if name == "pwsh.exe" else None

        with (
            patch.dict(os.environ, {"SystemRoot": r"C:\Windows"}, clear=False),
            patch.object(path_dialogs.Path, "exists", fake_exists),
            patch("mediapipeline.desktop.api.path_dialogs.shutil.which", fake_which),
            patch("mediapipeline.desktop.api.path_dialogs._bundled_pwsh_candidates", return_value=[bundled]),
        ):
            candidates = path_dialogs._windows_powershell_candidates()

        self.assertEqual(candidates[0], bundled)
        self.assertIn(system_pwsh, candidates)

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
            patch("mediapipeline.desktop.api.path_dialogs.sys.platform", "win32"),
            patch(
                "mediapipeline.desktop.api.path_dialogs._select_windows_dialog_host",
                return_value=r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe",
            ),
            patch("mediapipeline.desktop.api.path_dialogs.subprocess.run", fake_run),
        ):
            result = path_dialogs.select_windows_paths_with_dialog(selection_mode="files", initial_path=r"C:\Media")

        self.assertTrue(result["ok"])
        self.assertEqual(result["paths"], [r"C:\Media\One.mkv", r"C:\Media\Two.mkv"])
        command = captured["command"]
        self.assertIsInstance(command, list)
        self.assertEqual(command[0], r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe")
        self.assertIn("-STA", command)
        self.assertIn("-EncodedCommand", command)

    def test_folder_files_filters_sidecars_and_reports_ignored_counts(self) -> None:
        def fake_run(command: list[str], **_kwargs: object) -> subprocess.CompletedProcess[bytes]:
            payload = {
                "ok": True,
                "canceled": False,
                "selection_mode": "folder_files",
                "paths": [
                    r"C:\Media\Ranma - S01E19.mkv",
                    r"C:\Media\Ranma - S01E19.pipeline.json",
                    r"C:\Media\notes.txt",
                    r"C:\Media\Ranma - S01E20.mp4",
                ],
                "message": "Selected folder with 4 direct child file(s).",
                "errors": [],
            }
            return subprocess.CompletedProcess(command, 0, stdout=json.dumps(payload).encode("utf-8"), stderr=b"")

        with (
            patch("mediapipeline.desktop.api.path_dialogs.sys.platform", "win32"),
            patch(
                "mediapipeline.desktop.api.path_dialogs._select_windows_dialog_host",
                return_value=r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe",
            ),
            patch("mediapipeline.desktop.api.path_dialogs.subprocess.run", fake_run),
        ):
            result = path_dialogs.select_windows_paths_with_dialog(selection_mode="folder_files")

        self.assertTrue(result["ok"])
        self.assertEqual(result["paths"], [r"C:\Media\Ranma - S01E19.mkv", r"C:\Media\Ranma - S01E20.mp4"])
        self.assertEqual(result["raw_path_count"], 4)
        self.assertEqual(result["ignored_path_count"], 2)
        self.assertEqual(result["ignored_sidecar_count"], 1)

    def test_known_dropped_folder_expands_direct_media_children_only(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            folder = root / "Season 02"
            nested = folder / "Nested"
            nested.mkdir(parents=True)
            media_one = folder / "Ranma - S01E01.mkv"
            media_two = folder / "Ranma - S01E02.mp4"
            sidecar = folder / "Ranma - S01E01.pipeline.json"
            note = folder / "notes.txt"
            nested_media = nested / "Ranma - S01E03.mkv"
            for path in (media_one, media_two, sidecar, note, nested_media):
                path.write_text("fixture", encoding="utf-8")

            result = path_dialogs.select_rename_paths_from_known_paths(
                [str(folder)],
                selection_mode="folder_files",
            )

        self.assertTrue(result["ok"])
        self.assertEqual(result["selection_mode"], "folder_files")
        self.assertEqual(result["paths"], [str(media_one), str(media_two)])
        self.assertNotIn(str(folder), result["paths"])
        self.assertNotIn(str(nested_media), result["paths"])
        self.assertEqual(result["raw_path_count"], 4)
        self.assertEqual(result["ignored_path_count"], 2)
        self.assertEqual(result["ignored_sidecar_count"], 1)
        self.assertEqual(result["ignored_non_media_count"], 1)

    def test_select_windows_paths_reports_missing_dialog_host(self) -> None:
        with (
            patch("mediapipeline.desktop.api.path_dialogs.sys.platform", "win32"),
            patch("mediapipeline.desktop.api.path_dialogs._select_windows_dialog_host", return_value=None),
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
            patch("mediapipeline.desktop.api.path_dialogs.sys.platform", "win32"),
            patch(
                "mediapipeline.desktop.api.path_dialogs._select_windows_dialog_host",
                return_value=r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe",
            ),
            patch("mediapipeline.desktop.api.path_dialogs.subprocess.run", fake_run),
        ):
            result = path_dialogs.select_windows_paths_with_dialog(selection_mode="files")

        self.assertFalse(result["ok"])
        self.assertIn("powershell.exe", result["message"])
        self.assertEqual(result["errors"], ["Add-Type failed: not found"])


if __name__ == "__main__":
    unittest.main()
