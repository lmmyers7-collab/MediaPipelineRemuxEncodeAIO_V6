from __future__ import annotations

from datetime import datetime, timezone
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mediapipeline_desktop_app.application.facade_status_policy import (
    application_capabilities,
    int_from_mapping,
    snapshot_counts,
    snapshot_latest_paths,
    snapshot_recent_events,
    snapshot_warnings,
    telemetry_fields,
    telemetry_gpu_present,
    telemetry_sampled_at,
)
from mediapipeline_desktop_app.models import ResolvedPaths, Snapshot, TelemetrySnapshot


def _resolved(root: Path) -> ResolvedPaths:
    return ResolvedPaths(
        app_root=root / "DesktopApp",
        workspace_root=root,
        pipeline_path=root / "Pipeline" / "MediaPipeline.ps1",
        config_path=root / "Pipeline" / "config.psd1",
        audit_script_path=root / "Pipeline" / "audit.ps1",
        rerun_script_path=root / "Pipeline" / "rerun.ps1",
        powershell_host=str(root / "pwsh.exe"),
    )


def _snapshot(root: Path) -> Snapshot:
    return Snapshot(
        resolved=_resolved(root),
        current_activity="Processing.",
        status_summary="Status OK",
        log_tail="",
        progress={},
        audit_progress=None,
        latest_failure_report=root / "State" / "Failures" / "latest.txt",
        latest_failure_json=None,
        latest_audit_csv=root / "State" / "Audit" / "audit.csv",
        latest_priority_csv=None,
        pipeline_events=[{"index": index} for index in range(30)],
        last_error="last error",
    )


class StatusPolicyTests(unittest.TestCase):
    def test_application_capabilities_are_stable_and_copied(self) -> None:
        capabilities = application_capabilities()
        capabilities.append("mutated")

        self.assertIn("snapshot", application_capabilities())
        self.assertIn("pipeline-start", application_capabilities())
        self.assertIn("diagnostics-open", application_capabilities())
        self.assertIn("pending-publish-open", application_capabilities())
        self.assertIn("rename-apply", application_capabilities())
        self.assertIn("settings-save-patch", application_capabilities())
        self.assertIn("settings-reload", application_capabilities())
        self.assertIn("backend-shutdown", application_capabilities())
        self.assertIn("command-result-envelope", application_capabilities())
        self.assertNotIn("mutated", application_capabilities())

    def test_snapshot_counts_preserve_int_float_fallback_behavior(self) -> None:
        progress = {
            "CurrentQueueIndex": "2.0",
            "CurrentQueueTotal": "bad",
            "TotalProcessed": 10,
            "Encoded": "",
            "Remuxed": None,
            "TotalFailed": "3",
            "Movies": "4.9",
            "TVEpisodes": "6",
        }

        self.assertEqual(int_from_mapping({"value": "7.8"}, "value"), 7)
        self.assertEqual(int_from_mapping({"value": "bad"}, "value"), 0)
        self.assertEqual(
            snapshot_counts(progress),
            {
                "queue_index": 2,
                "queue_total": 0,
                "processed": 10,
                "encoded": 0,
                "remuxed": 0,
                "failed": 3,
                "movies": 4,
                "tv_episodes": 6,
            },
        )

    def test_snapshot_paths_warnings_and_recent_events_are_stable(self) -> None:
        root = Path("C:/MediaPipeline")
        snapshot = _snapshot(root)

        latest = snapshot_latest_paths(snapshot)
        recent = snapshot_recent_events(snapshot)

        self.assertEqual(latest["latest_failure_report"], str(root / "State" / "Failures" / "latest.txt"))
        self.assertEqual(latest["latest_audit_csv"], str(root / "State" / "Audit" / "audit.csv"))
        self.assertNotIn("latest_failure_json", latest)
        self.assertEqual(snapshot_warnings(snapshot), ["last error"])
        self.assertEqual(len(recent), 25)
        self.assertEqual(recent[0]["index"], 5)
        self.assertEqual(recent[-1]["index"], 29)

    def test_telemetry_fields_preserve_gpu_presence_and_sample_times(self) -> None:
        naive = TelemetrySnapshot(collected_at=datetime(2026, 5, 8, 12, 0, 0))
        aware = TelemetrySnapshot(
            collected_at=datetime(2026, 5, 8, 12, 0, 0, tzinfo=timezone.utc),
            cpu_percent=12.0,
            memory_percent=44.0,
            gpu_encoder_percent=0.0,
            gpu_name="NVIDIA GPU",
            gpu_count=1,
            gpu_rows=[{"index": "0", "encoder_percent": 0.0}],
            source="nvidia-smi",
        )

        fields = telemetry_fields(aware)

        self.assertEqual(telemetry_sampled_at(naive), "2026-05-08T12:00:00")
        self.assertIn("2026-05-08T", telemetry_sampled_at(aware))
        self.assertFalse(telemetry_gpu_present(TelemetrySnapshot()))
        self.assertTrue(telemetry_gpu_present(TelemetrySnapshot(gpu_encoder_percent=0.0)))
        self.assertTrue(fields["gpu_present"])
        self.assertEqual(fields["gpu_encoder_percent"], 0.0)
        self.assertEqual(fields["gpu_rows"], [{"index": "0", "encoder_percent": 0.0}])
        self.assertEqual(fields["source"], "nvidia-smi")


if __name__ == "__main__":
    unittest.main()
