from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root

sys.path.insert(0, str(find_repo_root(Path(__file__)) / "src"))

from mediapipeline.desktop.models import ResolvedPaths
from mediapipeline.core.audit.rerun_service import AuditRerunServiceMixin
from mediapipeline.core.failures.cleanup_service import FailureCleanupServiceMixin
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
