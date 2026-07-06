from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
import sys
from types import SimpleNamespace

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "src"))

from mediapipeline.core.api.commands_path_picker import LocalApiPathPickerCommandPayloadMixin


class PathPickerHarness(LocalApiPathPickerCommandPayloadMixin):
    pass


class PathPickerCommandTests(unittest.TestCase):
    def test_rejects_unknown_target_key(self) -> None:
        payload = PathPickerHarness()._path_picker_browse_payload({"target_key": "unknown"})

        self.assertFalse(payload["ok"])
        self.assertEqual(payload["command"], "path_picker.browse")
        self.assertEqual(payload["errors"], ["unsupported_target_key"])
        self.assertFalse(payload["data"]["writes_config"])
        self.assertTrue(payload["data"]["stages_only"])
        self.assertFalse(payload["data"]["mutates_media"])

    def test_rejects_invalid_selection_mode_for_target(self) -> None:
        payload = PathPickerHarness()._path_picker_browse_payload(
            {"target_key": "queue.rerun_csv", "selection_mode": "folder"}
        )

        self.assertFalse(payload["ok"])
        self.assertEqual(payload["errors"], ["unsupported_selection_mode"])
        self.assertEqual(payload["data"]["allowed_selection_modes"], ["files"])
        self.assertFalse(payload["data"]["writes_config"])
        self.assertTrue(payload["data"]["stages_only"])

    def test_canceled_picker_returns_staged_only_info_without_selected_path(self) -> None:
        harness = PathPickerHarness()
        harness._path_picker = lambda **_kwargs: {  # type: ignore[attr-defined]
            "ok": True,
            "canceled": True,
            "selection_mode": "folder",
            "paths": [],
            "message": "Folder selection canceled.",
            "errors": [],
        }

        payload = harness._path_picker_browse_payload({"target_key": "metrics.source_root"})

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["severity"], "info")
        self.assertTrue(payload["data"]["canceled"])
        self.assertEqual(payload["data"]["selected_path"], "")
        self.assertFalse(payload["data"]["writes_config"])
        self.assertTrue(payload["data"]["stages_only"])
        self.assertFalse(payload["data"]["launches_work"])
        self.assertFalse(payload["data"]["mutates_media"])

    def test_validates_folder_file_executable_csv_and_media_targets(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            csv_path = root / "rerun.csv"
            exe_path = root / "ffmpeg.exe"
            media_path = root / "movie.mkv"
            csv_path.write_text("path\n", encoding="utf-8")
            exe_path.write_text("", encoding="utf-8")
            media_path.write_text("", encoding="utf-8")

            selected_by_target = {
                "reports.audit_library_root": str(root),
                "launch.rerun_csv": str(csv_path),
                "queue.rerun_csv": str(csv_path),
                "settings.wizard.ffmpeg_path": str(exe_path),
                "launch.single_file": str(media_path),
            }
            harness = PathPickerHarness()
            harness._path_picker = lambda target_key, **kwargs: {  # type: ignore[attr-defined]
                "ok": True,
                "canceled": False,
                "selection_mode": kwargs["selection_mode"],
                "paths": [selected_by_target[target_key]],
                "message": "Selected 1 path.",
                "errors": [],
            }

            for target_key, selected_path in selected_by_target.items():
                with self.subTest(target_key=target_key):
                    payload = harness._path_picker_browse_payload({"target_key": target_key})
                    self.assertTrue(payload["ok"], payload)
                    self.assertEqual(payload["data"]["selected_path"], selected_path)
                    self.assertEqual(payload["data"]["validation"]["status_state"], "ready")
                    self.assertFalse(payload["data"]["writes_config"])
                    self.assertTrue(payload["data"]["stages_only"])

    def test_folder_to_direct_files_filters_to_media_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            media_path = root / "episode.mkv"
            sidecar_path = root / "episode.pipeline.json"
            media_path.write_text("", encoding="utf-8")
            sidecar_path.write_text("", encoding="utf-8")
            harness = PathPickerHarness()
            harness._path_picker = lambda **_kwargs: {  # type: ignore[attr-defined]
                "ok": True,
                "canceled": False,
                "selection_mode": "folder_files",
                "paths": [str(media_path), str(sidecar_path)],
                "message": "Selected folder direct files.",
                "errors": [],
            }

            payload = harness._path_picker_browse_payload({"target_key": "rename.source.folder_files"})

            self.assertTrue(payload["ok"], payload)
            self.assertEqual(payload["data"]["paths"], [str(media_path)])
            self.assertEqual(payload["data"]["validation"]["status_state"], "ready")
            self.assertEqual(payload["data"]["validation"]["ignored_sidecar_count"], 1)

    def test_rerun_csv_browse_defaults_to_audit_reports_when_empty(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            audit_reports = root / "LocalBase" / "AuditReports"
            audit_reports.mkdir(parents=True)
            selected_csv = audit_reports / "audit_rerun_export_20260628_120000.csv"
            selected_csv.write_text("enabled,source_path\ntrue,C:\\Media\\Movie.mkv\n", encoding="utf-8")
            captured_kwargs: dict[str, object] = {}

            class Harness(PathPickerHarness):
                def _resolved(self) -> object:
                    return SimpleNamespace(audit_reports_path=audit_reports)

            harness = Harness()

            def _picker(**kwargs: object) -> dict[str, object]:
                captured_kwargs.update(kwargs)
                return {
                    "ok": True,
                    "canceled": False,
                    "selection_mode": kwargs["selection_mode"],
                    "paths": [str(selected_csv)],
                    "message": "Selected 1 path.",
                    "errors": [],
                }

            harness._path_picker = _picker  # type: ignore[attr-defined]

            payload = harness._path_picker_browse_payload({"target_key": "queue.rerun_csv", "initial_path": ""})

            self.assertTrue(payload["ok"], payload)
            self.assertEqual(captured_kwargs["initial_path"], str(audit_reports))
            self.assertEqual(payload["data"]["selected_path"], str(selected_csv))

    def test_rerun_csv_browse_keeps_explicit_initial_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            audit_reports = root / "LocalBase" / "AuditReports"
            explicit_csv = root / "ManualExports" / "manual_rerun.csv"
            explicit_csv.parent.mkdir(parents=True)
            explicit_csv.write_text("enabled,source_path\ntrue,C:\\Media\\Movie.mkv\n", encoding="utf-8")
            captured_kwargs: dict[str, object] = {}

            class Harness(PathPickerHarness):
                def _resolved(self) -> object:
                    return SimpleNamespace(audit_reports_path=audit_reports)

            harness = Harness()
            harness._path_picker = lambda **kwargs: (  # type: ignore[attr-defined]
                captured_kwargs.update(kwargs)
                or {
                    "ok": True,
                    "canceled": False,
                    "selection_mode": kwargs["selection_mode"],
                    "paths": [str(explicit_csv)],
                    "message": "Selected 1 path.",
                    "errors": [],
                }
            )

            payload = harness._path_picker_browse_payload(
                {"target_key": "queue.rerun_csv", "initial_path": str(explicit_csv)}
            )

            self.assertTrue(payload["ok"], payload)
            self.assertEqual(captured_kwargs["initial_path"], str(explicit_csv))

    def test_csv_target_rejects_non_csv_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "rerun.txt"
            path.write_text("path\n", encoding="utf-8")
            harness = PathPickerHarness()
            harness._path_picker = lambda **_kwargs: {  # type: ignore[attr-defined]
                "ok": True,
                "canceled": False,
                "selection_mode": "files",
                "paths": [str(path)],
                "message": "Selected 1 path.",
                "errors": [],
            }

            payload = harness._path_picker_browse_payload({"target_key": "queue.rerun_csv"})

            self.assertFalse(payload["ok"])
            self.assertEqual(payload["severity"], "warning")
            self.assertEqual(payload["data"]["validation"]["status_state"], "blocked")
            self.assertIn("not a CSV file", payload["data"]["validation"]["message"])


if __name__ == "__main__":
    unittest.main()
