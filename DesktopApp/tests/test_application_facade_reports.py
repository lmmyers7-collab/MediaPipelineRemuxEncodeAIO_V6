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
        self.assertEqual(preview["retry_state"]["schema_version"], "desktop_retry_state.v1")
        self.assertEqual(preview["retry_state"]["blocked_count"], 1)
        self.assertEqual(marker_preview["schema_version"], "desktop_failure_preview.v1")
        self.assertEqual(marker_preview["source_kind"], "markers")
        self.assertEqual(marker_preview["count"], 1)
        self.assertEqual(marker_preview["rows"][0]["error_code"], "PUBLISH_UNAVAILABLE")
        self.assertEqual(marker_preview["rows"][0]["retry_limit"], 5)
        self.assertEqual(marker_preview["retry_state"]["status_state"], "retrying")
        self.assertTrue(marker_preview["retry_state"]["rows"][0]["retry_allowed"])

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
            preview = facade.clear_failure_markers(
                resolved,
                {"scope": "selected", "marker_paths": [str(root / "State" / "Failures" / "Markers" / "one.json")], "dry_run": True},
            ).to_mapping()
            cleared = facade.clear_failure_markers(
                resolved,
                {"scope": "selected", "marker_paths": [str(root / "State" / "Failures" / "Markers" / "one.json")], "confirm_clear": True},
            ).to_mapping()

        self.assertFalse(blocked["ok"])
        self.assertIn("confirm_clear", blocked["message"])
        self.assertEqual(len(calls), 2)
        self.assertTrue(preview["ok"])
        self.assertTrue(preview["data"]["dry_run"])
        self.assertFalse(preview["data"]["writes_failure_markers"])
        self.assertTrue(cleared["ok"])
        self.assertEqual(cleared["data"]["markers"], 1)
        self.assertTrue(cleared["data"]["writes_failure_markers"])

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
