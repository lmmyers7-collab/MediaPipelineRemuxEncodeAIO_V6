from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.failures.policy import (
    FAILURE_JSON_EMPTY_MESSAGE,
    FAILURE_LOADER_UNAVAILABLE_MESSAGE,
    FAILURE_MARKER_SERVICE_UNAVAILABLE_MESSAGE,
    FAILURE_NO_JSON_REPORT_MESSAGE,
    FAILURE_REPORT_SERVICE_UNAVAILABLE_MESSAGE,
    bounded_failure_limit,
    failure_json_read_error_result,
    failure_latest_json_resolution_error_result,
    failure_loader_unavailable_result,
    failure_marker_lookup,
    failure_marker_service_unavailable_result,
    failure_markers_read_error_result,
    failure_no_json_report_result,
    failure_preview_fields,
    failure_preview_from_records,
    failure_report_service_unavailable_result,
    failure_record_to_row,
    normalize_failure_source_kind,
)
from mediapipeline_desktop_app.models import FailureRecord


def _record(
    *,
    source_json: str = "C:/Reports/failure.json",
    source_path: str = "C:/Source/Movies/Movie (2024)/Movie.mkv",
    classification: str = "operator_required",
    stage: str = "encode",
    error_code: str = "ENCODE_FAILED",
) -> FailureRecord:
    return FailureRecord(
        source_json=Path(source_json),
        payload={
            "SourcePath": source_path,
            "JobId": "job-123",
            "CorrelationId": "run-456",
            "Stage": stage,
            "Reason": "Pipeline stage failed.",
            "Classification": classification,
            "ErrorCode": error_code,
            "ArtifactPath": "C:/Reports/artifact.json",
            "ReproPath": "C:/Reports/repro.txt",
            "SuggestedAction": "Review manually.",
            "SuggestedRename": "Movie (2024)",
            "RecordedAt": "2026-05-07T22:00:00-04:00",
            "RetryCount": "2",
            "RetryLimit": "5",
            "Escalated": "true",
        },
    )


