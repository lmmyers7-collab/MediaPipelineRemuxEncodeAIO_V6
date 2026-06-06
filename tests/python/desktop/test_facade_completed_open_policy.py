from __future__ import annotations

import unittest
import sys
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root

sys.path.insert(0, str(find_repo_root(Path(__file__)) / "src"))

from mediapipeline.core.completed.open_policy import (
    allowed_completed_open_targets_text,
    completed_open_disallowed_target_result,
    completed_open_exception_result,
    completed_open_path,
    completed_open_path_missing_result,
    completed_open_path_service_unavailable_result,
    completed_open_read_exception_result,
    completed_open_requires_row_result,
    completed_open_row_missing_result,
    completed_open_service_unavailable_result,
    completed_open_success_result,
    completed_open_target_label,
    find_completed_record_by_key,
    normalize_completed_open_target,
)
from mediapipeline.desktop.models import CompletedJobRecord


class CompletedOpenPolicyTests(unittest.TestCase):
    def test_target_helpers_normalize_and_label_allowlisted_targets(self) -> None:
        self.assertEqual(normalize_completed_open_target(" Output_Folder "), "output_folder")
        self.assertEqual(normalize_completed_open_target(" Output_File "), "output_file")
        self.assertEqual(normalize_completed_open_target(" Play_Output_File "), "play_output_file")
        self.assertIn("output_folder", allowed_completed_open_targets_text())
        self.assertIn("output_file", allowed_completed_open_targets_text())
        self.assertIn("play_output_file", allowed_completed_open_targets_text())
        self.assertEqual(completed_open_target_label("play_output_file"), "completed output playback")
        self.assertEqual(completed_open_target_label("output_file"), "completed output file")
        self.assertEqual(completed_open_target_label("sidecar"), "completed sidecar file")

    def test_find_completed_record_by_key_ignores_non_records(self) -> None:
        record = CompletedJobRecord(
            sidecar_path=Path(r"D:\Library\Movie.pipeline.json"),
            payload={"output_path": r"D:\Library\Movie.mkv"},
        )

        found = find_completed_record_by_key(["not-a-record", record], "row-1", lambda item: "row-1")
        missing = find_completed_record_by_key([record], "row-2", lambda item: "row-1")

        self.assertIs(found, record)
        self.assertIsNone(missing)

    def test_completed_open_path_uses_manifest_owned_paths(self) -> None:
        record = CompletedJobRecord(
            sidecar_path=Path(r"D:\Library\Movie.pipeline.json"),
            payload={
                "source_path": r"E:\Source\Movie.mkv",
                "output_path": r"D:\Library\Movie.mkv",
            },
        )

        self.assertEqual(completed_open_path(record, "output_file"), Path(r"D:\Library\Movie.mkv"))
        self.assertEqual(completed_open_path(record, "play_output_file"), Path(r"D:\Library\Movie.mkv"))
        self.assertEqual(completed_open_path(record, "output_folder"), Path(r"D:\Library"))
        self.assertEqual(completed_open_path(record, "sidecar"), Path(r"D:\Library\Movie.pipeline.json"))
        self.assertEqual(completed_open_path(record, "source_folder"), Path(r"E:\Source"))
        self.assertIsNone(completed_open_path(record, "not-allowed"))

    def test_completed_open_result_helpers_preserve_command_contract(self) -> None:
        path = Path(r"D:\Library\Movie.mkv")

        self.assertEqual(completed_open_requires_row_result().warnings, ["No completed row key was provided."])
        self.assertIn("Allowed targets", completed_open_disallowed_target_result().errors[0])
        self.assertEqual(completed_open_service_unavailable_result().message, "Completed history service is not available.")
        self.assertIn("offline", completed_open_read_exception_result(OSError("offline")).message)
        self.assertEqual(completed_open_row_missing_result().severity, "warning")
        self.assertEqual(completed_open_path_missing_result("sidecar", "row-1").data, {"target": "sidecar", "row_key": "row-1"})

        open_unavailable = completed_open_path_service_unavailable_result("output_folder", "row-1", path)
        open_failed = completed_open_exception_result("output_folder", "row-1", path, RuntimeError("blocked"))
        opened = completed_open_success_result("output_file", "row-1", path)
        played = completed_open_success_result("play_output_file", "row-1", path)

        self.assertEqual(open_unavailable.data["path"], str(path))
        self.assertIn("blocked", open_failed.message)
        self.assertTrue(opened.ok)
        self.assertEqual(opened.message, "Opened completed output file.")
        self.assertEqual(played.message, "Opened completed output playback with the default app.")
        self.assertEqual(opened.refresh_hint, "completed")


if __name__ == "__main__":
    unittest.main()
