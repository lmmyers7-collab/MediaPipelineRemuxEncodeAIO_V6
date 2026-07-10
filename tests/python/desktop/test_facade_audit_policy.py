from __future__ import annotations

import sys
import unittest
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root

sys.path.insert(0, str(find_repo_root(Path(__file__)) / "src"))

from mediapipeline.core.audit.preview_policy import (
    AUDIT_EMPTY_CSV_MESSAGE,
    AUDIT_LOADER_UNAVAILABLE_MESSAGE,
    AUDIT_NO_CSV_REPORT_MESSAGE,
    AUDIT_REPORT_SERVICE_UNAVAILABLE_MESSAGE,
    audit_duplicate_group_metadata,
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
from mediapipeline.desktop.models import AuditRecord


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
        self.assertFalse(row["duplicate_group"])
        self.assertEqual(row["duplicate_group_size"], 0)

    def test_preview_fields_count_visible_buckets_and_truncation(self) -> None:
        records = [
            _record(lookup_title="Show", bucket="RERUN_PIPELINE", priority="HIGH", path="C:/TV/Show/Show - S01E01.mkv"),
            _record(
                lookup_title="Movie (1979)",
                media_type="Movie",
                bucket="REDOWNLOAD_CANDIDATE",
                priority="LOW",
                path="C:/Movies/Movie (1979).mkv",
            ),
            _record(lookup_title="Other", bucket="REVIEW", priority="MEDIUM", path="C:/Movies/Other.mkv"),
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
        self.assertEqual(fields["medium_priority_count"], 1)
        self.assertEqual(fields["priority_count"], 2)
        self.assertEqual(fields["rerun_count"], 1)
        self.assertEqual(fields["redownload_count"], 1)
        self.assertEqual(fields["review_count"], 1)
        self.assertEqual(fields["actionable_count"], 3)
        self.assertEqual(fields["duplicate_group_count"], 0)
        self.assertEqual(fields["warnings"], ["Showing 2 of 3 audit row(s)."])

    def test_duplicate_group_count_uses_normalized_lookup_titles(self) -> None:
        records = [
            _record(lookup_title="Movie (1979)", media_type="Movie", path="C:/Movies/Movie (1979).mkv"),
            _record(lookup_title="Movie", media_type="Movie", path="C:/Other/Movie.mkv", relative_path="Other\\Movie.mkv"),
            _record(lookup_title="Another Movie", media_type="Movie", path="C:/Movies/Another Movie.mkv"),
        ]

        self.assertEqual(audit_duplicate_group_count(records), 1)

    def test_duplicate_group_metadata_marks_same_leaf_duplicate_rows(self) -> None:
        records = [
            _record(
                path="C:/Movies/Library One/Jurassic World Fallen Kingdom (2018).mkv",
                relative_path="Library One\\Jurassic World Fallen Kingdom (2018).mkv",
                lookup_title="Jurassic World Fallen Kingdom (2018)",
                media_type="Movie",
            ),
            _record(
                path="D:/Outsource/Movies/Jurassic World Fallen Kingdom (2018).mkv",
                relative_path="Movies\\Jurassic World Fallen Kingdom (2018).mkv",
                lookup_title="Jurrasic World Fallen Kingdom (2018)",
                media_type="Movie",
                issue="bdpgs-only-subtitles",
            ),
            _record(
                path="C:/Movies/Unique (2001).mkv",
                relative_path="Unique (2001).mkv",
                lookup_title="Unique (2001)",
                media_type="Movie",
            ),
        ]

        fields = audit_preview_fields(
            records,
            source="audit_summary_latest.csv",
            priority_only=False,
            limit=100,
            empty_warning="No rows.",
        )
        duplicate_rows = [row for row in fields["rows"] if row["duplicate_group"]]
        metadata = audit_duplicate_group_metadata(records)

        self.assertEqual(fields["duplicate_group_count"], 1)
        self.assertEqual(len(duplicate_rows), 2)
        self.assertEqual({row["duplicate_group_type"] for row in duplicate_rows}, {"same_leaf"})
        self.assertEqual({row["duplicate_group_size"] for row in duplicate_rows}, {2})
        self.assertEqual(len(metadata), 2)

    def test_tv_episode_sets_are_not_title_duplicate_groups(self) -> None:
        records = [
            _record(
                path="C:/TV/Show/Season 01/Show - S01E01.mkv",
                relative_path="Show\\Season 01\\Show - S01E01.mkv",
                lookup_title="Show",
                media_type="TV",
            ),
            _record(
                path="C:/TV/Show/Season 01/Show - S01E02.mkv",
                relative_path="Show\\Season 01\\Show - S01E02.mkv",
                lookup_title="Show",
                media_type="TV",
            ),
        ]

        fields = audit_preview_fields(
            records,
            source="audit_summary_latest.csv",
            priority_only=False,
            limit=100,
            empty_warning="No rows.",
        )

        self.assertEqual(audit_duplicate_group_count(records), 0)
        self.assertEqual(fields["duplicate_group_count"], 0)
        self.assertFalse(any(row["duplicate_group"] for row in fields["rows"]))

    def test_ignored_records_do_not_drive_preview_counts_or_duplicates(self) -> None:
        ignored_path = "C:/Movies/Dupe.mkv"
        records = [
            _record(
                path=ignored_path,
                relative_path="Ignored\\Dupe.mkv",
                lookup_title="Dupe (1979)",
                media_type="Movie",
                bucket="REDOWNLOAD_CANDIDATE",
                priority="HIGH",
            ),
            _record(
                path="D:/Movies/Dupe.mkv",
                relative_path="Visible\\Dupe.mkv",
                lookup_title="Dupe",
                media_type="Movie",
                bucket="REVIEW",
                priority="LOW",
            ),
        ]

        fields = audit_preview_fields(
            records,
            source="audit_summary_latest.csv",
            priority_only=False,
            limit=100,
            empty_warning="No rows.",
            ignore_manifest={
                "version": 1,
                "entries": {"c:/movies/dupe.mkv": {"reason": "operator reviewed"}},
            },
        )

        self.assertEqual(fields["count"], 1)
        self.assertEqual(fields["total_count"], 2)
        self.assertEqual(fields["ignored_count"], 1)
        self.assertEqual(fields["high_priority_count"], 0)
        self.assertEqual(fields["medium_priority_count"], 0)
        self.assertEqual(fields["priority_count"], 0)
        self.assertEqual(fields["redownload_count"], 0)
        self.assertEqual(fields["review_count"], 1)
        self.assertEqual(fields["actionable_count"], 0)
        self.assertEqual(fields["duplicate_group_count"], 0)
        self.assertEqual(len(fields["rows"]), 1)
        self.assertFalse(fields["rows"][0]["duplicate_group"])
        self.assertEqual(fields["warnings"], ["1 audit row(s) hidden by the audit ignore manifest."])

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
        self.assertEqual(fields["actionable_count"], 0)
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
        self.assertEqual(loader_missing.error, AUDIT_LOADER_UNAVAILABLE_MESSAGE)
        self.assertEqual(read_error.warnings, ["Audit CSV could not be read: bad csv"])
        self.assertEqual(read_error.error, "Audit CSV could not be read: bad csv")

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