class FailureFacadePolicyTests(unittest.TestCase):
    def test_source_kind_and_limit_normalization_match_facade_contract(self) -> None:
        self.assertEqual(normalize_failure_source_kind(None), "latest_json")
        self.assertEqual(normalize_failure_source_kind(" Markers "), "markers")
        self.assertEqual(normalize_failure_source_kind("Custom"), "custom")
        self.assertEqual(bounded_failure_limit(None), 100)
        self.assertEqual(bounded_failure_limit("bad"), 100)
        self.assertEqual(bounded_failure_limit(0), 100)
        self.assertEqual(bounded_failure_limit(-10), 1)
        self.assertEqual(bounded_failure_limit(999), 500)
        self.assertEqual(bounded_failure_limit("25"), 25)

    def test_failure_record_row_preserves_operator_fields(self) -> None:
        record = _record(source_path="C:/Source/TV/Show/Season 01/Show - S01E01.mkv")
        row = failure_record_to_row(record)

        self.assertEqual(row["source_path"], "C:/Source/TV/Show/Season 01/Show - S01E01.mkv")
        self.assertEqual(row["job_id"], "job-123")
        self.assertEqual(row["correlation_id"], "run-456")
        self.assertEqual(row["stage"], "encode")
        self.assertEqual(row["reason"], "Pipeline stage failed.")
        self.assertEqual(row["classification"], "operator_required")
        self.assertEqual(row["error_code"], "ENCODE_FAILED")
        self.assertEqual(row["media_type"], "TV")
        self.assertEqual(row["lookup_title"], "Show (Season 01)")
        self.assertEqual(row["recorded_at"], "2026-05-07T22:00:00-04:00")
        self.assertEqual(row["retry_count"], 2)
        self.assertEqual(row["retry_limit"], 5)
        self.assertFalse(row["retry_allowed"])
        self.assertEqual(row["retry_status_state"], "blocked")
        self.assertEqual(row["retry_route_or_command"], "none_exposed")
        self.assertTrue(row["escalated"])
        self.assertEqual(row["artifact_path"], str(Path("C:/Reports/artifact.json")))
        self.assertEqual(row["repro_path"], str(Path("C:/Reports/repro.txt")))
        self.assertEqual(row["suggested_action"], "Review manually.")
        self.assertEqual(row["suggested_rename"], "Movie (2024)")
        self.assertEqual(row["source_json"], str(Path("C:/Reports/failure.json")))
        self.assertEqual(row["triage"]["status_label"], "Needs operator")
        self.assertEqual(row["triage"]["severity"], "blocked")
        self.assertEqual(row["triage"]["plain_summary"], "Pipeline stage failed.")
        self.assertEqual(row["triage"]["suggested_fix"], "Review manually.")
        self.assertFalse(row["clear_error"]["available"])
        self.assertIn("could not be loaded", row["clear_error"]["unavailable_reason"])

    def test_failure_marker_lookup_and_marker_rows_enable_clear_error(self) -> None:
        record = _record(
            source_json="C:/State/Failures/Markers/one.json",
            source_path="C:/Source/Movies/Movie (2024)/Movie.mkv",
        )
        lookup = failure_marker_lookup([record])
        row = failure_record_to_row(record, source_kind="markers", marker_lookup=lookup)

        self.assertIn("c:\\source\\movies\\movie (2024)\\movie.mkv", lookup)
        self.assertTrue(row["clear_error"]["available"])
        self.assertEqual(row["clear_error"]["marker_path"], str(Path("C:/State/Failures/Markers/one.json")))
        self.assertEqual(row["clear_error"]["marker_paths"], [str(Path("C:/State/Failures/Markers/one.json"))])

    def test_failure_preview_fields_count_visible_classifications_and_truncation(self) -> None:
        records = [
            _record(classification="operator_required", error_code="ONE"),
            _record(classification="permanent", error_code="TWO"),
            _record(classification="transient", error_code="THREE"),
            "not-a-record",
        ]

        fields = failure_preview_fields(
            records,
            source="latest_failures.json",
            source_kind="latest_json",
            limit=2,
            empty_warning="No rows.",
        )

        self.assertEqual(fields["source"], "latest_failures.json")
        self.assertEqual(fields["source_kind"], "latest_json")
        self.assertEqual(fields["count"], 3)
        self.assertEqual(len(fields["rows"]), 2)
        self.assertEqual(fields["operator_required_count"], 1)
        self.assertEqual(fields["permanent_count"], 1)
        self.assertEqual(fields["transient_count"], 0)
        self.assertEqual(fields["retry_state"]["schema_version"], "desktop_retry_state.v1")
        self.assertEqual(fields["retry_state"]["row_count"], 2)
        self.assertEqual(fields["retry_state"]["blocked_count"], 2)
        self.assertEqual(fields["retry_state"]["status_state"], "blocked")
        self.assertEqual(fields["warnings"], ["Showing 2 of 3 failure row(s)."])

    def test_empty_failure_preview_fields_keep_operator_warning(self) -> None:
        fields = failure_preview_fields(
            [],
            source="markers",
            source_kind="markers",
            limit=100,
            empty_warning="No failure markers are available from the state store.",
        )

        self.assertEqual(fields["rows"], [])
        self.assertEqual(fields["count"], 0)
        self.assertEqual(fields["operator_required_count"], 0)
        self.assertEqual(fields["permanent_count"], 0)
        self.assertEqual(fields["transient_count"], 0)
        self.assertEqual(fields["retry_state"]["status_state"], "idle")
        self.assertEqual(fields["retry_state"]["read_only"], True)
        self.assertEqual(fields["warnings"], ["No failure markers are available from the state store."])

    def test_failure_preview_dto_helpers_preserve_warning_contracts(self) -> None:
        marker_service_missing = failure_marker_service_unavailable_result()
        markers_read_error = failure_markers_read_error_result(Path("C:/State/Failures/Markers"), RuntimeError("locked"))
        report_service_missing = failure_report_service_unavailable_result()
        latest_json_error = failure_latest_json_resolution_error_result(RuntimeError("offline"))
        no_report = failure_no_json_report_result()
        loader_missing = failure_loader_unavailable_result(Path("C:/Reports/failures.json"))
        json_read_error = failure_json_read_error_result(Path("C:/Reports/failures.json"), RuntimeError("bad json"))

        self.assertEqual(marker_service_missing.source_kind, "markers")
        self.assertEqual(marker_service_missing.warnings, [FAILURE_MARKER_SERVICE_UNAVAILABLE_MESSAGE])
        self.assertEqual(markers_read_error.source, str(Path("C:/State/Failures/Markers")))
        self.assertEqual(markers_read_error.warnings, ["Failure markers could not be read: locked"])
        self.assertEqual(report_service_missing.warnings, [FAILURE_REPORT_SERVICE_UNAVAILABLE_MESSAGE])
        self.assertEqual(latest_json_error.warnings, ["Latest failure JSON could not be resolved: offline"])
        self.assertEqual(no_report.warnings, [FAILURE_NO_JSON_REPORT_MESSAGE])
        self.assertEqual(loader_missing.warnings, [FAILURE_LOADER_UNAVAILABLE_MESSAGE])
        self.assertEqual(json_read_error.warnings, ["Failure JSON could not be read: bad json"])

    def test_failure_preview_from_records_wraps_fields_in_dto(self) -> None:
        preview = failure_preview_from_records(
            [_record()],
            source="latest_failures.json",
            source_kind="latest_json",
            limit=100,
            empty_warning=FAILURE_JSON_EMPTY_MESSAGE,
        )

        self.assertEqual(preview.source, "latest_failures.json")
        self.assertEqual(preview.count, 1)
        self.assertEqual(preview.operator_required_count, 1)
        self.assertEqual(preview.retry_state["schema_version"], "desktop_retry_state.v1")
        self.assertEqual(preview.warnings, [])

    def test_retry_state_allows_transient_rows_before_limit(self) -> None:
        preview = failure_preview_from_records(
            [
                _record(
                    classification="transient",
                    error_code="SOURCE_LOCKED",
                    source_path="C:/Source/Movies/Movie (2024)/Movie.mkv",
                )
            ],
            source="markers",
            source_kind="markers",
            limit=100,
            empty_warning=FAILURE_JSON_EMPTY_MESSAGE,
        ).to_mapping()

        self.assertEqual(preview["retry_state"]["schema_version"], "desktop_retry_state.v1")
        self.assertEqual(preview["retry_state"]["status_state"], "retrying")
        self.assertEqual(preview["retry_state"]["retryable_count"], 1)
        self.assertEqual(preview["retry_state"]["rows"][0]["attempt"], 2)
        self.assertEqual(preview["retry_state"]["rows"][0]["max_attempts"], 5)
        self.assertTrue(preview["retry_state"]["rows"][0]["retry_allowed"])
        self.assertEqual(preview["rows"][0]["retry_status_state"], "retrying")
        self.assertIn("next backend queue pass", preview["rows"][0]["retry_safe_next_action"])
        self.assertTrue(preview["rows"][0]["clear_error"]["available"])
        self.assertEqual(preview["rows"][0]["clear_error"]["marker_paths"], [str(Path("C:/Reports/failure.json"))])


if __name__ == "__main__":
    unittest.main()
