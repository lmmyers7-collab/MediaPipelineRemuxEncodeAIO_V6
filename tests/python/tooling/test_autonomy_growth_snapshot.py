from __future__ import annotations

from contextlib import redirect_stdout
import io
import json
import tempfile
import unittest
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root
import sys

sys.path.insert(0, str(find_repo_root(Path(__file__)) / "src"))

from mediapipeline.tools import autonomy_growth_snapshot


def _paths_payload(root: Path) -> dict[str, object]:
    state = root / "State"
    return {
        "app_root": str(root),
        "workspace_root": str(root),
        "pipeline_path": str(root / "pipeline.ps1"),
        "config_path": str(root / "config.psd1"),
        "audit_script_path": str(root / "audit.ps1"),
        "rerun_script_path": str(root / "rerun.ps1"),
        "powershell_host": "pwsh",
        "local_base": str(root / "LocalBase"),
        "state_root": str(state),
        "active_jobs_path": str(state / "ActiveJobs"),
        "failed_reports_path": str(state / "Failures" / "Reports"),
        "failed_markers_path": str(state / "Failures" / "Markers"),
        "pending_push_path": str(state / "PendingServerPush"),
        "completed_manifest_path": str(state / "Completed" / "completed_jobs.jsonl"),
        "queue_snapshot_path": str(state / "Progress" / "queue_snapshot.json"),
        "progress_file": str(state / "Progress" / "pipeline_progress.json"),
        "event_file": str(state / "Progress" / "pipeline_events.jsonl"),
        "log_file": str(root / "LocalBase" / "pipeline_debug.log"),
        "config_data": {"NetworkRole": "standalone"},
    }


class AutonomyGrowthSnapshotToolTests(unittest.TestCase):
    def test_record_snapshot_from_payload_writes_bounded_diagnostics_state_only(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            payload = _paths_payload(root)
            for key in ("state_root", "pending_push_path", "completed_manifest_path", "queue_snapshot_path", "log_file"):
                path = Path(str(payload[key]))
                if path.suffix:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text("", encoding="utf-8")
                else:
                    path.mkdir(parents=True, exist_ok=True)

            first = autonomy_growth_snapshot.record_snapshot_from_payload(payload, max_snapshots=1)
            second = autonomy_growth_snapshot.record_snapshot_from_payload(payload, max_snapshots=1)

        self.assertEqual(second["schema_version"], "desktop_autonomy_growth_snapshot_cli.v1")
        self.assertTrue(first["ok"])
        self.assertTrue(second["ok"])
        self.assertEqual(second["write_result"]["retained_snapshot_count"], 1)
        self.assertEqual(second["history"]["snapshot_count"], 1)
        self.assertFalse(second["media_mutation_performed"])
        self.assertFalse(second["pending_publish_mutation_performed"])
        self.assertFalse(second["queue_mutation_performed"])
        self.assertIn("autonomy_growth_snapshots.jsonl", second["write_result"]["snapshot_path"])
        self.assertEqual(second["health"]["schema_version"], "desktop_autonomy_health.v1")

    def test_main_records_snapshot_and_prints_json(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            payload = _paths_payload(root)
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                exit_code = autonomy_growth_snapshot.main(
                    [
                        "--paths-json",
                        json.dumps(payload),
                        "--max-snapshots",
                        "2",
                    ]
                )
            output = json.loads(stdout.getvalue())

        self.assertEqual(exit_code, 0)
        self.assertTrue(output["ok"])
        self.assertEqual(output["schema_version"], "desktop_autonomy_growth_snapshot_cli.v1")
        self.assertEqual(output["write_result"]["max_snapshot_count"], 2)

    def test_main_without_payload_fails_without_writing(self) -> None:
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            exit_code = autonomy_growth_snapshot.main([])
        output = json.loads(stdout.getvalue())

        self.assertEqual(exit_code, 2)
        self.assertFalse(output["ok"])
        self.assertEqual(output["schema_version"], "desktop_autonomy_growth_snapshot_cli_error.v1")


if __name__ == "__main__":
    unittest.main()
