from __future__ import annotations

import json
import logging
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mediapipeline_desktop_app.models import ResolvedPaths
from app.status.service import StatusServiceMixin


class DummyStatusService(StatusServiceMixin):
    def __init__(self) -> None:
        self.logger = logging.getLogger("test_status_service")


class StatusServiceContractTests(unittest.TestCase):
    def _resolved(self, root: Path) -> ResolvedPaths:
        return ResolvedPaths(
            app_root=root,
            workspace_root=root,
            pipeline_path=root / "pipeline.ps1",
            config_path=root / "config.psd1",
            audit_script_path=root / "audit.ps1",
            rerun_script_path=root / "rerun.ps1",
            powershell_host=None,
            progress_file=root / "pipeline_progress.json",
            event_file=root / "pipeline_events.jsonl",
        )

    def test_read_progress_returns_normalized_current_contract(self) -> None:
        service = DummyStatusService()
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            progress = {
                "ProgressVersion": "2",
                "LastUpdate": "2026-05-06 12:00:00",
                "CurrentQueueIndex": "1",
                "CurrentQueueTotal": "2",
                "CurrentStagePercent": "50",
                "PauseRequested": "false",
                "StopRequested": "true",
                "ControlRequests": {},
                "Status": "Processing",
                "TotalProcessed": "1",
                "Encoded": "0",
                "Remuxed": "1",
                "Failed": "0",
                "Movies": "1",
                "TVEpisodes": "0",
            }
            resolved = self._resolved(root)
            resolved.progress_file.write_text(json.dumps(progress), encoding="utf-8")

            result = service.read_progress(resolved)

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result["ProgressVersion"], 2)
        self.assertEqual(result["CurrentQueueIndex"], 1)
        self.assertEqual(result["CurrentStagePercent"], 50.0)
        self.assertTrue(result["StopRequested"])

    def test_read_progress_rejects_invalid_current_contract(self) -> None:
        service = DummyStatusService()
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved = self._resolved(root)
            resolved.progress_file.write_text(
                json.dumps({"ProgressVersion": 2, "LastUpdate": "2026-05-06 12:00:00", "Status": "Processing", "CurrentStagePercent": 999}),
                encoding="utf-8",
            )

            result = service.read_progress(resolved)

        self.assertIsNone(result)

    def test_read_pipeline_events_tail_skips_invalid_contract_records(self) -> None:
        service = DummyStatusService()
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved = self._resolved(root)
            valid = {
                "schema_version": "pipeline_event.v1",
                "event_id": "event-1",
                "event_type": "job_started",
                "timestamp": "2026-05-06T12:00:00Z",
                "created_at": "2026-05-06T12:00:00Z",
                "data": {"display_name": "Movie.mkv"},
            }
            invalid = {
                "schema_version": "pipeline_event.v1",
                "event_type": "job_started",
                "timestamp": "2026-05-06T12:00:00Z",
                "created_at": "2026-05-06T12:00:00Z",
                "data": {},
            }
            resolved.event_file.write_text(json.dumps(invalid) + "\n" + json.dumps(valid) + "\n", encoding="utf-8")

            events = service.read_pipeline_events_tail(resolved)

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["event_id"], "event-1")
        self.assertEqual(events[0]["data"]["display_name"], "Movie.mkv")

    def test_format_active_job_summary_uses_current_contract(self) -> None:
        service = DummyStatusService()
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            active_jobs = root / "ActiveJobs"
            active_jobs.mkdir()
            record = {
                "schema_version": "desktop_active_job.v1",
                "launch_id": "launch-1",
                "job_kind": "pipeline",
                "mode": "once",
                "status": "active",
                "pid": 1234,
                "app_pid": 999,
                "command_line": "pwsh -File pipeline.ps1",
                "args": ["pwsh", "-File", "pipeline.ps1"],
                "cwd": str(root),
                "stdout_log": str(root / "stdout.log"),
                "stderr_log": str(root / "stderr.log"),
                "show_console": False,
                "metadata": {},
                "launched_at": "2026-05-06T12:00:00-04:00",
                "last_update": "2026-05-06T12:00:01-04:00",
                "return_code": None,
            }
            (active_jobs / "launch-1.json").write_text(json.dumps(record), encoding="utf-8")
            resolved = self._resolved(root)
            resolved.active_jobs_path = active_jobs

            rows = service._format_active_job_summary(resolved)

        self.assertEqual(rows, ["pipeline once: active (pid 1234) launched 2026-05-06T12:00:00-04:00"])

    def test_format_active_job_summary_reports_invalid_current_contract(self) -> None:
        service = DummyStatusService()
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            active_jobs = root / "ActiveJobs"
            active_jobs.mkdir()
            (active_jobs / "bad.json").write_text(
                json.dumps(
                    {
                        "schema_version": "desktop_active_job.v1",
                        "launch_id": "launch-1",
                        "job_kind": "pipeline",
                        "status": "mystery",
                        "args": [],
                        "metadata": {},
                    }
                ),
                encoding="utf-8",
            )
            resolved = self._resolved(root)
            resolved.active_jobs_path = active_jobs

            rows = service._format_active_job_summary(resolved)

        self.assertEqual(len(rows), 1)
        self.assertIn("invalid active job contract", rows[0])


if __name__ == "__main__":
    unittest.main()
