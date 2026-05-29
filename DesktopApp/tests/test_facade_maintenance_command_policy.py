from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.maintenance.command_policy import (
    completed_backfill_dry_run_result,
    completed_backfill_exception_result,
    completed_backfill_unavailable_result,
    maintenance_int_value,
    release_build_builder_kwargs,
    release_build_confirmation_required_result,
    release_build_message,
    release_build_result,
    release_builder_unavailable_result,
    release_dry_run_builder_kwargs,
    release_dry_run_exception_result,
    release_dry_run_invalid_result,
    release_dry_run_message,
    release_dry_run_result,
    release_stdout_value,
)


class MaintenanceCommandPolicyTests(unittest.TestCase):
    def test_release_stdout_value_matches_colon_labels_case_insensitively(self) -> None:
        stdout = "\n".join(["Copy files      : 12", "Exclude         : 4", "Other: value"])

        self.assertEqual(release_stdout_value(stdout, "copy files"), "12")
        self.assertEqual(release_stdout_value(stdout, "Exclude"), "4")
        self.assertEqual(release_stdout_value(stdout, "Missing"), "")

    def test_release_dry_run_builder_kwargs_force_dry_run_and_preserve_existing_bool_semantics(self) -> None:
        kwargs = release_dry_run_builder_kwargs(
            {
                "destination_root": " C:/Deploy ",
                "zip_package": False,
                "verify": True,
                "include_optional_tools": "false",
                "force": True,
            },
            timeout_seconds=1800,
        )

        self.assertEqual(kwargs["destination_root"], "C:/Deploy")
        self.assertFalse(kwargs["zip_package"])
        self.assertTrue(kwargs["verify"])
        self.assertTrue(kwargs["include_optional_tools"])
        self.assertTrue(kwargs["force"])
        self.assertTrue(kwargs["dry_run"])
        self.assertEqual(kwargs["timeout_seconds"], 1800)

    def test_release_dry_run_result_shapes_success_and_failure_payloads(self) -> None:
        success = release_dry_run_result(
            {
                "success": True,
                "returncode": "0",
                "stdout": "Copy files: 12\nExclude: 3",
                "manifest_exists": False,
                "zip_exists": False,
                "elapsed_seconds": 1.25,
            },
            {"include_optional_tools": True},
        )
        failure = release_dry_run_result(
            {
                "success": False,
                "timed_out": True,
                "returncode": "124",
                "stderr": "timed out",
            },
            {},
        )

        self.assertTrue(success.ok)
        self.assertEqual(success.severity, "info")
        self.assertEqual(success.message, "Release dry run complete: 12 file(s) would be copied; 3 excluded.")
        self.assertTrue(success.data["options"]["include_optional_tools"])
        self.assertEqual(success.data["release_progress"]["schema_version"], "desktop_release_package_progress.v1")
        self.assertEqual(success.data["progress_bars"][0]["id"], "release_package")
        self.assertEqual(success.data["progress_bars"][0]["percent"], 100.0)
        self.assertFalse(failure.ok)
        self.assertEqual(failure.severity, "warning")
        self.assertEqual(failure.data["release_progress"]["status"], "blocked")
        self.assertEqual(failure.errors, ["timed out"])

    def test_release_build_result_shapes_real_deployment_payloads(self) -> None:
        kwargs = release_build_builder_kwargs(
            {
                "destination_root": " C:/Deploy ",
                "zip_package": True,
                "verify": True,
                "force": True,
            },
            timeout_seconds=7200,
        )
        result = release_build_result(
            {
                "success": True,
                "returncode": "0",
                "stdout": "Copy files: 12\nExclude: 3",
                "manifest_exists": True,
                "zip_exists": True,
                "manifest_path": "C:/Deploy/release_manifest.json",
                "zip_path": "C:/Deploy.zip",
                "elapsed_seconds": 1.25,
            },
            {"zip_package": True, "verify": True, "force": True},
        )

        self.assertFalse(kwargs["dry_run"])
        self.assertTrue(kwargs["force"])
        self.assertTrue(result.ok)
        self.assertEqual(result.command, "maintenance.release_build")
        self.assertEqual(result.message, "Deployment build complete: 12 file(s) copied; manifest written; zip written.")
        self.assertFalse(result.data["dry_run"])
        self.assertTrue(result.data["manifest_exists"])
        self.assertTrue(result.data["zip_exists"])
        self.assertTrue(result.data["writes_release_package"])
        self.assertEqual(result.data["release_progress"]["schema_version"], "desktop_release_package_progress.v1")
        self.assertEqual(result.data["release_progress"]["status"], "complete")
        self.assertEqual(result.data["progress_bars"][0]["source"], "maintenance.release_build")

    def test_release_error_results_are_stable(self) -> None:
        self.assertEqual(release_builder_unavailable_result().message, "Release package builder is not available.")
        self.assertEqual(release_build_confirmation_required_result().warnings, ["confirm_create must be true."])
        self.assertEqual(release_dry_run_invalid_result().errors, ["build_release_package must return a dictionary."])
        self.assertIn("bad", release_dry_run_exception_result(RuntimeError("bad")).message)
        self.assertEqual(release_dry_run_message({"stdout": ""}), "Release dry run complete. No files were copied.")
        self.assertIn("manifest not found", release_build_message({"stdout": ""}))
        self.assertEqual(maintenance_int_value("5.5"), 5)
        self.assertEqual(maintenance_int_value("bad"), 0)

    def test_completed_backfill_result_shapes_dry_run_payloads(self) -> None:
        result = completed_backfill_dry_run_result(
            True,
            "\n".join(
                [
                    "Backfill dry run complete.",
                    "Sidecars ingested : 9",
                    "Skipped (bad JSON): 1",
                    "Manifest: C:/State/completed_jobs.jsonl",
                ]
            ),
            completed_manifest_path=Path("C:/Fallback/completed_jobs.jsonl"),
            checkpoint_path=Path("C:/RunLogs/checkpoint.json"),
            timeout_seconds=600,
        )
        failed = completed_backfill_dry_run_result(
            False,
            "",
            completed_manifest_path=None,
            checkpoint_path=None,
            timeout_seconds=30,
        )

        self.assertTrue(result.ok)
        self.assertIn("9 sidecar(s)", result.message)
        self.assertFalse(result.data["writes_manifest"])
        self.assertEqual(result.data["backfill_progress"]["schema_version"], "desktop_maintenance_backfill_progress.v1")
        self.assertEqual(result.data["backfill_progress"]["records_scanned"], 10)
        self.assertEqual(result.data["backfill_progress"]["records_written"], 0)
        self.assertEqual(result.data["progress_bars"][0]["id"], "maintenance_backfill")
        self.assertEqual(result.data["manifest_path"], "C:/State/completed_jobs.jsonl")
        self.assertFalse(failed.ok)
        self.assertEqual(failed.errors, ["Backfill dry run failed."])
        self.assertEqual(completed_backfill_unavailable_result().command, "maintenance.completed_backfill_dry_run")
        self.assertIn("offline", completed_backfill_exception_result(OSError("offline")).message)


if __name__ == "__main__":
    unittest.main()
