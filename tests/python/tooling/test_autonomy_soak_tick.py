from __future__ import annotations

from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
import io
import json
import tempfile
import unittest
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root
import sys

sys.path.insert(0, str(find_repo_root(Path(__file__)) / "src"))

from mediapipeline.tools import autonomy_soak_tick


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


def _prepare_clean_state(payload: dict[str, object]) -> None:
    for key in ("state_root", "pending_push_path", "completed_manifest_path", "queue_snapshot_path", "log_file"):
        path = Path(str(payload[key]))
        if path.suffix:
            path.parent.mkdir(parents=True, exist_ok=True)
            if key == "queue_snapshot_path":
                path.write_text(json.dumps({"runnable_count": 0}), encoding="utf-8")
            else:
                path.write_text("", encoding="utf-8")
        else:
            path.mkdir(parents=True, exist_ok=True)


class AutonomySoakTickToolTests(unittest.TestCase):
    def test_tick_without_snapshot_is_read_only_and_exit_zero_when_ready(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            payload = _paths_payload(root)
            _prepare_clean_state(payload)

            result = autonomy_soak_tick.run_tick_from_payload(payload, record_snapshot=False)
            tick_history_exists = Path(result["tick_history"]["history_path"]).exists()

        self.assertEqual(result["schema_version"], "desktop_autonomy_soak_tick.v1")
        self.assertTrue(result["ok"])
        self.assertEqual(result["exit_code"], 0)
        self.assertEqual(result["health"]["overall_status"], "ready")
        self.assertFalse(result["snapshot"]["requested"])
        self.assertFalse(result["snapshot"]["recorded"])
        self.assertFalse(result["tick_history"]["requested"])
        self.assertFalse(result["tick_history"]["recorded"])
        self.assertFalse(tick_history_exists)
        self.assertFalse(Path(result["history"]["snapshot_path"]).exists())
        self.assertFalse(result["media_mutation_performed"])
        self.assertFalse(result["pending_publish_mutation_performed"])
        self.assertFalse(result["queue_mutation_performed"])

    def test_tick_records_snapshot_only_when_requested(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            payload = _paths_payload(root)
            _prepare_clean_state(payload)

            result = autonomy_soak_tick.run_tick_from_payload(payload, record_snapshot=True, max_snapshots=1)
            snapshot_exists = Path(result["history"]["snapshot_path"]).exists()

        self.assertTrue(result["ok"])
        self.assertTrue(result["snapshot"]["requested"])
        self.assertTrue(result["snapshot"]["recorded"])
        self.assertEqual(result["snapshot"]["write_result"]["retained_snapshot_count"], 1)
        self.assertEqual(result["history"]["snapshot_count"], 1)
        self.assertTrue(snapshot_exists)

    def test_tick_records_bounded_tick_history_only_when_requested(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            payload = _paths_payload(root)
            _prepare_clean_state(payload)

            first = autonomy_soak_tick.run_tick_from_payload(
                payload,
                record_tick_history=True,
                max_tick_records=1,
            )
            second = autonomy_soak_tick.run_tick_from_payload(
                payload,
                record_tick_history=True,
                max_tick_records=1,
            )
            history_path = Path(second["tick_history"]["history_path"])
            history_exists = history_path.exists()
            records = [json.loads(line) for line in history_path.read_text(encoding="utf-8").splitlines()]

        self.assertTrue(first["tick_history"]["recorded"])
        self.assertTrue(second["tick_history"]["recorded"])
        self.assertTrue(history_exists)
        self.assertEqual(second["tick_history"]["record_count"], 1)
        self.assertEqual(second["tick_history"]["write_result"]["retained_record_count"], 1)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["schema_version"], "desktop_autonomy_soak_tick_record.v1")
        self.assertEqual(records[0]["overall_status"], "ready")
        self.assertEqual(records[0]["exit_code"], 0)
        self.assertEqual(records[0]["blocked_count"], 0)
        self.assertEqual(records[0]["review_count"], 0)
        self.assertFalse(second["tick_history"]["write_result"]["media_mutation_performed"])
        self.assertFalse(second["tick_history"]["write_result"]["pending_publish_mutation_performed"])
        self.assertFalse(second["tick_history"]["write_result"]["queue_mutation_performed"])
        self.assertFalse(second["tick_history"]["write_result"]["cleanup_performed"])

    def test_blocked_health_returns_blocked_exit_without_killing_work(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            payload = _paths_payload(root)
            _prepare_clean_state(payload)
            Path(str(payload["log_file"])).unlink()
            active_jobs = Path(str(payload["active_jobs_path"]))
            active_jobs.mkdir(parents=True, exist_ok=True)
            stale = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
            (active_jobs / "pipeline.json").write_text(
                json.dumps(
                    {
                        "schema_version": "active_job.v1",
                        "job_kind": "pipeline",
                        "status": "active",
                        "pid": 43210,
                        "launched_at": stale,
                        "last_update": stale,
                    }
                ),
                encoding="utf-8",
            )

            result = autonomy_soak_tick.run_tick_from_payload(payload, record_snapshot=False)

        self.assertFalse(result["ok"])
        self.assertEqual(result["exit_code"], autonomy_soak_tick.AUTONOMY_SOAK_BLOCKED_EXIT_CODE)
        self.assertEqual(result["health"]["overall_status"], "blocked")
        self.assertFalse(result["would_kill_active_work"])

    def test_main_records_snapshot_and_prints_json(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            payload = _paths_payload(root)
            _prepare_clean_state(payload)
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                exit_code = autonomy_soak_tick.main(
                    [
                        "--paths-json",
                        json.dumps(payload),
                        "--record-snapshot",
                        "--max-snapshots",
                        "2",
                        "--record-tick-history",
                        "--max-tick-records",
                        "2",
                    ]
                )
            output = json.loads(stdout.getvalue())

        self.assertEqual(exit_code, 0)
        self.assertEqual(output["schema_version"], "desktop_autonomy_soak_tick.v1")
        self.assertTrue(output["snapshot"]["recorded"])
        self.assertTrue(output["tick_history"]["recorded"])


if __name__ == "__main__":
    unittest.main()
