from __future__ import annotations

import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root

sys.path.insert(0, str(find_repo_root(Path(__file__)) / "src"))

from mediapipeline.desktop.models import ResolvedPaths
from mediapipeline.core.audit.rerun_service import AuditRerunServiceMixin
from mediapipeline.core.failures.cleanup_service import FailureCleanupServiceMixin
from mediapipeline.core.failures.artifacts import failure_artifact_cleanup_plan, failure_artifact_summary
from mediapipeline.core.failures.markers import (
    failure_record_from_marker_payload,
    normalize_failure_marker_payload,
)
from mediapipeline.core.paths.layout import path_within_root


def _resolved(root: Path, markers: Path) -> ResolvedPaths:
    return ResolvedPaths(
        app_root=root,
        workspace_root=root,
        pipeline_path=root / "pipeline.ps1",
        config_path=root / "config.psd1",
        audit_script_path=root / "audit.ps1",
        rerun_script_path=root / "rerun.ps1",
        powershell_host=None,
        failed_markers_path=markers,
    )


class FailureMarkerHelperTests(unittest.TestCase):
    def test_normalize_failure_marker_payload_maps_pipeline_snake_case_contract(self) -> None:
        payload = normalize_failure_marker_payload(
            {
                "source_full_path": r"C:\Media\Movie.mkv",
                "error_code": "FFMPEG_FAILED",
                "retry_count": 2,
                "unknown_field": "preserved",
            }
        )

        self.assertEqual(payload["SourcePath"], r"C:\Media\Movie.mkv")
        self.assertEqual(payload["ErrorCode"], "FFMPEG_FAILED")
        self.assertEqual(payload["RetryCount"], 2)
        self.assertEqual(payload["unknown_field"], "preserved")

    def test_failure_record_from_marker_payload_skips_non_dict_records(self) -> None:
        self.assertIsNone(failure_record_from_marker_payload(Path("marker.json"), ["not", "a", "dict"]))

    def test_failure_record_from_marker_payload_builds_failure_record(self) -> None:
        record = failure_record_from_marker_payload(
            Path("marker.json"),
            {"source_full_path": r"C:\Media\Movie.mkv", "stage": "encode", "error_code": "FFMPEG_FAILED"},
        )

        self.assertIsNotNone(record)
        assert record is not None
        self.assertEqual(record.source_path_text, r"C:\Media\Movie.mkv")
        self.assertEqual(record.stage, "encode")
        self.assertEqual(record.error_code, "FFMPEG_FAILED")

    def test_audit_rerun_service_loads_normalized_failure_marker_records(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            markers = root / "State" / "Failures" / "Markers"
            markers.mkdir(parents=True)
            (markers / "001.json").write_text(
                json.dumps(
                    {
                        "source_full_path": str(root / "TV" / "Show" / "Episode.mkv"),
                        "stage": "remux",
                        "error_code": "REMUX_FAILED",
                    }
                ),
                encoding="utf-8",
            )
            (markers / "skip.json").write_text(json.dumps(["unexpected"]), encoding="utf-8")
            records = AuditRerunServiceMixin().load_failure_marker_records(_resolved(root, markers))

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].stage, "remux")
        self.assertEqual(records[0].error_code, "REMUX_FAILED")

    def test_clear_failure_markers_dry_run_does_not_move_marker(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            service = _FailureCleanupHarness(root)
            resolved = _failure_cleanup_resolved(root)
            marker = resolved.failed_markers_path / "marker-1.json"  # type: ignore[operator]
            marker.parent.mkdir(parents=True)
            marker.write_text(json.dumps({"source_full_path": str(root / "Movie.mkv")}), encoding="utf-8")

            result = service.clear_failure_markers(resolved, marker_paths=[str(marker)], dry_run=True)

            self.assertTrue(marker.exists())
            self.assertTrue(result["dry_run"])
            self.assertEqual(len(result["planned"]), 1)
            self.assertEqual(result["markers"], 0)
            self.assertEqual(result["manifest_path"], "")

    def test_clear_failure_markers_moves_selected_marker_and_writes_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            service = _FailureCleanupHarness(root)
            resolved = _failure_cleanup_resolved(root)
            marker = resolved.failed_markers_path / "marker-1.json"  # type: ignore[operator]
            report = resolved.failed_reports_path / "round_failures_1.json"  # type: ignore[operator]
            marker.parent.mkdir(parents=True)
            report.parent.mkdir(parents=True)
            marker.write_text(json.dumps({"source_full_path": str(root / "Movie.mkv")}), encoding="utf-8")
            report.write_text("[]", encoding="utf-8")

            result = service.clear_failure_markers(resolved, marker_paths=[str(marker)])

            self.assertFalse(marker.exists())
            self.assertTrue(report.exists(), "marker clear must not remove failure reports")
            self.assertEqual(result["markers"], 1)
            self.assertTrue(Path(result["manifest_path"]).exists())
            self.assertTrue(Path(result["archive_dir"]).exists())
            manifest = json.loads(Path(result["manifest_path"]).read_text(encoding="utf-8"))
            self.assertEqual(manifest["operation"], "clear_failure_markers")
            self.assertEqual(manifest["status"], "completed")
            self.assertEqual(len(manifest["moved"]), 1)
            self.assertTrue(Path(manifest["moved"][0]["archive_path"]).exists())

    def test_clear_failure_markers_rejects_paths_outside_marker_folder(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            service = _FailureCleanupHarness(root)
            resolved = _failure_cleanup_resolved(root)
            outside = root / "outside.json"
            outside.write_text("{}", encoding="utf-8")
            resolved.failed_markers_path.mkdir(parents=True)  # type: ignore[union-attr]

            result = service.clear_failure_markers(resolved, marker_paths=[str(outside)])

            self.assertTrue(outside.exists())
            self.assertEqual(result["markers"], 0)
            self.assertTrue(result["errors"])
            self.assertIn("outside failure marker folder", result["errors"][0])

    def test_archive_failure_evidence_dry_run_returns_fingerprint_without_writes(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            service = _FailureCleanupHarness(root)
            resolved = _failure_cleanup_resolved(root)
            marker = resolved.failed_markers_path / "marker-1.json"  # type: ignore[operator]
            report = resolved.failed_reports_path / "round_failures_1.txt"  # type: ignore[operator]
            marker.parent.mkdir(parents=True)
            report.parent.mkdir(parents=True)
            marker.write_text(json.dumps({"source_full_path": str(root / "Movie.mkv")}), encoding="utf-8")
            report.write_text("failure text", encoding="utf-8")

            result = service.archive_failure_evidence(
                resolved,
                scope="all_active",
                include_markers=True,
                include_reports=True,
                dry_run=True,
            )

            self.assertTrue(marker.exists())
            self.assertTrue(report.exists())
            self.assertTrue(result["dry_run"])
            self.assertEqual(len(result["planned"]), 2)
            self.assertTrue(result["dry_run_fingerprint"])
            self.assertFalse(Path(result["manifest_path"]).exists(), "dry run must not write a manifest")
            self.assertFalse(Path(result["archive_dir"]).exists(), "dry run must not create an archive folder")

    def test_archive_failure_evidence_fingerprint_mismatch_blocks_writes(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            service = _FailureCleanupHarness(root)
            resolved = _failure_cleanup_resolved(root)
            marker = resolved.failed_markers_path / "marker-1.json"  # type: ignore[operator]
            marker.parent.mkdir(parents=True)
            marker.write_text(json.dumps({"source_full_path": str(root / "Movie.mkv")}), encoding="utf-8")

            result = service.archive_failure_evidence(
                resolved,
                scope="all_active",
                include_markers=True,
                include_reports=False,
                dry_run=False,
                dry_run_fingerprint="wrong",
                reason="verified stale markers",
            )

            self.assertTrue(marker.exists())
            self.assertEqual(result["markers"], 0)
            self.assertTrue(result["errors"])
            self.assertIn("fingerprint mismatch", result["errors"][0])

    def test_archive_failure_evidence_current_plan_uses_default_reason(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            service = _FailureCleanupHarness(root)
            resolved = _failure_cleanup_resolved(root)
            marker = resolved.failed_markers_path / "marker-1.json"  # type: ignore[operator]
            media = root / "Movie.mkv"
            marker.parent.mkdir(parents=True)
            marker.write_text(json.dumps({"source_full_path": str(media)}), encoding="utf-8")
            media.write_text("media placeholder", encoding="utf-8")

            result = service.archive_failure_evidence(
                resolved,
                scope="all_active",
                include_markers=True,
                include_reports=False,
                dry_run=False,
            )

            self.assertFalse(marker.exists())
            self.assertTrue(media.exists(), "archive must not touch media")
            self.assertEqual(result["markers"], 1)
            self.assertEqual(result["confirmation_mode"], "current_plan")
            manifest = json.loads(Path(result["manifest_path"]).read_text(encoding="utf-8"))

        self.assertEqual(manifest["reason"], "Routine failure evidence archive.")
        self.assertEqual(manifest["confirmation_mode"], "current_plan")

    def test_archive_failure_evidence_moves_only_failure_markers_and_round_reports(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            service = _FailureCleanupHarness(root)
            resolved = _failure_cleanup_resolved(root)
            marker = resolved.failed_markers_path / "marker-1.json"  # type: ignore[operator]
            report_json = resolved.failed_reports_path / "round_failures_1.json"  # type: ignore[operator]
            report_txt = resolved.failed_reports_path / "round_failures_1.txt"  # type: ignore[operator]
            unrelated_report = resolved.failed_reports_path / "latest_failure_report.txt"  # type: ignore[operator]
            media = root / "Movie.mkv"
            marker.parent.mkdir(parents=True)
            report_json.parent.mkdir(parents=True)
            marker.write_text(json.dumps({"source_full_path": str(media)}), encoding="utf-8")
            report_json.write_text("[]", encoding="utf-8")
            report_txt.write_text("failure text", encoding="utf-8")
            unrelated_report.write_text("latest report stays", encoding="utf-8")
            media.write_text("media placeholder", encoding="utf-8")
            preview = service.archive_failure_evidence(
                resolved,
                scope="all_active",
                include_markers=True,
                include_reports=True,
                dry_run=True,
            )

            result = service.archive_failure_evidence(
                resolved,
                scope="all_active",
                include_markers=True,
                include_reports=True,
                dry_run=False,
                dry_run_fingerprint=preview["dry_run_fingerprint"],
                reason="operator verified stale failure evidence",
            )

            self.assertFalse(marker.exists())
            self.assertFalse(report_json.exists())
            self.assertFalse(report_txt.exists())
            self.assertTrue(unrelated_report.exists(), "archive must not move non-round failure reports")
            self.assertTrue(media.exists(), "archive must not touch media")
            self.assertEqual(result["markers"], 1)
            self.assertEqual(result["reports"], 2)
            manifest_path = Path(result["manifest_path"])
            self.assertTrue(manifest_path.exists())
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["operation"], "archive_failure_evidence")
            self.assertEqual(manifest["status"], "completed")
            self.assertEqual(manifest["reason"], "operator verified stale failure evidence")
            self.assertEqual(len(manifest["moved"]), 3)
            self.assertTrue(all(Path(item["archive_path"]).exists() for item in manifest["moved"]))

    def test_failure_artifact_summary_counts_current_and_legacy_roots(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            resolved = _failure_cleanup_resolved(root)
            resolved.config_data = {"FailureArtifactWarningThresholdGB": 0.000001}
            current = resolved.state_root / "Failures" / "Artifacts"  # type: ignore[operator]
            legacy = resolved.local_base / "Failed" / "Artifacts"  # type: ignore[operator]
            current.mkdir(parents=True)
            legacy.mkdir(parents=True)
            old_file = current / "old-small.mkv"
            large_file = current / "large-current.mkv"
            legacy_file = legacy / "legacy-medium.mkv"
            old_file.write_bytes(b"a" * 128)
            large_file.write_bytes(b"b" * 4096)
            legacy_file.write_bytes(b"c" * 1024)
            os.utime(old_file, (1_700_000_000, 1_700_000_000))
            os.utime(large_file, (1_700_000_200, 1_700_000_200))
            os.utime(legacy_file, (1_700_000_100, 1_700_000_100))

            payload = failure_artifact_summary(resolved)
            post_sizes = {
                old_file.name: old_file.stat().st_size,
                large_file.name: large_file.stat().st_size,
                legacy_file.name: legacy_file.stat().st_size,
            }

        self.assertEqual(payload["schema_version"], "failure_artifact_summary.v1")
        self.assertEqual(payload["evidence_authority"], "backend")
        self.assertEqual(payload["total_bytes"], 5248)
        self.assertEqual(payload["file_count"], 3)
        self.assertEqual(payload["status"], "warning")
        self.assertTrue(payload["warning"])
        self.assertIn("configured", payload["warning_message"])
        self.assertEqual(payload["threshold_gb"], 0.000001)
        self.assertEqual(payload["touches_media"], False)
        self.assertEqual(payload["cleanup_route_available"], True)
        self.assertEqual(payload["retention_days"], 0)
        self.assertEqual(payload["cleanup_target_gb"], 0)
        self.assertFalse(payload["cleanup_policy_enabled"])
        self.assertEqual([item["role"] for item in payload["root_paths"]], ["current", "legacy"])
        self.assertEqual([item["file_count"] for item in payload["root_paths"]], [2, 1])
        largest = payload["largest_files"]
        self.assertEqual([item["name"] for item in largest], ["large-current.mkv", "legacy-medium.mkv", "old-small.mkv"])
        self.assertEqual(largest[0]["size_bytes"], 4096)
        self.assertEqual(largest[0]["role"], "current")
        self.assertEqual(payload["oldest_modified_at"], "2023-11-14T22:13:20Z")
        self.assertEqual(payload["newest_modified_at"], "2023-11-14T22:16:40Z")
        self.assertEqual(payload["scan_errors"], [])
        self.assertEqual(
            post_sizes,
            {"old-small.mkv": 128, "large-current.mkv": 4096, "legacy-medium.mkv": 1024},
        )

    def test_failure_artifact_summary_handles_missing_empty_and_disabled_threshold(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            resolved = _failure_cleanup_resolved(root)
            resolved.config_data = {"FailureArtifactWarningThresholdGB": 0}
            current = resolved.state_root / "Failures" / "Artifacts"  # type: ignore[operator]
            current.mkdir(parents=True)

            payload = failure_artifact_summary(resolved)

        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["total_bytes"], 0)
        self.assertEqual(payload["file_count"], 0)
        self.assertEqual(payload["largest_files"], [])
        self.assertEqual(payload["oldest_modified_at"], "")
        self.assertEqual(payload["newest_modified_at"], "")
        self.assertEqual(payload["threshold_gb"], 0)
        self.assertFalse(payload["warning"])
        self.assertEqual(len(payload["root_paths"]), 2)
        self.assertTrue(payload["root_paths"][0]["exists"])
        self.assertFalse(payload["root_paths"][1]["exists"])

    def test_failure_artifact_summary_reports_scan_errors_without_failure(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            resolved = _failure_cleanup_resolved(root)
            current = resolved.state_root / "Failures" / "Artifacts"  # type: ignore[operator]
            current.parent.mkdir(parents=True)
            current.write_text("not a directory", encoding="utf-8")

            payload = failure_artifact_summary(resolved)

        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["total_bytes"], 0)
        self.assertEqual(payload["file_count"], 0)
        self.assertTrue(payload["scan_errors"])
        self.assertIn("exists but is not a directory", payload["scan_errors"][0])
        self.assertTrue(payload["root_paths"][0]["exists"])
        self.assertFalse(payload["root_paths"][0]["is_dir"])

    def test_failure_artifact_cleanup_plan_disabled_policy_does_not_select_files(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            resolved = _failure_cleanup_resolved(root)
            current = resolved.state_root / "Failures" / "Artifacts"  # type: ignore[operator]
            current.mkdir(parents=True)
            artifact = current / "old-artifact.mkv"
            artifact.write_bytes(b"x" * 128)
            os.utime(artifact, (1_700_000_000, 1_700_000_000))

            plan = failure_artifact_cleanup_plan(resolved, now=1_700_100_000)

        self.assertTrue(plan["dry_run"])
        self.assertEqual(plan["planned_count"], 0)
        self.assertEqual(plan["planned_bytes"], 0)
        self.assertFalse(plan["policy"]["enabled"])
        self.assertTrue(plan["dry_run_fingerprint"])
        self.assertEqual(plan["touches_media"], False)
        self.assertEqual(plan["source_media_mutation"], False)
        self.assertIn("cleanup policy disabled", plan["skipped"][0]["reason"])

    def test_failure_artifact_cleanup_plan_explicit_zero_target_selects_backlog(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            resolved = _failure_cleanup_resolved(root)
            current = resolved.state_root / "Failures" / "Artifacts"  # type: ignore[operator]
            current.mkdir(parents=True)
            first = current / "first-artifact.mkv"
            second = current / "second-artifact.mkv"
            first.write_bytes(b"x" * 128)
            second.write_bytes(b"y" * 256)
            os.utime(first, (1_700_000_000, 1_700_000_000))
            os.utime(second, (1_700_000_100, 1_700_000_100))

            plan = failure_artifact_cleanup_plan(resolved, target_gb=0, now=1_700_100_000)

        self.assertTrue(plan["dry_run"])
        self.assertEqual(plan["planned_count"], 2)
        self.assertEqual(plan["planned_bytes"], 384)
        self.assertEqual([item["name"] for item in plan["planned"]], ["first-artifact.mkv", "second-artifact.mkv"])
        self.assertEqual([item["reasons"] for item in plan["planned"]], [["cleanup_target_gb"], ["cleanup_target_gb"]])
        self.assertTrue(plan["policy"]["enabled"])
        self.assertTrue(plan["policy"]["target_enabled"])
        self.assertEqual(plan["policy"]["cleanup_target_gb"], 0)
        self.assertEqual(plan["touches_media"], False)
        self.assertEqual(plan["source_media_mutation"], False)

    def test_failure_artifact_cleanup_plan_selects_requested_artifact_paths_without_policy(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            resolved = _failure_cleanup_resolved(root)
            current = resolved.state_root / "Failures" / "Artifacts"  # type: ignore[operator]
            current.mkdir(parents=True)
            selected = current / "selected-artifact.mkv"
            unselected = current / "unselected-artifact.mkv"
            missing = current / "missing-artifact.mkv"
            selected.write_bytes(b"x" * 128)
            unselected.write_bytes(b"y" * 256)
            os.utime(selected, (1_700_000_000, 1_700_000_000))
            os.utime(unselected, (1_700_000_100, 1_700_000_100))

            plan = failure_artifact_cleanup_plan(
                resolved,
                artifact_paths=[str(selected), str(selected), str(missing)],
                now=1_700_100_000,
            )

        self.assertTrue(plan["policy"]["enabled"])
        self.assertTrue(plan["policy"]["selection_enabled"])
        self.assertEqual(plan["policy"]["selected_count"], 2)
        self.assertEqual(plan["requested_artifact_paths"], [str(selected), str(missing)])
        self.assertEqual(plan["planned_count"], 1)
        self.assertEqual(plan["planned"][0]["name"], "selected-artifact.mkv")
        self.assertEqual(plan["planned"][0]["reasons"], ["selected"])
        self.assertEqual(plan["planned_bytes"], 128)
        self.assertEqual(plan["skipped"][0]["reason"], "selected artifact unavailable")

    def test_failure_artifact_cleanup_plan_selects_files_older_than_retention(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            resolved = _failure_cleanup_resolved(root)
            resolved.config_data = {"FailureArtifactRetentionDays": 30}
            current = resolved.state_root / "Failures" / "Artifacts"  # type: ignore[operator]
            current.mkdir(parents=True)
            old_file = current / "old-artifact.mkv"
            recent_file = current / "recent-artifact.mkv"
            old_file.write_bytes(b"x" * 128)
            recent_file.write_bytes(b"y" * 256)
            now = 1_700_000_000
            os.utime(old_file, (now - 31 * 24 * 60 * 60, now - 31 * 24 * 60 * 60))
            os.utime(recent_file, (now - 2 * 24 * 60 * 60, now - 2 * 24 * 60 * 60))

            plan = failure_artifact_cleanup_plan(resolved, now=now)

        self.assertEqual(plan["planned_count"], 1)
        self.assertEqual(plan["planned"][0]["name"], "old-artifact.mkv")
        self.assertEqual(plan["planned"][0]["reasons"], ["retention_days"])
        self.assertEqual(plan["planned_bytes"], 128)
        self.assertTrue(plan["policy"]["retention_enabled"])
        self.assertFalse(plan["policy"]["target_enabled"])

    def test_failure_artifact_cleanup_plan_selects_oldest_files_until_target(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            resolved = _failure_cleanup_resolved(root)
            resolved.config_data = {"FailureArtifactCleanupTargetGB": 500 / (1024**3)}
            current = resolved.state_root / "Failures" / "Artifacts"  # type: ignore[operator]
            current.mkdir(parents=True)
            oldest = current / "oldest.mkv"
            middle = current / "middle.mkv"
            newest = current / "newest.mkv"
            oldest.write_bytes(b"a" * 400)
            middle.write_bytes(b"b" * 300)
            newest.write_bytes(b"c" * 200)
            os.utime(oldest, (1_700_000_000, 1_700_000_000))
            os.utime(middle, (1_700_000_100, 1_700_000_100))
            os.utime(newest, (1_700_000_200, 1_700_000_200))

            plan = failure_artifact_cleanup_plan(resolved, now=1_700_001_000)

        self.assertEqual(plan["total_bytes"], 900)
        self.assertEqual(plan["planned_count"], 1)
        self.assertEqual(plan["planned_bytes"], 400)
        self.assertEqual(plan["planned"][0]["name"], "oldest.mkv")
        self.assertEqual(plan["planned"][0]["reasons"], ["cleanup_target_gb"])

    def test_cleanup_failure_artifacts_fingerprint_mismatch_blocks_delete(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            service = _FailureCleanupHarness(root)
            resolved = _failure_cleanup_resolved(root)
            resolved.config_data = {"FailureArtifactRetentionDays": 1}
            current = resolved.state_root / "Failures" / "Artifacts"  # type: ignore[operator]
            current.mkdir(parents=True)
            artifact = current / "old-artifact.mkv"
            artifact.write_bytes(b"x" * 128)
            os.utime(artifact, (1_700_000_000, 1_700_000_000))

            result = service.cleanup_failure_artifacts(
                resolved,
                dry_run=False,
                dry_run_fingerprint="wrong",
                reason="stale artifact cleanup",
            )

            self.assertTrue(artifact.exists())

        self.assertEqual(result["deleted_count"], 0)
        self.assertTrue(result["errors"])
        self.assertIn("fingerprint mismatch", "\n".join(result["errors"]))

    def test_cleanup_failure_artifacts_policy_current_plan_uses_default_reason(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            service = _FailureCleanupHarness(root)
            resolved = _failure_cleanup_resolved(root)
            resolved.config_data = {"FailureArtifactRetentionDays": 1}
            current = resolved.state_root / "Failures" / "Artifacts"  # type: ignore[operator]
            current.mkdir(parents=True)
            old_artifact = current / "old-artifact.mkv"
            old_artifact.write_bytes(b"x" * 128)
            os.utime(old_artifact, (1_700_000_000, 1_700_000_000))

            result = service.cleanup_failure_artifacts(
                resolved,
                dry_run=False,
            )

            self.assertFalse(old_artifact.exists())
            self.assertEqual(result["deleted_count"], 1)
            self.assertEqual(result["confirmation_mode"], "current_plan")
            manifest = json.loads(Path(result["manifest_path"]).read_text(encoding="utf-8"))

        self.assertEqual(manifest["reason"], "Routine failure artifact cleanup.")
        self.assertEqual(manifest["confirmation_mode"], "current_plan")

    def test_cleanup_failure_artifacts_selected_paths_still_require_fingerprint(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            service = _FailureCleanupHarness(root)
            resolved = _failure_cleanup_resolved(root)
            current = resolved.state_root / "Failures" / "Artifacts"  # type: ignore[operator]
            current.mkdir(parents=True)
            artifact = current / "selected-artifact.mkv"
            artifact.write_bytes(b"x" * 128)

            result = service.cleanup_failure_artifacts(
                resolved,
                artifact_paths=[str(artifact)],
                dry_run=False,
            )

            self.assertTrue(artifact.exists())
            self.assertEqual(result["deleted_count"], 0)
            self.assertIn("selected artifact paths requires", "\n".join(result["errors"]))

    def test_cleanup_failure_artifacts_deletes_only_previewed_artifacts_and_writes_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            service = _FailureCleanupHarness(root)
            resolved = _failure_cleanup_resolved(root)
            resolved.config_data = {"FailureArtifactRetentionDays": 1}
            current = resolved.state_root / "Failures" / "Artifacts"  # type: ignore[operator]
            current.mkdir(parents=True)
            old_artifact = current / "old-artifact.mkv"
            recent_artifact = current / "recent-artifact.mkv"
            old_artifact.write_bytes(b"x" * 128)
            recent_artifact.write_bytes(b"y" * 256)
            old_time = 1_700_000_000
            recent_time = int(time.time())
            os.utime(old_artifact, (old_time, old_time))
            os.utime(recent_artifact, (recent_time, recent_time))
            marker = resolved.failed_markers_path / "marker-1.json"  # type: ignore[operator]
            report = resolved.failed_reports_path / "round_failures_1.json"  # type: ignore[operator]
            media = root / "Movie.mkv"
            marker.parent.mkdir(parents=True)
            report.parent.mkdir(parents=True)
            marker.write_text("{}", encoding="utf-8")
            report.write_text("[]", encoding="utf-8")
            media.write_bytes(b"media")

            preview = service.cleanup_failure_artifacts(resolved, dry_run=True)
            result = service.cleanup_failure_artifacts(
                resolved,
                dry_run=False,
                dry_run_fingerprint=preview["dry_run_fingerprint"],
                reason="operator verified stale failure artifact",
            )

            self.assertFalse(old_artifact.exists())
            self.assertTrue(recent_artifact.exists(), "cleanup must keep artifacts inside retention window")
            self.assertTrue(marker.exists(), "cleanup must not delete active failure markers")
            self.assertTrue(report.exists(), "cleanup must not delete failure reports")
            self.assertTrue(media.exists(), "cleanup must not delete source/output media paths")
            self.assertEqual(result["deleted_count"], 1)
            self.assertEqual(result["deleted_bytes"], 128)
            self.assertTrue(result["touches_failure_artifacts"])
            self.assertFalse(result["touches_media"])
            self.assertFalse(result["source_media_mutation"])
            manifest = json.loads(Path(result["manifest_path"]).read_text(encoding="utf-8"))

        self.assertEqual(manifest["operation"], "cleanup_failure_artifacts")
        self.assertEqual(manifest["status"], "completed")
        self.assertEqual(manifest["reason"], "operator verified stale failure artifact")
        self.assertEqual(len(manifest["deleted"]), 1)
        self.assertFalse(manifest["source_media_mutation"])

    def test_cleanup_failure_artifacts_deletes_selected_artifacts_only(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            service = _FailureCleanupHarness(root)
            resolved = _failure_cleanup_resolved(root)
            current = resolved.state_root / "Failures" / "Artifacts"  # type: ignore[operator]
            current.mkdir(parents=True)
            selected_artifact = current / "selected-artifact.mkv"
            kept_artifact = current / "kept-artifact.mkv"
            selected_artifact.write_bytes(b"x" * 128)
            kept_artifact.write_bytes(b"y" * 256)

            preview = service.cleanup_failure_artifacts(
                resolved,
                artifact_paths=[str(selected_artifact)],
                dry_run=True,
            )
            result = service.cleanup_failure_artifacts(
                resolved,
                artifact_paths=[str(selected_artifact)],
                dry_run=False,
                dry_run_fingerprint=preview["dry_run_fingerprint"],
                reason="operator selected this artifact",
            )

            self.assertFalse(selected_artifact.exists())
            self.assertTrue(kept_artifact.exists())
            self.assertEqual(result["deleted_count"], 1)
            self.assertEqual(result["deleted"][0]["name"], "selected-artifact.mkv")
            manifest = json.loads(Path(result["manifest_path"]).read_text(encoding="utf-8"))

        self.assertEqual(manifest["requested_artifact_paths"], [str(selected_artifact)])
        self.assertEqual(len(manifest["deleted"]), 1)


class _FailureCleanupHarness(FailureCleanupServiceMixin):
    def __init__(self, root: Path) -> None:
        self.app_root = root

    def _path_within_root(self, path: Path, root: Path) -> bool:
        return path_within_root(path, root)


def _failure_cleanup_resolved(root: Path) -> ResolvedPaths:
    local_base = root / "Scratch"
    return ResolvedPaths(
        app_root=root,
        workspace_root=root,
        pipeline_path=root / "pipeline.ps1",
        config_path=root / "config.psd1",
        audit_script_path=root / "audit.ps1",
        rerun_script_path=root / "rerun.ps1",
        powershell_host=None,
        local_base=local_base,
        state_root=local_base / "State",
        failed_markers_path=local_base / "State" / "Failures" / "Markers",
        failed_reports_path=local_base / "State" / "Failures" / "Reports",
    )


if __name__ == "__main__":
    unittest.main()
