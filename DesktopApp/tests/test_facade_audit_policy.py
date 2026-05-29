from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.audit.preview_policy import (
    AUDIT_EMPTY_CSV_MESSAGE,
    AUDIT_LOADER_UNAVAILABLE_MESSAGE,
    AUDIT_NO_CSV_REPORT_MESSAGE,
    AUDIT_REPORT_SERVICE_UNAVAILABLE_MESSAGE,
    audit_csv_read_error_result,
    audit_duplicate_group_count,
    audit_latest_csv_resolution_error_result,
    audit_loader_unavailable_result,
    audit_no_csv_report_result,
    audit_preview_fields,
    audit_preview_from_records,
    audit_report_service_unavailable_result,
    audit_record_to_row,
    bounded_audit_limit,
)
from mediapipeline_desktop_app.models import AuditRecord


def _record(
    *,
    source_csv: str = "C:/Reports/audit.csv",
    path: str = "C:/Source/TV/Show/Season 01/Show - S01E01.mkv",
    relative_path: str = "Show\\Season 01\\Show - S01E01.mkv",
    lookup_title: str = "Show",
    media_type: str = "TV",
    bucket: str = "RERUN_PIPELINE",
    priority: str = "HIGH",
    score: str = "90",
    issue: str = "subtitle_srt_required",
) -> AuditRecord:
    return AuditRecord(
        source_csv=Path(source_csv),
        row={
            "Path": path,
            "RelativePath": relative_path,
            "LookupTitle": lookup_title,
            "MediaType": media_type,
            "EffectiveBucket": bucket,
            "PriorityFixLevel": priority,
            "PriorityScore": score,
            "PrimaryIssueCode": issue,
            "PrimarySuggestedAction": "Rerun pipeline.",
            "IssueMessages": "Preferred-language SRT missing.",
        },
    )


class AuditFacadePolicyTests(unittest.TestCase):
    def test_bounded_limit_matches_existing_audit_preview_bounds(self) -> None:
        self.assertEqual(bounded_audit_limit(None), 100)
        self.assertEqual(bounded_audit_limit("bad"), 100)
        self.assertEqual(bounded_audit_limit(0), 100)
        self.assertEqual(bounded_audit_limit(-5), 1)
        self.assertEqual(bounded_audit_limit(999), 500)
        self.assertEqual(bounded_audit_limit("25"), 25)

    def test_audit_record_row_preserves_report_fields(self) -> None:
        record = _record()
        row = audit_record_to_row(record)

        self.assertEqual(row["path"], str(Path("C:/Source/TV/Show/Season 01/Show - S01E01.mkv")))
        self.assertEqual(row["relative_path"], "Show\\Season 01\\Show - S01E01.mkv")
        self.assertEqual(row["lookup_title"], "Show")
        self.assertEqual(row["media_type"], "TV")
        self.assertEqual(row["effective_bucket"], "RERUN_PIPELINE")
        self.assertEqual(row["priority_fix_level"], "HIGH")
        self.assertEqual(row["priority_score"], 90)
        self.assertEqual(row["primary_issue_code"], "subtitle_srt_required")
        self.assertEqual(row["primary_suggested_action"], "Rerun pipeline.")
        self.assertEqual(row["issue_messages"], "Preferred-language SRT missing.")
        self.assertEqual(row["source_csv"], str(Path("C:/Reports/audit.csv")))

    def test_preview_fields_count_visible_buckets_and_truncation(self) -> None:
        records = [
            _record(lookup_title="Show", bucket="RERUN_PIPELINE", priority="HIGH"),
            _record(lookup_title="Movie (1979)", media_type="Movie", bucket="REDOWNLOAD_CANDIDATE", priority="LOW"),
            _record(lookup_title="Other", bucket="REVIEW", priority="HIGH"),
            "not-a-record",
        ]

        fields = audit_preview_fields(
            records,
            source="audit_summary_latest.csv",
            priority_only=True,
            limit=2,
            empty_warning="No rows.",
        )

        self.assertEqual(fields["source"], "audit_summary_latest.csv")
        self.assertTrue(fields["priority_only"])
        self.assertEqual(fields["count"], 3)
        self.assertEqual(len(fields["rows"]), 2)
        self.assertEqual(fields["high_priority_count"], 1)
        self.assertEqual(fields["rerun_count"], 1)
        self.assertEqual(fields["redownload_count"], 1)
        self.assertEqual(fields["review_count"], 0)
        self.assertEqual(fields["duplicate_group_count"], 0)
        self.assertEqual(fields["warnings"], ["Showing 2 of 3 audit row(s)."])

    def test_duplicate_group_count_uses_normalized_lookup_titles(self) -> None:
        records = [
            _record(lookup_title="Movie (1979)", media_type="Movie"),
            _record(lookup_title="Movie", media_type="Movie", path="C:/Other/Movie.mkv", relative_path="Other\\Movie.mkv"),
            _record(lookup_title="Another Movie", media_type="Movie"),
        ]

        self.assertEqual(audit_duplicate_group_count(records), 1)

    def test_empty_preview_fields_keep_operator_warning(self) -> None:
        fields = audit_preview_fields(
            [],
            source="audit_summary_latest.csv",
            priority_only=False,
            limit=100,
            empty_warning="Latest audit CSV contains no rows.",
        )

        self.assertFalse(fields["priority_only"])
        self.assertEqual(fields["count"], 0)
        self.assertEqual(fields["duplicate_group_count"], 0)
        self.assertEqual(fields["warnings"], ["Latest audit CSV contains no rows."])

    def test_audit_preview_dto_helpers_preserve_warning_contracts(self) -> None:
        service_missing = audit_report_service_unavailable_result(priority_only=True)
        latest_error = audit_latest_csv_resolution_error_result(False, RuntimeError("offline"))
        no_report = audit_no_csv_report_result(False)
        loader_missing = audit_loader_unavailable_result(Path("C:/Reports/audit.csv"), True)
        read_error = audit_csv_read_error_result(Path("C:/Reports/audit.csv"), False, RuntimeError("bad csv"))

        self.assertTrue(service_missing.priority_only)
        self.assertEqual(service_missing.warnings, [AUDIT_REPORT_SERVICE_UNAVAILABLE_MESSAGE])
        self.assertEqual(latest_error.warnings, ["Latest audit CSV could not be resolved: offline"])
        self.assertEqual(no_report.warnings, [AUDIT_NO_CSV_REPORT_MESSAGE])
        self.assertEqual(loader_missing.source, str(Path("C:/Reports/audit.csv")))
        self.assertEqual(loader_missing.warnings, [AUDIT_LOADER_UNAVAILABLE_MESSAGE])
        self.assertEqual(read_error.warnings, ["Audit CSV could not be read: bad csv"])

    def test_audit_preview_from_records_wraps_fields_in_dto(self) -> None:
        preview = audit_preview_from_records(
            [_record()],
            source="audit_summary_latest.csv",
            priority_only=False,
            limit=100,
            empty_warning=AUDIT_EMPTY_CSV_MESSAGE,
        )

        self.assertEqual(preview.source, "audit_summary_latest.csv")
        self.assertEqual(preview.count, 1)
        self.assertEqual(preview.rerun_count, 1)
        self.assertEqual(preview.warnings, [])


if __name__ == "__main__":
    unittest.main()
