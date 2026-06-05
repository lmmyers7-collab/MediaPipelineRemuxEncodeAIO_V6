from __future__ import annotations

import unittest
from pathlib import Path

from mediapipeline.core.status.summary_sections import (
    append_audit_progress_section,
    append_latest_path_section,
    append_plain_section,
    append_progress_section,
)


class StatusSummarySectionsTests(unittest.TestCase):
    def test_append_plain_section_omits_empty_values(self) -> None:
        lines: list[str] = ["header"]
        append_plain_section(lines, "Recent errors", "-------------", [])
        self.assertEqual(lines, ["header"])

    def test_append_progress_section_includes_stale_health(self) -> None:
        lines: list[str] = []
        append_progress_section(
            lines,
            progress={
                "ProgressVersion": "v1",
                "LastUpdate": "2026-05-08T01:02:03",
                "Status": "Running",
                "CurrentStage": "Encode",
                "CurrentStagePercent": 25,
                "CurrentRoute": "encode",
                "CurrentQueuePhase": "processing",
                "CurrentQueueIndex": 1,
                "CurrentQueueTotal": 3,
                "CurrentFile": "Movie.mkv",
                "CurrentFilePath": r"D:\scratch\Movie.mkv",
                "TotalProcessed": 2,
                "Encoded": 1,
                "Remuxed": 1,
                "Failed": 0,
                "Movies": 1,
                "TVEpisodes": 1,
            },
            progress_is_stale=True,
        )
        text = "\n".join(lines)
        self.assertIn("Progress", text)
        self.assertIn("Queue position   : 1 / 3", text)
        self.assertIn("Progress health  : STALE - pipeline_progress.json is not updating.", text)

    def test_append_audit_progress_section_reports_write_failures_and_stale_state(self) -> None:
        lines: list[str] = []
        append_audit_progress_section(
            lines,
            audit_progress={
                "last_update": "2026-05-08T01:02:03",
                "status": "Running",
                "processed_files": 4,
                "total_files": 10,
                "current_file": "Episode.mkv",
                "current_operation": "probe",
                "progress_persistence_healthy": False,
            },
            audit_progress_is_stale=True,
        )
        text = "\n".join(lines)
        self.assertIn("Progress health  : write failures", text)
        self.assertIn("Audit health     : STALE - audit_progress.json is not updating.", text)

    def test_append_latest_path_section_formats_optional_paths(self) -> None:
        lines: list[str] = []
        append_latest_path_section(lines, "Latest audit CSV", "----------------", None)
        self.assertEqual(lines, [])
        append_latest_path_section(lines, "Latest audit CSV", "----------------", Path(r"D:\audit.csv"))
        self.assertEqual(lines, ["", "Latest audit CSV", "----------------", str(Path(r"D:\audit.csv"))])


if __name__ == "__main__":
    unittest.main()
