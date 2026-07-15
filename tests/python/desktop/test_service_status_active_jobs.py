from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root

sys.path.insert(0, str(find_repo_root(Path(__file__)) / "src"))

from mediapipeline.core.status.active_jobs import active_job_detail_rows, format_active_job_summary, worker_progress_payload


class StatusActiveJobsHelperTests(unittest.TestCase):
    def test_format_active_job_summary_reports_missing_folder(self) -> None:
        self.assertEqual(format_active_job_summary(None), ["No ActiveJobs records found."])

    def test_format_active_job_summary_reports_current_contract_record(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            folder = root / "ActiveJobs"
            folder.mkdir()
            (folder / "launch.json").write_text(
                json.dumps(
                    {
                        "schema_version": "desktop_active_job.v1",
                        "launch_id": "launch-1",
                        "job_kind": "pipeline",
                        "mode": "continuous",
                        "status": "active",
                        "pid": 123,
                        "app_pid": 456,
                        "command_line": "pwsh -File pipeline.ps1",
                        "args": ["pwsh", "-File", "pipeline.ps1"],
                        "cwd": str(root),
                        "stdout_log": str(root / "stdout.log"),
                        "stderr_log": str(root / "stderr.log"),
                        "show_console": False,
                        "metadata": {},
                        "launched_at": "2026-05-08T12:00:00-04:00",
                        "last_update": "2026-05-08T12:00:01-04:00",
                        "return_code": None,
                    }
                ),
                encoding="utf-8",
            )

            rows = format_active_job_summary(folder)

        self.assertEqual(rows, ["pipeline continuous: active (pid 123) launched 2026-05-08T12:00:00-04:00"])

    def test_active_job_detail_rows_reports_current_contract_record(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            folder = root / "ActiveJobs"
            folder.mkdir()
            (folder / "launch.json").write_text(
                json.dumps(
                    {
                        "schema_version": "desktop_active_job.v1",
                        "launch_id": "launch-1",
                        "job_kind": "pipeline",
                        "mode": "continuous",
                        "status": "active",
                        "pid": 123,
                        "app_pid": 456,
                        "command_line": "pwsh -File pipeline.ps1",
                        "args": ["pwsh", "-File", "pipeline.ps1"],
                        "cwd": str(root),
                        "stdout_log": str(root / "stdout.log"),
                        "stderr_log": str(root / "stderr.log"),
                        "show_console": False,
                        "metadata": {"route": "encode"},
                        "launched_at": "2026-05-08T12:00:00-04:00",
                        "last_update": "2026-05-08T12:00:01-04:00",
                        "return_code": None,
                    }
                ),
                encoding="utf-8",
            )

            rows = active_job_detail_rows(folder)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["source"], "contract")
        self.assertEqual(rows[0]["launch_id"], "launch-1")
        self.assertEqual(rows[0]["status_state"], "running")
        self.assertEqual(rows[0]["pid"], 123)
        self.assertEqual(rows[0]["args_count"], 3)
        self.assertEqual(rows[0]["metadata"], {"route": "encode"})

    def test_active_job_detail_rows_projects_kill_degraded_as_reconciliation_warning(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            folder = root / "ActiveJobs"
            folder.mkdir()
            (folder / "degraded.json").write_text(
                json.dumps(
                    {
                        "schema_version": "desktop_active_job.v1",
                        "launch_id": "launch-degraded",
                        "job_kind": "rerun_csv",
                        "mode": "rerun_csv",
                        "status": "kill_degraded",
                        "pid": 123,
                        "app_pid": 456,
                        "command_line": "pwsh -File rerun.ps1",
                        "args": ["pwsh", "-File", "rerun.ps1"],
                        "cwd": str(root),
                        "stdout_log": str(root / "stdout.log"),
                        "stderr_log": str(root / "stderr.log"),
                        "show_console": False,
                        "metadata": {},
                        "launched_at": "2026-05-08T12:00:00-04:00",
                        "last_update": "2026-05-08T12:00:01-04:00",
                        "return_code": -9,
                    }
                ),
                encoding="utf-8",
            )

            rows = active_job_detail_rows(folder)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["source"], "contract")
        self.assertEqual(rows[0]["status"], "kill_degraded")
        self.assertEqual(rows[0]["status_state"], "warning")

    def test_format_active_job_summary_reports_legacy_record(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            folder = Path(td) / "ActiveJobs"
            folder.mkdir()
            (folder / "legacy.json").write_text(
                json.dumps(
                    {
                        "job_kind": "audit",
                        "mode": "scan",
                        "status": "failed_immediate",
                        "pid": 42,
                        "launched_at": "2026-05-08T12:00:00",
                        "return_code": 1,
                    }
                ),
                encoding="utf-8",
            )

            rows = format_active_job_summary(folder)

        self.assertEqual(rows, ["audit scan: failed_immediate (pid 42) rc=1 launched 2026-05-08T12:00:00"])

    def test_format_active_job_summary_reports_invalid_current_contract(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            folder = Path(td) / "ActiveJobs"
            folder.mkdir()
            (folder / "bad.json").write_text(
                json.dumps(
                    {
                        "schema_version": "desktop_active_job.v1",
                        "launch_id": "launch-1",
                        "job_kind": "pipeline",
                        "status": "not-a-status",
                        "args": [],
                        "metadata": {},
                    }
                ),
                encoding="utf-8",
            )

            rows = format_active_job_summary(folder)

        self.assertEqual(len(rows), 1)
        self.assertIn("invalid active job contract", rows[0])

    def test_active_job_detail_rows_reports_invalid_current_contract(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            folder = Path(td) / "ActiveJobs"
            folder.mkdir()
            (folder / "bad.json").write_text(
                json.dumps(
                    {
                        "schema_version": "desktop_active_job.v1",
                        "launch_id": "launch-1",
                        "job_kind": "pipeline",
                        "status": "not-a-status",
                        "args": [],
                        "metadata": {},
                    }
                ),
                encoding="utf-8",
            )

            rows = active_job_detail_rows(folder)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["source"], "invalid")
        self.assertEqual(rows[0]["status"], "not-a-status")
        self.assertEqual(rows[0]["status_state"], "warning")
        self.assertIn("invalid active job contract", rows[0]["issue"])

    def test_worker_progress_payload_joins_active_job_progress_and_log_tail(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            folder = root / "ActiveJobs"
            folder.mkdir()
            (folder / "launch.json").write_text(
                json.dumps(
                    {
                        "schema_version": "desktop_active_job.v1",
                        "launch_id": "launch-1",
                        "job_kind": "pipeline",
                        "mode": "once",
                        "status": "active",
                        "pid": 123,
                        "app_pid": 456,
                        "command_line": "pwsh -File pipeline.ps1",
                        "args": ["pwsh", "-File", "pipeline.ps1"],
                        "cwd": str(root),
                        "stdout_log": str(root / "stdout.log"),
                        "stderr_log": str(root / "stderr.log"),
                        "show_console": False,
                        "metadata": {"route": "encode"},
                        "launched_at": "2026-05-08T12:00:00-04:00",
                        "last_update": "2026-05-08T12:01:00-04:00",
                        "return_code": None,
                    }
                ),
                encoding="utf-8",
            )

            payload = worker_progress_payload(
                folder,
                {
                    "ProgressVersion": 2,
                    "Status": "Processing",
                    "LastUpdate": "2026-05-08T12:02:00-04:00",
                    "CurrentStage": "encode",
                    "CurrentStagePercent": 42.5,
                    "CurrentFileDisplay": "Movie.mkv",
                    "CurrentItemStartedAt": "2026-05-08T12:00:30-04:00",
                },
                "first line\nffmpeg speed=1.2x\n",
                now=datetime.fromisoformat("2026-05-08T12:02:03-04:00"),
            )

        self.assertEqual(payload["schema_version"], "desktop_worker_progress.v1")
        self.assertEqual(payload["status"], "running")
        self.assertEqual(payload["active_count"], 1)
        self.assertEqual(payload["rows"][0]["worker_id"], "local")
        self.assertEqual(payload["rows"][0]["job_id"], "launch-1")
        self.assertEqual(payload["rows"][0]["source"], "Movie.mkv")
        self.assertEqual(payload["rows"][0]["stage"], "encode")
        self.assertEqual(payload["rows"][0]["percent"], 42.5)
        self.assertEqual(payload["rows"][0]["elapsed_seconds"], 90)
        self.assertEqual(payload["rows"][0]["last_log_line"], "ffmpeg speed=1.2x")
        self.assertEqual(payload["progress_bars"][0]["id"], "worker_local_launch_1")
        self.assertEqual(payload["progress_bars"][0]["mode"], "determinate")
        self.assertEqual(payload["progress_bars"][0]["percent"], 42.5)
        self.assertIn("Mutation guardrail", "\n".join(payload["summary_lines"]))

    def test_worker_progress_payload_uses_active_job_stdout_for_csv_rerun(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            folder = root / "ActiveJobs"
            folder.mkdir()
            stdout_log = root / "rerun.stdout.log"
            current_line = "2026-05-08 12:03:00 [INFO] STAGE COPY attempt 1/3: Delicatessen.mkv"
            stdout_log.write_text(
                "\n".join(
                    [
                        "2026-05-08 12:02:00 [INFO] Rerun CSV rows listed: 100; enabled/planned: 100",
                        current_line,
                    ]
                ),
                encoding="utf-8",
            )
            (folder / "rerun.json").write_text(
                json.dumps(
                    {
                        "schema_version": "desktop_active_job.v1",
                        "launch_id": "rerun-1",
                        "job_kind": "rerun_csv",
                        "mode": "process",
                        "status": "active",
                        "pid": 123,
                        "app_pid": 456,
                        "command_line": "pwsh -File Invoke-RerunCsv.ps1",
                        "args": ["pwsh", "-File", "Invoke-RerunCsv.ps1"],
                        "cwd": str(root),
                        "stdout_log": str(stdout_log),
                        "stderr_log": str(root / "rerun.stderr.log"),
                        "show_console": False,
                        "metadata": {"route": "rerun_csv"},
                        "launched_at": "2026-05-08T12:00:00-04:00",
                        "last_update": "2026-05-08T12:03:00-04:00",
                        "return_code": None,
                    }
                ),
                encoding="utf-8",
            )

            payload = worker_progress_payload(
                folder,
                {
                    "ProgressVersion": 2,
                    "Status": "Idle",
                    "LastUpdate": "2026-05-08T11:59:00-04:00",
                    "CurrentStage": "idle",
                    "CurrentStagePercent": 0,
                    "CurrentFileDisplay": "None",
                },
                "2026-05-08 11:59:00 [ERROR] stale generic pipeline tail\n",
                now=datetime.fromisoformat("2026-05-08T12:03:05-04:00"),
            )

        self.assertEqual(payload["status"], "running")
        self.assertEqual(payload["active_count"], 1)
        self.assertEqual(payload["rows"][0]["worker_label"], "Local rerun_csv")
        self.assertEqual(payload["rows"][0]["stage"], "active")
        self.assertEqual(payload["rows"][0]["last_log_line"], current_line)
        self.assertEqual(payload["progress_bars"][0]["mode"], "indeterminate")
        self.assertIn(f"last={current_line}", payload["progress_bars"][0]["detail"])

    def test_worker_progress_payload_joins_csv_rerun_child_progress_when_launch_matches(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            folder = root / "ActiveJobs"
            folder.mkdir()
            (folder / "rerun.json").write_text(
                json.dumps(
                    {
                        "schema_version": "desktop_active_job.v1",
                        "launch_id": "20260704_220624_184605_rerun_csv_22844_4ea5fba2",
                        "job_kind": "rerun_csv",
                        "mode": "process",
                        "status": "active",
                        "pid": 123,
                        "app_pid": 456,
                        "command_line": "pwsh -File Invoke-RerunCsv.ps1",
                        "args": ["pwsh", "-File", "Invoke-RerunCsv.ps1"],
                        "cwd": str(root),
                        "stdout_log": str(root / "rerun.stdout.log"),
                        "stderr_log": str(root / "rerun.stderr.log"),
                        "show_console": False,
                        "metadata": {"route": "rerun_csv"},
                        "launched_at": "2026-07-04T22:06:24-04:00",
                        "last_update": "2026-07-04T22:24:42-04:00",
                        "return_code": None,
                    }
                ),
                encoding="utf-8",
            )

            payload = worker_progress_payload(
                folder,
                {
                    "ProgressVersion": 2,
                    "Status": "Encoding Movie",
                    "LastUpdate": "2026-07-04T22:24:45-04:00",
                    "CurrentStage": "encode",
                    "CurrentStagePercent": 30,
                    "CurrentFileDisplay": "Cars (2006).mkv",
                    "CurrentItemStartedAt": "2026-07-04T22:24:00-04:00",
                    "ActiveJobKind": "rerun_csv",
                    "RerunParentLaunchId": "20260704_220624_184605_rerun_csv_22844_4ea5fba2",
                },
                "ENCODE : 30%\n",
                now=datetime.fromisoformat("2026-07-04T22:24:46-04:00"),
            )

        self.assertEqual(payload["status"], "running")
        self.assertEqual(payload["active_count"], 1)
        self.assertEqual(payload["rows"][0]["worker_label"], "Local rerun_csv")
        self.assertEqual(payload["rows"][0]["source"], "Cars (2006).mkv")
        self.assertEqual(payload["rows"][0]["stage"], "encode")
        self.assertEqual(payload["rows"][0]["percent"], 30.0)
        self.assertEqual(payload["progress_bars"][0]["mode"], "determinate")
        self.assertIn("file=Cars (2006).mkv", payload["progress_bars"][0]["detail"])

    def test_worker_progress_payload_treats_stop_requested_progress_as_warning(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            folder = root / "ActiveJobs"
            folder.mkdir()
            (folder / "launch.json").write_text(
                json.dumps(
                    {
                        "schema_version": "desktop_active_job.v1",
                        "launch_id": "launch-1",
                        "job_kind": "pipeline",
                        "mode": "once",
                        "status": "active",
                        "pid": 123,
                        "app_pid": 456,
                        "command_line": "pwsh -File pipeline.ps1",
                        "args": ["pwsh", "-File", "pipeline.ps1"],
                        "cwd": str(root),
                        "stdout_log": str(root / "stdout.log"),
                        "stderr_log": str(root / "stderr.log"),
                        "show_console": False,
                        "metadata": {},
                        "launched_at": "2026-05-08T12:00:00-04:00",
                        "last_update": "2026-05-08T12:01:00-04:00",
                        "return_code": None,
                    }
                ),
                encoding="utf-8",
            )

            payload = worker_progress_payload(
                folder,
                {
                    "ProgressVersion": 2,
                    "Status": "Stopped",
                    "LastUpdate": "2026-05-08T12:02:00-04:00",
                    "CurrentStage": "stopped",
                    "StopRequested": "true",
                    "CurrentFileDisplay": "Movie.mkv",
                    "CurrentItemStartedAt": "2026-05-08T12:00:30-04:00",
                },
                "pipeline stopped by operator\n",
                now=datetime.fromisoformat("2026-05-08T12:02:03-04:00"),
            )

        self.assertEqual(payload["status"], "warning")
        self.assertEqual(payload["blocked_count"], 0)
        self.assertEqual(payload["warning_count"], 1)
        self.assertEqual(payload["rows"][0]["status_state"], "warning")
        self.assertEqual(payload["progress_bars"][0]["status"], "warning")

    def test_worker_progress_payload_treats_bad_active_update_as_warning(self) -> None:
        payload = worker_progress_payload(
            None,
            {
                "ProgressVersion": 2,
                "Status": "Processing",
                "LastUpdate": "not a date",
                "CurrentStage": "encode",
                "CurrentStagePercent": 42.5,
                "CurrentFileDisplay": "Movie.mkv",
            },
            "ffmpeg running\n",
            now=datetime.fromisoformat("2026-05-08T12:02:03-04:00"),
        )

        self.assertEqual(payload["status"], "warning")
        self.assertEqual(payload["warning_count"], 1)
        self.assertTrue(payload["rows"][0]["stale"])
        self.assertEqual(payload["rows"][0]["status_state"], "warning")
        self.assertEqual(payload["progress_bars"][0]["status"], "warning")

    def test_worker_progress_payload_does_not_fake_rows_when_no_runtime_evidence_exists(self) -> None:
        payload = worker_progress_payload(None, None, "")

        self.assertEqual(payload["schema_version"], "desktop_worker_progress.v1")
        self.assertEqual(payload["status"], "idle")
        self.assertEqual(payload["rows"], [])
        self.assertEqual(payload["progress_bars"], [])

    def test_worker_progress_payload_does_not_treat_completed_progress_as_active_worker(self) -> None:
        payload = worker_progress_payload(
            None,
            {
                "ProgressVersion": 2,
                "Status": "Completed",
                "LastUpdate": "2026-05-08T12:02:00-04:00",
                "CurrentStage": "completed",
                "CurrentStagePercent": 100,
                "CurrentFileDisplay": "Movie.mkv",
            },
            "pipeline complete\n",
        )

        self.assertEqual(payload["status"], "idle")
        self.assertEqual(payload["rows"], [])
        self.assertEqual(payload["progress_bars"], [])

    def test_worker_progress_payload_excludes_completed_failed_active_jobs_when_idle(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            folder = root / "ActiveJobs"
            folder.mkdir()
            (folder / "failed.json").write_text(
                json.dumps(
                    {
                        "schema_version": "desktop_active_job.v1",
                        "launch_id": "launch-failed",
                        "job_kind": "pipeline",
                        "mode": "once",
                        "status": "failed",
                        "pid": 123,
                        "app_pid": 456,
                        "command_line": "pwsh -File pipeline.ps1",
                        "args": ["pwsh", "-File", "pipeline.ps1"],
                        "cwd": str(root),
                        "stdout_log": str(root / "stdout.log"),
                        "stderr_log": str(root / "stderr.log"),
                        "show_console": False,
                        "metadata": {},
                        "launched_at": "2026-05-08T12:00:00-04:00",
                        "last_update": "2026-05-08T12:01:00-04:00",
                        "completed_at": "2026-05-08T12:01:00-04:00",
                        "return_code": 1,
                    }
                ),
                encoding="utf-8",
            )

            payload = worker_progress_payload(
                folder,
                {
                    "ProgressVersion": 2,
                    "Status": "Idle",
                    "LastUpdate": "2026-05-08T12:02:00-04:00",
                    "CurrentStage": "idle",
                    "CurrentStagePercent": 0,
                    "CurrentFileDisplay": "None",
                },
                "pipeline idle\n",
                now=datetime.fromisoformat("2026-05-08T12:02:03-04:00"),
            )

        self.assertEqual(payload["status"], "idle")
        self.assertEqual(payload["rows"], [])
        self.assertEqual(payload["progress_bars"], [])


if __name__ == "__main__":
    unittest.main()
