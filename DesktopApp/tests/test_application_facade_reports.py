from __future__ import annotations

import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mediapipeline_desktop_app.application import MediaPipelineApplicationFacade
from DesktopApp.tests.test_application_facade import DummyFacadeService, _resolved


class ApplicationFacadeReportsTests(unittest.TestCase):
    def test_failure_preview_reads_latest_json_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            failure_json = root / "failures.json"
            failure_json.write_text(
                json.dumps(
                    [
                        {
                            "SourcePath": str(root / "TV" / "Show" / "Season 01" / "Show - S01E01.mkv"),
                            "JobId": "job-encode-1",
                            "Stage": "encode",
                            "Reason": "No NVENC capable devices found",
                            "Classification": "operator_required",
                            "ErrorCode": "ENCODE_NVENC_FAILED",
                            "RecordedAt": "2026-05-07T12:00:00-04:00",
                            "SuggestedAction": "Review GPU availability.",
                            "RetryCount": 3,
                            "RetryLimit": 3,
                            "Escalated": True,
                        },
                        {
                            "SourcePath": str(root / "Movies" / "Movie (1979)" / "Movie.mkv"),
                            "Stage": "scratch-copy",
                            "Reason": "File locked",
                            "Classification": "transient",
                            "ErrorCode": "SOURCE_LOCKED",
                        },
                    ]
                ),
                encoding="utf-8",
            )
            facade = MediaPipelineApplicationFacade(DummyFacadeService(root), app_version="v5-test")

            resolved = _resolved(root)
            markers_path = root / "State" / "Failed" / "Markers"
            markers_path.mkdir(parents=True)
            (markers_path / "marker-1.json").write_text(
                json.dumps(
                    {
                        "source_full_path": str(root / "TV" / "Show" / "Season 01" / "Show - S01E02.mkv"),
                        "job_id": "job-publish-1",
                        "stage": "publish",
                        "reason": "Network destination unavailable",
                        "classification": "transient",
                        "error_code": "PUBLISH_UNAVAILABLE",
                        "recorded_at": "2026-05-07T12:30:00-04:00",
                        "suggested_action": "Retry when the share is online.",
                        "retry_count": 1,
                        "retry_limit": 5,
                    }
                ),
                encoding="utf-8",
            )
            resolved.failed_markers_path = markers_path

            preview = facade.get_failure_preview(resolved).to_mapping()
            marker_preview = facade.get_failure_preview(resolved, source_kind="markers").to_mapping()

        self.assertEqual(preview["schema_version"], "desktop_failure_preview.v1")
        self.assertEqual(preview["source"], str(failure_json))
        self.assertEqual(preview["count"], 2)
        self.assertEqual(preview["operator_required_count"], 1)
        self.assertEqual(preview["transient_count"], 1)
        self.assertEqual(preview["rows"][0]["error_code"], "ENCODE_NVENC_FAILED")
        self.assertEqual(preview["rows"][0]["media_type"], "TV")
        self.assertTrue(preview["rows"][0]["escalated"])
        self.assertEqual(preview["rows"][0]["job_id"], "job-encode-1")
        self.assertEqual(preview["rows"][0]["triage"]["status_label"], "Needs operator")
        self.assertEqual(preview["rows"][0]["triage"]["severity"], "blocked")
        self.assertEqual(preview["rows"][0]["triage"]["suggested_fix"], "Review GPU availability.")
        self.assertFalse(preview["rows"][0]["clear_error"]["available"])
        self.assertIn("No active failure marker", preview["rows"][0]["clear_error"]["unavailable_reason"])
        self.assertEqual(preview["retry_state"]["schema_version"], "desktop_retry_state.v1")
        self.assertEqual(preview["retry_state"]["blocked_count"], 1)
        self.assertEqual(marker_preview["schema_version"], "desktop_failure_preview.v1")
        self.assertEqual(marker_preview["source_kind"], "markers")
        self.assertEqual(marker_preview["count"], 1)
        self.assertEqual(marker_preview["rows"][0]["error_code"], "PUBLISH_UNAVAILABLE")
        self.assertEqual(marker_preview["rows"][0]["retry_limit"], 5)
        self.assertEqual(marker_preview["rows"][0]["triage"]["status_label"], "Will retry")
        self.assertTrue(marker_preview["rows"][0]["clear_error"]["available"])
        self.assertEqual(marker_preview["rows"][0]["clear_error"]["marker_path"], str(markers_path / "marker-1.json"))
        self.assertEqual(marker_preview["retry_state"]["status_state"], "retrying")
        self.assertTrue(marker_preview["retry_state"]["rows"][0]["retry_allowed"])

    def test_latest_failure_preview_maps_single_active_marker_for_clear_error(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            source_path = root / "TV" / "Show" / "Season 01" / "Show - S01E01.mkv"
            failure_json = root / "failures.json"
            failure_json.write_text(
                json.dumps(
                    [
                        {
                            "SourcePath": str(source_path),
                            "Stage": "tv-parse",
                            "Reason": "Could not parse episode token.",
                            "Classification": "operator_required",
                            "ErrorCode": "TV_PARSE_FAILED",
                            "SuggestedAction": "Rename the source to include S01E01.",
                        }
                    ]
                ),
                encoding="utf-8",
            )
            markers_path = root / "State" / "Failures" / "Markers"
            markers_path.mkdir(parents=True)
            marker_file = markers_path / "marker-1.json"
            marker_file.write_text(
                json.dumps(
                    {
                        "source_full_path": str(source_path),
                        "stage": "tv-parse",
                        "reason": "Could not parse episode token.",
                        "classification": "operator_required",
                        "error_code": "TV_PARSE_FAILED",
                        "suggested_action": "Rename the source to include S01E01.",
                    }
                ),
                encoding="utf-8",
            )
            facade = MediaPipelineApplicationFacade(DummyFacadeService(root), app_version="v5-test")
            resolved = _resolved(root)
            resolved.failed_markers_path = markers_path

            preview = facade.get_failure_preview(resolved).to_mapping()

        self.assertEqual(preview["rows"][0]["triage"]["status_label"], "Needs operator")
        self.assertEqual(preview["rows"][0]["triage"]["plain_summary"], "Could not parse episode token.")
        self.assertEqual(preview["rows"][0]["clear_error"]["available"], True)
        self.assertEqual(preview["rows"][0]["clear_error"]["marker_path"], str(marker_file))
        self.assertEqual(preview["rows"][0]["clear_error"]["marker_paths"], [str(marker_file)])

    def test_latest_failure_preview_maps_retryable_warning_marker_for_clear_error(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            source_path = root / "Movies" / "Retry Movie.mkv"
            failure_json = root / "failures.json"
            failure_json.write_text(
                json.dumps(
                    [
                        {
                            "SourcePath": str(source_path),
                            "Stage": "subtitle-extract",
                            "Reason": "BDPGS subtitle OCR failed.",
                            "Classification": "transient",
                            "ErrorCode": "SUBTITLE_BDPGS_OCR_FAILED",
                            "SuggestedAction": "Configure PgsToSrt before retry.",
                            "RetryCount": 1,
                            "RetryLimit": 5,
                        }
                    ]
                ),
                encoding="utf-8",
            )
            markers_path = root / "State" / "Failures" / "Markers"
            markers_path.mkdir(parents=True)
            marker_file = markers_path / "marker-1.json"
            marker_file.write_text(
                json.dumps(
                    {
                        "source_full_path": str(source_path),
                        "stage": "subtitle-extract",
                        "reason": "BDPGS subtitle OCR failed.",
                        "classification": "transient",
                        "error_code": "SUBTITLE_BDPGS_OCR_FAILED",
                        "suggested_action": "Configure PgsToSrt before retry.",
                        "retry_count": 1,
                        "retry_limit": 5,
                    }
                ),
                encoding="utf-8",
            )
            facade = MediaPipelineApplicationFacade(DummyFacadeService(root), app_version="v5-test")
            resolved = _resolved(root)
            resolved.failed_markers_path = markers_path

            preview = facade.get_failure_preview(resolved).to_mapping()

        self.assertEqual(preview["rows"][0]["triage"]["status_label"], "Will retry")
        self.assertEqual(preview["rows"][0]["triage"]["severity"], "warning")
        self.assertTrue(preview["rows"][0]["retry_allowed"])
        self.assertTrue(preview["rows"][0]["clear_error"]["available"])
        self.assertEqual(preview["rows"][0]["clear_error"]["marker_path"], str(marker_file))
        self.assertEqual(preview["rows"][0]["clear_error"]["marker_paths"], [str(marker_file)])

    def test_latest_failure_preview_maps_multiple_matching_markers_for_clear_error(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            source_path = root / "Movies" / "Ambiguous.mkv"
            (root / "failures.json").write_text(
                json.dumps(
                    [
                        {
                            "SourcePath": str(source_path),
                            "Stage": "encode",
                            "Reason": "Encode failed.",
                            "Classification": "operator_required",
                            "ErrorCode": "ENCODE_FAILED",
                        }
                    ]
                ),
                encoding="utf-8",
            )
            markers_path = root / "State" / "Failures" / "Markers"
            markers_path.mkdir(parents=True)
            for index in range(2):
                (markers_path / f"marker-{index}.json").write_text(
                    json.dumps(
                        {
                            "source_full_path": str(source_path),
                            "stage": "encode",
                            "reason": "Encode failed.",
                            "classification": "operator_required",
                            "error_code": "ENCODE_FAILED",
                        }
                    ),
                    encoding="utf-8",
                )
            facade = MediaPipelineApplicationFacade(DummyFacadeService(root), app_version="v5-test")
            resolved = _resolved(root)
            resolved.failed_markers_path = markers_path

            preview = facade.get_failure_preview(resolved).to_mapping()

        expected_paths = [str(markers_path / "marker-0.json"), str(markers_path / "marker-1.json")]
        self.assertTrue(preview["rows"][0]["clear_error"]["available"])
        self.assertEqual(preview["rows"][0]["clear_error"]["marker_path"], expected_paths[0])
        self.assertEqual(preview["rows"][0]["clear_error"]["marker_paths"], expected_paths)
        self.assertEqual(preview["rows"][0]["clear_error"]["marker_count"], 2)

    def test_clear_failure_markers_requires_confirmation_and_passes_marker_paths(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyFacadeService(root)
            calls: list[dict[str, object]] = []

            def clear_failure_markers(resolved, *, marker_paths=None, dry_run=False):  # type: ignore[no-untyped-def]
                calls.append({"resolved": resolved, "marker_paths": marker_paths, "dry_run": dry_run})
                return {
                    "schema_version": "failure_marker_clear_result.v1",
                    "markers": 0 if dry_run else 1,
                    "planned": [{"path": str(root / "State" / "Failures" / "Markers" / "one.json")}],
                    "skipped": [],
                    "errors": [],
                    "dry_run": dry_run,
                    "manifest_path": "" if dry_run else str(root / "manifest.json"),
                    "archive_dir": "" if dry_run else str(root / "ClearedMarkers"),
                }

            service.clear_failure_markers = clear_failure_markers  # type: ignore[attr-defined]
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)

            blocked = facade.clear_failure_markers(
                resolved,
                {"scope": "selected", "marker_paths": [str(root / "State" / "Failures" / "Markers" / "one.json")]},
            ).to_mapping()
            blocked_string_confirm = facade.clear_failure_markers(
                resolved,
                {
                    "scope": "selected",
                    "marker_paths": [str(root / "State" / "Failures" / "Markers" / "one.json")],
                    "confirm_clear": "false",
                },
            ).to_mapping()
            preview = facade.clear_failure_markers(
                resolved,
                {"scope": "selected", "marker_paths": [str(root / "State" / "Failures" / "Markers" / "one.json")], "dry_run": True},
            ).to_mapping()
            preview_all = facade.clear_failure_markers(
                resolved,
                {"scope": "all_markers", "dry_run": True},
            ).to_mapping()
            cleared = facade.clear_failure_markers(
                resolved,
                {"scope": "selected", "marker_paths": [str(root / "State" / "Failures" / "Markers" / "one.json")], "confirm_clear": True},
            ).to_mapping()

        self.assertFalse(blocked["ok"])
        self.assertIn("confirm_clear", blocked["message"])
        self.assertFalse(blocked_string_confirm["ok"])
        self.assertIn("confirm_clear", blocked_string_confirm["message"])
        self.assertEqual(len(calls), 3)
        self.assertTrue(preview["ok"])
        self.assertTrue(preview["data"]["dry_run"])
        self.assertFalse(preview["data"]["writes_failure_markers"])
        self.assertTrue(preview_all["ok"])
        self.assertEqual(preview_all["data"]["scope"], "all_markers")
        self.assertIsNone(calls[1]["marker_paths"])
        self.assertTrue(cleared["ok"])
        self.assertEqual(cleared["data"]["markers"], 1)
        self.assertTrue(cleared["data"]["writes_failure_markers"])

    def test_clear_failure_markers_blocked_result_reports_no_marker_writes(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyFacadeService(root)

            def clear_failure_markers(resolved, *, marker_paths=None, dry_run=False):  # type: ignore[no-untyped-def]
                return {
                    "schema_version": "failure_marker_clear_result.v1",
                    "markers": 0,
                    "planned": [],
                    "skipped": [],
                    "errors": ["Failure marker does not exist."],
                    "dry_run": dry_run,
                    "manifest_path": "",
                    "archive_dir": "",
                }

            service.clear_failure_markers = clear_failure_markers  # type: ignore[attr-defined]
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")

            result = facade.clear_failure_markers(
                _resolved(root),
                {
                    "scope": "selected",
                    "marker_paths": [str(root / "State" / "Failures" / "Markers" / "missing.json")],
                    "confirm_clear": True,
                },
            ).to_mapping()

        self.assertFalse(result["ok"])
        self.assertFalse(result["data"]["writes_failure_markers"])
        self.assertFalse(result["data"]["touches_media"])

    def test_audit_preview_reads_latest_csv_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            audit_csv = root / "audit_summary_latest.csv"
            fieldnames = [
                "Path",
                "RelativePath",
                "LookupTitle",
                "MediaType",
                "EffectiveBucket",
                "PriorityFixLevel",
                "PriorityScore",
                "PrimaryIssueCode",
                "PrimarySuggestedAction",
                "IssueMessages",
            ]
            with audit_csv.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerow(
                    {
                        "Path": str(root / "TV" / "Show" / "Season 01" / "Show - S01E01.mkv"),
                        "RelativePath": "Show\\Season 01\\Show - S01E01.mkv",
                        "LookupTitle": "Show",
                        "MediaType": "TV",
                        "EffectiveBucket": "RERUN_PIPELINE",
                        "PriorityFixLevel": "HIGH",
                        "PriorityScore": "90",
                        "PrimaryIssueCode": "subtitle_srt_required",
                        "PrimarySuggestedAction": "Rerun pipeline after subtitle policy update.",
                        "IssueMessages": "Preferred-language SRT missing.",
                    }
                )
                writer.writerow(
                    {
                        "Path": str(root / "Movies" / "Movie (1979)" / "Movie.mkv"),
                        "RelativePath": "Movie (1979)\\Movie.mkv",
                        "LookupTitle": "Movie (1979)",
                        "MediaType": "Movie",
                        "EffectiveBucket": "REVIEW",
                        "PriorityFixLevel": "LOW",
                        "PriorityScore": "15",
                        "PrimaryIssueCode": "metadata_review",
                        "PrimarySuggestedAction": "Review manually.",
                        "IssueMessages": "Sidecar metadata mismatch.",
                    }
                )
            facade = MediaPipelineApplicationFacade(DummyFacadeService(root), app_version="v5-test")

            preview = facade.get_audit_preview(_resolved(root)).to_mapping()

        self.assertEqual(preview["schema_version"], "desktop_audit_preview.v1")
        self.assertEqual(preview["source"], str(audit_csv))
        self.assertEqual(preview["count"], 2)
        self.assertEqual(preview["high_priority_count"], 1)
        self.assertEqual(preview["rerun_count"], 1)
        self.assertEqual(preview["review_count"], 1)
        self.assertEqual(preview["rows"][0]["effective_bucket"], "RERUN_PIPELINE")
        self.assertEqual(preview["rows"][0]["priority_score"], 90)
        self.assertEqual(preview["rows"][0]["primary_issue_code"], "subtitle_srt_required")
