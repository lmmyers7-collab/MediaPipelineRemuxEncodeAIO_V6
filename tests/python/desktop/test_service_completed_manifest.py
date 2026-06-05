from __future__ import annotations

import json
import logging
import sys
import tempfile
import unittest
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root

sys.path.insert(0, str(find_repo_root(Path(__file__)) / "src"))

from mediapipeline.desktop.models import CompletedJobRecord
from mediapipeline.core.completed.manifest import (
    annotate_completed_output_health,
    completed_sidecar_path_from_payload,
    read_completed_manifest_records,
)


class CompletedManifestHelperTests(unittest.TestCase):
    def _logger(self) -> logging.Logger:
        logger = logging.getLogger("test_completed_manifest")
        logger.handlers.clear()
        logger.addHandler(logging.NullHandler())
        logger.propagate = False
        return logger

    def test_completed_sidecar_path_uses_output_path_or_manifest_fallback(self) -> None:
        manifest = Path("completed_jobs.jsonl")

        self.assertEqual(
            completed_sidecar_path_from_payload(manifest, {"output_path": r"C:\Media\Movie.mkv"}),
            Path(r"C:\Media\Movie.pipeline.json"),
        )
        self.assertEqual(completed_sidecar_path_from_payload(manifest, {}), manifest)

    def test_read_completed_manifest_records_reverses_skips_bad_rows_and_marks_health(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            first_output = root / "First.mkv"
            first_output.write_text("media", encoding="utf-8")
            missing_output = root / "Missing.mkv"
            manifest = root / "completed_jobs.jsonl"
            manifest.write_text(
                "\ufeff"
                + json.dumps({"output_path": str(first_output), "route": "remux"})
                + "\nnot-json\n[]\n"
                + json.dumps({"output_path": str(missing_output), "route": "encode"})
                + "\n"
                + json.dumps({"output_file": "NoOutputPath.mkv", "route": "copy"})
                + "\n",
                encoding="utf-8",
            )

            rows = read_completed_manifest_records(
                manifest,
                limit=10,
                logger=self._logger(),
            )

        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0].sidecar_path, manifest)
        self.assertEqual(rows[0].payload["_diagnostics_output_exists"], False)
        self.assertEqual(rows[0].payload["_diagnostics_output_health"], "completed metadata without media")
        self.assertEqual(rows[1].output_path, missing_output)
        self.assertEqual(rows[1].payload["_diagnostics_output_exists"], False)
        self.assertEqual(rows[2].output_path, first_output)
        self.assertEqual(rows[2].payload["_diagnostics_output_exists"], True)
        self.assertEqual(rows[2].payload["_diagnostics_output_health"], "ok")

    def test_read_completed_manifest_records_honors_limit_after_recent_first_ordering(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            manifest = Path(td) / "completed_jobs.jsonl"
            manifest.write_text(
                json.dumps({"output_file": "old.mkv"}) + "\n" + json.dumps({"output_file": "new.mkv"}) + "\n",
                encoding="utf-8",
            )

            rows = read_completed_manifest_records(
                manifest,
                limit=1,
                logger=self._logger(),
            )

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].payload["output_file"], "new.mkv")

    def test_read_completed_manifest_records_accepts_no_limit_for_full_history(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            manifest = Path(td) / "completed_jobs.jsonl"
            manifest.write_text(
                "\n".join(json.dumps({"output_file": f"movie-{index}.mkv"}) for index in range(3)) + "\n",
                encoding="utf-8",
            )

            rows = read_completed_manifest_records(
                manifest,
                limit=None,
                logger=self._logger(),
            )

        self.assertEqual([row.payload["output_file"] for row in rows], ["movie-2.mkv", "movie-1.mkv", "movie-0.mkv"])

    def test_annotate_completed_output_health_handles_existence_errors(self) -> None:
        class RaisingRecord(CompletedJobRecord):
            @property
            def output_path(self) -> Path:  # type: ignore[override]
                raise OSError("offline share")

        record = RaisingRecord(sidecar_path=Path("sidecar.pipeline.json"), payload={})

        annotate_completed_output_health(record)

        self.assertFalse(record.payload["_diagnostics_output_exists"])
        self.assertIn("offline share", record.payload["_diagnostics_output_health"])


if __name__ == "__main__":
    unittest.main()
