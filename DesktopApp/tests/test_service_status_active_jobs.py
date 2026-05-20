from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mediapipeline_desktop_app.service_status_active_jobs import active_job_detail_rows, format_active_job_summary


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
        self.assertEqual(rows[0]["pid"], 123)
        self.assertEqual(rows[0]["args_count"], 3)
        self.assertEqual(rows[0]["metadata"], {"route": "encode"})

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
        self.assertIn("invalid active job contract", rows[0]["issue"])


if __name__ == "__main__":
    unittest.main()
