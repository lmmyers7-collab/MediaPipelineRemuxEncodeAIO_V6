from __future__ import annotations

import sys
import unittest
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root

sys.path.insert(0, str(find_repo_root(Path(__file__)) / "src"))

from mediapipeline.core.failures.policy import (
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
from mediapipeline.desktop.models import FailureRecord


def _record(
    *,
    source_json: str = "C:/Reports/failure.json",
    source_path: str = "C:/Source/Movies/Movie (2024)/Movie.mkv",
    classification: str = "operator_required",
    stage: str = "encode",
    error_code: str = "ENCODE_FAILED",
    retryable: str | None = None,
    payload_updates: dict[str, object] | None = None,
) -> FailureRecord:
    payload = {
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
    }
    if retryable is not None:
        payload["Retryable"] = retryable
    if payload_updates:
        payload.update(payload_updates)
    return FailureRecord(
        source_json=Path(source_json),
        payload=payload,
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
        self.assertFalse(row["evidence_details"]["structured"])
        self.assertIn("No structured proof", row["evidence_details"]["summary_lines"][0])
        self.assertFalse(row["clear_error"]["available"])
        self.assertIn("could not be loaded", row["clear_error"]["unavailable_reason"])

    def test_failure_record_row_lists_structured_video_stream_evidence(self) -> None:
        record = _record(
            stage="video-stream-policy",
            error_code="SOURCE_VIDEO_STREAMS_UNVETTED",
            payload_updates={
                "video_stream_evidence": {
                    "schema_version": "pipeline_failure_video_stream_evidence.v1",
                    "route": "encode",
                    "source_real_video_stream_count": 2,
                    "source_attached_picture_stream_count": 1,
                    "source_streams": [
                        {"source": "source", "index": 0, "ordinal": 0, "codec": "hevc", "width": 1920, "height": 1080},
                        {"source": "source", "index": 2, "ordinal": 1, "codec": "h264", "width": 1280, "height": 720},
                        {
                            "source": "source",
                            "index": 5,
                            "ordinal": -1,
                            "codec": "mjpeg",
                            "width": 600,
                            "height": 900,
                            "attached_picture": True,
                        },
                    ],
                }
            },
        )

        row = failure_record_to_row(record)
        details = row["evidence_details"]

        self.assertEqual(details["schema_version"], "desktop_failure_evidence_details.v1")
        self.assertTrue(details["structured"])
        self.assertIn("video_stream_evidence", details["source"])
        self.assertIn("Video streams: source real=2, attached=1", details["summary_lines"])
        labels = [stream["label"] for stream in details["stream_rows"]]
        self.assertIn("source v:0 hevc 1920x1080", labels)
        self.assertIn("source v:2 h264 1280x720", labels)
        self.assertIn("source v:5 mjpeg 600x900 attached-picture", labels)
        self.assertIn({"label": "Route", "value": "encode"}, details["proof_fields"])
        self.assertTrue(row["triage"]["detail_available"])

    def test_failure_record_row_normalizes_legacy_video_inventory_payload(self) -> None:
        record = _record(
            stage="subtitle-burn-video-stream-policy",
            error_code="SUBTITLE_BURN_MULTI_VIDEO_UNSUPPORTED",
            payload_updates={
                "source_video_stream_count": 2,
                "subtitle_burn_stream": "s:3",
                "video_stream_inventory": {
                    "RealVideoStreamCount": 2,
                    "AttachedPicCount": 0,
                    "RealVideoStreams": [
                        {"Index": 0, "VideoOrdinal": 0, "Codec": "hevc", "Width": 3840, "Height": 2160},
                        {"Index": 1, "VideoOrdinal": 1, "Codec": "mjpeg", "Width": 1920, "Height": 1080},
                    ],
                    "AttachedPicStreams": [],
                },
            },
        )

        details = failure_record_to_row(record)["evidence_details"]

        self.assertTrue(details["structured"])
        self.assertIn("Video streams: source real=2, attached=0", details["summary_lines"])
        self.assertEqual([stream["label"] for stream in details["stream_rows"]][:2], [
            "source v:0 hevc 3840x2160",
            "source v:1 mjpeg 1920x1080",
        ])
        self.assertIn({"label": "Subtitle burn stream", "value": "s:3"}, details["proof_fields"])

    def test_failure_record_row_lists_subtitle_failure_details(self) -> None:
        record = _record(
            stage="subtitle-extract",
            error_code="SUBTITLE_BDPGS_OCR_FAILED",
            classification="transient",
            payload_updates={
                "subtitle_failure_details": {
                    "schema_version": "pipeline_failure_subtitle_evidence.v1",
                    "family": "bdpgs",
                    "failure_count": 2,
                    "failures": [
                        {
                            "stream_index": 4,
                            "error_code": "SUBTITLE_BDPGS_OCR_FAILED",
                            "reason": "PgsToSrt exited 1",
                            "repro_path": "C:/Reports/subtitle-repro.ps1",
                            "tool": "bdpgs-ocr",
                        },
                        {
                            "stream_index": 6,
                            "error_code": "SUBTITLE_BDPGS_OCR_FAILED",
                            "reason": "OCR language data missing",
                        },
                    ],
                }
            },
        )

        details = failure_record_to_row(record)["evidence_details"]

        self.assertTrue(details["structured"])
        self.assertIn("Subtitle failures: 2 recorded (bdpgs)", details["summary_lines"])
        self.assertIn(
            {"label": "Subtitle stream 4", "value": "SUBTITLE_BDPGS_OCR_FAILED: PgsToSrt exited 1"},
            details["proof_fields"],
        )
        self.assertIn({"label": "Subtitle repro", "value": "C:/Reports/subtitle-repro.ps1"}, details["proof_fields"])
        self.assertIn({"label": "Subtitle tool", "value": "bdpgs-ocr"}, details["proof_fields"])

    def test_failure_record_row_allowlists_common_tool_config_path_evidence(self) -> None:
        record = _record(
            stage="encoder-activation",
            error_code="ENCODER_TOOL_MISSING",
            payload_updates={
                "Tool": "ffmpeg",
                "config_path": "C:/Pipeline/config.psd1",
                "missing_path": "C:/Tools/ffmpeg/bin/ffmpeg.exe",
                "arbitrary_nested_marker_json": {"secret": "do not expose"},
            },
        )

        details = failure_record_to_row(record)["evidence_details"]

        self.assertTrue(details["structured"])
        self.assertIn({"label": "Tool", "value": "ffmpeg"}, details["proof_fields"])
        self.assertIn({"label": "Config path", "value": "C:/Pipeline/config.psd1"}, details["proof_fields"])
        self.assertIn({"label": "Missing path", "value": "C:/Tools/ffmpeg/bin/ffmpeg.exe"}, details["proof_fields"])
        proof_text = "\n".join(field["value"] for field in details["proof_fields"])
        self.assertNotIn("do not expose", proof_text)

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

    def test_failure_preview_fields_add_resolution_summary_and_groups(self) -> None:
        records = [
            _record(
                source_json="C:/State/Failures/Markers/one.json",
                source_path="C:/Source/Movies/Movie (2024)/Movie.mkv",
                classification="operator_required",
                stage="video-stream-policy",
                error_code="SOURCE_VIDEO_STREAMS_UNVETTED",
            ),
            _record(
                source_json="C:/State/Failures/Markers/two.json",
                source_path="C:/Source/Movies/Other (2024)/Other.mkv",
                classification="operator_required",
                stage="video-stream-policy",
                error_code="SOURCE_VIDEO_STREAMS_UNVETTED",
            ),
        ]
        lookup = failure_marker_lookup(records)

        fields = failure_preview_fields(
            records,
            source="markers",
            source_kind="markers",
            limit=100,
            empty_warning="No rows.",
            marker_lookup=lookup,
        )

        self.assertEqual(fields["resolution_summary"]["schema_version"], "desktop_failure_resolution.v1")
        self.assertEqual(fields["resolution_summary"]["status"], "blocked")
        self.assertEqual(fields["resolution_summary"]["blocking_count"], 2)
        self.assertEqual(fields["resolution_summary"]["clearable_count"], 2)
        self.assertEqual(len(fields["resolution_groups"]), 1)
        group = fields["resolution_groups"][0]
        self.assertEqual(group["schema_version"], "desktop_failure_resolution_group.v1")
        self.assertEqual(group["row_count"], 2)
        self.assertEqual(group["owner"], "Settings")
        self.assertEqual(group["primary_action"]["kind"], "open_owner_page")
        self.assertEqual(group["primary_action"]["label"], "Open Settings")
        self.assertEqual(group["clearable_count"], 2)
        self.assertEqual(len(group["affected_row_keys"]), 2)
        self.assertEqual(group["lifecycle_state"], "new")
        self.assertEqual(group["lifecycle_label"], "New")
        self.assertTrue(group["journal_key"])
        self.assertEqual(group["verification"]["active_marker_count"], 2)
        self.assertFalse(group["verification"]["safe_to_resolve"])
        self.assertTrue(group["playbook_steps"])
        self.assertTrue(group["available_transitions"])
        self.assertEqual(fields["resolution_summary"]["unacknowledged_count"], 1)

    def test_failure_preview_groups_mixed_retry_and_owner_actions(self) -> None:
        records = [
            _record(
                classification="transient",
                stage="copy",
                error_code="SOURCE_LOCKED",
                source_path="C:/Source/Movies/Retry.mkv",
                retryable="true",
            ),
            _record(
                classification="operator_required",
                stage="pending-publish",
                error_code="PUBLISH_BLOCKED",
                source_path="C:/Source/Movies/Publish.mkv",
            ),
        ]

        fields = failure_preview_fields(
            records,
            source="latest_failures.json",
            source_kind="latest_json",
            limit=100,
            empty_warning="No rows.",
        )

        groups = {group["owner"]: group for group in fields["resolution_groups"]}
        retry_group = next(group for group in fields["resolution_groups"] if group["retryable_count"] == 1)
        self.assertEqual(retry_group["primary_action"]["label"], "Wait for backend retry")
        self.assertEqual(groups["Pending Publish"]["primary_action"]["label"], "Open Pending Publish")
        self.assertEqual(fields["resolution_summary"]["retryable_count"], 1)
        self.assertEqual(fields["resolution_summary"]["blocking_count"], 1)

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
        self.assertEqual(fields["resolution_summary"]["status"], "warning")
        self.assertEqual(fields["resolution_groups"], [])
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
