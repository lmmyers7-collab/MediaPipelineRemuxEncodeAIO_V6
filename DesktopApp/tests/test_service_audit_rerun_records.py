from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mediapipeline_desktop_app.models import AuditRecord, CompletedJobRecord, FailureRecord
from mediapipeline_desktop_app.service_audit_rerun import AuditRerunServiceMixin
from mediapipeline_desktop_app.service_audit_rerun_records import (
    audit_correlation_lookup_key,
    audit_row_value,
    correlate_audit_record,
    format_audit_correlation,
    rerun_media_kind_from_audit,
)


def _audit_record(**row: str) -> AuditRecord:
    return AuditRecord(source_csv=Path("audit.csv"), row=row)


class AuditRerunRecordHelperTests(unittest.TestCase):
    def test_lookup_key_normalizes_year_and_season_noise(self) -> None:
        self.assertEqual(
            audit_correlation_lookup_key("Show Name Season 02 (2020) S02"),
            "show name",
        )

    def test_correlate_audit_record_counts_exact_path_matches(self) -> None:
        audit = _audit_record(
            Path=r"C:\Source\Movies\Movie.mkv",
            LookupTitle="Movie (1999)",
            MediaType="Movie",
        )
        completed = CompletedJobRecord(
            sidecar_path=Path(r"C:\Library\Movies\Movie (1999)\Movie (1999).mkv.pipeline.json"),
            payload={
                "source_path": r"C:\Source\Movies\Movie.mkv",
                "output_path": r"C:\Library\Movies\Movie (1999)\Movie (1999).mkv",
                "route": "remux",
                "encoded_at": "2026-05-08T12:00:00-04:00",
            },
        )
        failure = FailureRecord(
            source_json=Path("round_failures.json"),
            payload={
                "SourcePath": r"C:\Source\Movies\Movie.mkv",
                "Stage": "encode",
                "ErrorCode": "FFMPEG_FAILED",
            },
        )

        correlation = correlate_audit_record(audit, [completed], [failure])

        self.assertEqual(correlation["completed_count"], 1)
        self.assertEqual(correlation["failure_count"], 1)
        self.assertIs(correlation["latest_completed"], completed)
        self.assertIs(correlation["latest_failure"], failure)

    def test_format_audit_correlation_reports_latest_completed_and_failure(self) -> None:
        audit = _audit_record(Path=r"C:\Source\Movies\Movie.mkv", LookupTitle="Movie", MediaType="Movie")
        completed = CompletedJobRecord(
            sidecar_path=Path(r"C:\Library\Movies\Movie\Movie.mkv.pipeline.json"),
            payload={
                "source_path": r"C:\Source\Movies\Movie.mkv",
                "output_path": r"C:\Library\Movies\Movie\Movie.mkv",
                "route": "remux",
                "encoded_at": "2026-05-08T12:00:00-04:00",
            },
        )
        failure = FailureRecord(
            source_json=Path("round_failures.json"),
            payload={
                "SourcePath": r"C:\Source\Movies\Movie.mkv",
                "Stage": "encode",
                "ErrorCode": "FFMPEG_FAILED",
            },
        )

        lines = format_audit_correlation(audit, [completed], [failure])

        self.assertIn("Completed Jobs      : 1 matched; latest REMUX", lines[0])
        self.assertEqual(lines[1], "Failure Records     : 1 matched; latest FFMPEG_FAILED")

    def test_audit_row_value_uses_first_non_empty_fallback(self) -> None:
        audit = _audit_record(MediaKind="", MediaType="TV", Bucket="priority")

        self.assertEqual(audit_row_value(audit, "MediaKind", "MediaType"), "TV")
        self.assertEqual(audit_row_value(audit, "Missing", "AlsoMissing"), "")

    def test_rerun_media_kind_maps_record_and_fallback_synonyms(self) -> None:
        self.assertEqual(rerun_media_kind_from_audit(_audit_record(MediaType="episode")), "TV")
        self.assertEqual(rerun_media_kind_from_audit(_audit_record(MediaType="", MediaKind="film")), "Movie")
        self.assertEqual(rerun_media_kind_from_audit(_audit_record(MediaType="", MediaKind="unknown")), "")

    def test_service_wrapper_methods_preserve_public_behavior(self) -> None:
        service = AuditRerunServiceMixin()
        audit = _audit_record(
            Path=r"C:\Source\TV\Show\Season 02\Episode.mkv",
            LookupTitle="Show Season 02",
            MediaType="TV",
        )

        self.assertEqual(service._audit_correlation_lookup_key("Show Season 02 (2020)"), "show")
        self.assertEqual(service._audit_row_value(audit, "Missing", "MediaType"), "TV")
        self.assertEqual(service._rerun_media_kind_from_audit(audit), "TV")
        self.assertEqual(service.correlate_audit_record(audit, [], [])["completed_count"], 0)
        self.assertEqual(
            service.format_audit_correlation(audit, [], []),
            ["Completed Jobs      : (none)", "Failure Records     : (none)"],
        )


if __name__ == "__main__":
    unittest.main()
