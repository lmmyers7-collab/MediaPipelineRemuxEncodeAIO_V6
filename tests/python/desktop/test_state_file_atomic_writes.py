from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root
from unittest.mock import patch

REPO_ROOT = find_repo_root(Path(__file__))
DESKTOP_ROOT = find_repo_root(Path(__file__)) / "src"
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(DESKTOP_ROOT))

from mediapipeline.core.ui_preferences import read_ui_preferences, write_ui_preferences
from mediapipeline.desktop.api.command_journal import CommandJournal


class StateFileAtomicWriteTests(unittest.TestCase):
    def test_ui_preferences_write_retries_transient_replace_permission_error(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            path = Path(raw_root) / "State" / "ui_preferences.json"
            real_replace = os.replace
            calls: list[tuple[str, str]] = []

            def flaky_replace(src: str | os.PathLike[str], dst: str | os.PathLike[str]) -> None:
                calls.append((str(src), str(dst)))
                if len(calls) == 1:
                    raise PermissionError("locked")
                real_replace(src, dst)

            with patch("mediapipeline.core.ui_preferences.os.replace", flaky_replace), patch("mediapipeline.core.ui_preferences.time.sleep", lambda _delay: None):
                payload = write_ui_preferences(
                    path,
                    {"mediapipeline.layout.home": "compact"},
                    source_surface="test",
                )

            saved = json.loads(path.read_text(encoding="utf-8"))

        self.assertEqual(len(calls), 2)
        self.assertEqual(payload["storage"], {"mediapipeline.layout.home": "compact"})
        self.assertEqual(saved["schema_version"], "desktop_ui_preferences.v1")
        self.assertEqual(saved["storage"], {"mediapipeline.layout.home": "compact"})

    def test_ui_preferences_read_returns_default_for_corrupt_json(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            path = Path(raw_root) / "State" / "ui_preferences.json"
            path.parent.mkdir(parents=True)
            path.write_text("{not json", encoding="utf-8")

            payload = read_ui_preferences(path)

        self.assertEqual(payload["schema_version"], "desktop_ui_preferences.v1")
        self.assertEqual(payload["source"], "default")
        self.assertEqual(payload["storage"], {})

    def test_command_journal_write_retries_transient_replace_permission_error(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            path = Path(raw_root) / "RunLogs" / "local_api_command_history.json"
            journal = CommandJournal(path=path, max_entries=2)
            real_replace = os.replace
            calls: list[tuple[str, str]] = []

            def flaky_replace(src: str | os.PathLike[str], dst: str | os.PathLike[str]) -> None:
                calls.append((str(src), str(dst)))
                if len(calls) == 1:
                    raise PermissionError("locked")
                real_replace(src, dst)

            with (
                patch("mediapipeline.desktop.api.command_journal.os.replace", flaky_replace),
                patch("mediapipeline.desktop.api.command_journal.time.sleep", lambda _delay: None),
            ):
                journal.record(
                    {
                        "schema_version": "desktop_command_result.v1",
                        "command": "settings.preview_patch",
                        "ok": True,
                        "severity": "info",
                        "message": "preview ready",
                    }
                )

            saved = json.loads(path.read_text(encoding="utf-8"))

        self.assertEqual(len(calls), 2)
        self.assertEqual(saved["schema_version"], "desktop_command_history.v1")
        self.assertEqual(saved["entries"][0]["command"], "settings.preview_patch")


if __name__ == "__main__":
    unittest.main()
