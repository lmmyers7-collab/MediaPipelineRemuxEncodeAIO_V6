from __future__ import annotations

import sys
import unittest
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root

sys.path.insert(0, str(find_repo_root(Path(__file__)) / "src"))

from mediapipeline.core.maintenance.command_policy import (
    completed_backfill_dry_run_result,
    completed_backfill_exception_result,
    completed_backfill_unavailable_result,
    dependency_atlas_open_exception_result,
    dependency_atlas_open_missing_result,
    dependency_atlas_open_service_unavailable_result,
    dependency_atlas_open_success_result,
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

    def test_release_dry_run_builder_kwargs_force_dry_run_and_reject_string_bool_options(self) -> None:
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
        self.assertFalse(kwargs["include_optional_tools"])
        self.assertTrue(kwargs["force"])
        self.assertTrue(kwargs["dry_run"])
        self.assertEqual(kwargs["timeout_seconds"], 1800)

    def test_release_defaults_form_a_builder_compatible_verified_request(self) -> None:
        dry_run_kwargs = release_dry_run_builder_kwargs({}, timeout_seconds=900)
        build_kwargs = release_build_builder_kwargs({}, timeout_seconds=900)
        dry_run_result = release_dry_run_result(
            {
                "success": True,
                "returncode": "0",
                "stdout": "Copy files: 12\nExclude: 3",
                "manifest_exists": False,
                "zip_exists": False,
            },
            {},
        )

        for options in (dry_run_kwargs, build_kwargs, dry_run_result.data["options"]):
            self.assertTrue(options["verify"])
            self.assertTrue(options["include_tests"])
            self.assertFalse(options["include_tauri_preview_binary"])
        self.assertTrue(dry_run_kwargs["dry_run"])
        self.assertFalse(build_kwargs["dry_run"])

        explicit_options = release_build_builder_kwargs(
            {
                "verify": False,
                "include_tests": False,
                "include_tauri_preview_binary": True,
            },
            timeout_seconds=900,
        )
        self.assertFalse(explicit_options["verify"])
        self.assertFalse(explicit_options["include_tests"])
        self.assertTrue(explicit_options["include_tauri_preview_binary"])

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
        self.assertFalse(success.data["manifest_created"])
        self.assertFalse(success.data["zip_created"])
        self.assertFalse(failure.ok)
        self.assertEqual(failure.severity, "warning")
        self.assertEqual(failure.data["release_progress"]["status"], "blocked")
        self.assertEqual(failure.errors, ["timed out"])

    def test_release_dry_run_result_distinguishes_preexisting_artifacts_from_new_writes(self) -> None:
        preexisting = release_dry_run_result(
            {
                "success": True,
                "returncode": "0",
                "stdout": "Copy files: 12\nExclude: 3",
                "manifest_exists": True,
                "manifest_preexisting": True,
                "manifest_created": False,
                "zip_exists": True,
                "zip_preexisting": True,
                "zip_created": False,
                "manifest_path": "C:/Deploy/release_manifest.json",
                "zip_path": "C:/Deploy.zip",
            },
            {},
        )
        unexpected_write = release_dry_run_result(
            {
                "success": True,
                "returncode": "0",
                "stdout": "Copy files: 12\nExclude: 3",
                "manifest_exists": True,
                "manifest_preexisting": False,
                "manifest_created": True,
                "zip_exists": False,
                "zip_created": False,
                "manifest_path": "C:/Deploy/release_manifest.json",
            },
            {},
        )
        unexpected_change = release_dry_run_result(
            {
                "success": True,
                "returncode": "0",
                "stdout": "Copy files: 12\nExclude: 3",
                "manifest_exists": True,
                "manifest_preexisting": True,
                "manifest_created": False,
                "manifest_changed": True,
                "zip_exists": True,
                "zip_preexisting": True,
                "zip_created": False,
                "zip_changed": True,
                "manifest_path": "C:/Deploy/release_manifest.json",
                "zip_path": "C:/Deploy.zip",
            },
            {},
        )

        self.assertTrue(preexisting.ok)
        self.assertTrue(preexisting.data["manifest_exists"])
        self.assertTrue(preexisting.data["manifest_preexisting"])
        self.assertFalse(preexisting.data["manifest_created"])
        self.assertFalse(preexisting.data["manifest_changed"])
        self.assertTrue(preexisting.data["zip_preexisting"])
        self.assertFalse(preexisting.data["zip_created"])
        self.assertFalse(preexisting.data["zip_changed"])
        self.assertFalse(unexpected_write.ok)
        self.assertIn("unexpectedly created a manifest", unexpected_write.message)
        self.assertEqual(unexpected_write.data["release_progress"]["status"], "blocked")
        steps = {step["key"]: step for step in unexpected_write.data["release_progress"]["steps"]}
        self.assertEqual(steps["manifest"]["status"], "blocked")
        self.assertFalse(unexpected_change.ok)
        self.assertIn("changed a preexisting manifest", unexpected_change.message)
        self.assertIn("changed a preexisting zip", unexpected_change.errors[1])
        self.assertTrue(unexpected_change.data["manifest_changed"])
        self.assertTrue(unexpected_change.data["zip_changed"])
        changed_steps = {step["key"]: step for step in unexpected_change.data["release_progress"]["steps"]}
        self.assertEqual(changed_steps["manifest"]["status"], "blocked")
        self.assertEqual(changed_steps["validate"]["status"], "blocked")
        self.assertEqual(changed_steps["optional_smoke"]["status"], "blocked")

    def test_release_build_result_shapes_real_deployment_payloads(self) -> None:
        kwargs = release_build_builder_kwargs(
            {
                "destination_root": " C:/Deploy ",
                "zip_package": True,
                "verify": True,
                "force": True,
                "include_tauri_preview_binary": True,
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
            {"zip_package": True, "verify": True, "force": True, "include_tauri_preview_binary": True},
        )

        self.assertFalse(kwargs["dry_run"])
        self.assertTrue(kwargs["force"])
        self.assertTrue(kwargs["include_tauri_preview_binary"])
        self.assertTrue(result.ok)
        self.assertEqual(result.command, "maintenance.release_build")
        self.assertEqual(result.message, "Deployment build complete: 12 file(s) copied; manifest written; zip written.")
        self.assertFalse(result.data["dry_run"])
        self.assertTrue(result.data["manifest_exists"])
        self.assertTrue(result.data["zip_exists"])
        self.assertTrue(result.data["writes_release_package"])
        self.assertTrue(result.data["options"]["include_tauri_preview_binary"])
        self.assertEqual(result.data["release_progress"]["schema_version"], "desktop_release_package_progress.v1")
        self.assertEqual(result.data["release_progress"]["status"], "complete")
        self.assertEqual(result.data["progress_bars"][0]["source"], "maintenance.release_build")

    def test_release_build_result_blocks_missing_required_artifact_evidence(self) -> None:
        missing_artifacts = release_build_result(
            {
                "success": True,
                "returncode": "0",
                "stdout": "Copy files: 12\nExclude: 0",
                "manifest_exists": False,
                "zip_exists": False,
                "manifest_path": "C:/Deploy/release_manifest.json",
                "zip_path": "C:/Deploy.zip",
                "elapsed_seconds": 1.25,
            },
            {"zip_package": True, "verify": True},
        )
        zip_not_requested = release_build_result(
            {
                "success": True,
                "returncode": "0",
                "stdout": "Copy files: 12\nExclude: 0",
                "manifest_exists": True,
                "zip_exists": False,
                "manifest_path": "C:/Deploy/release_manifest.json",
                "zip_path": "C:/Deploy.zip",
                "elapsed_seconds": 1.25,
            },
            {"zip_package": False, "verify": True},
        )

        self.assertFalse(missing_artifacts.ok)
        self.assertEqual(missing_artifacts.severity, "error")
        self.assertIn("artifact verification failed", missing_artifacts.message)
        self.assertIn("Release manifest was not found", missing_artifacts.errors[0])
        self.assertIn("Release zip was requested but not found", missing_artifacts.errors[1])
        self.assertFalse(missing_artifacts.data["writes_release_package"])
        self.assertTrue(missing_artifacts.data["process_success"])
        self.assertEqual(missing_artifacts.data["release_progress"]["status"], "blocked")
        self.assertEqual(missing_artifacts.data["progress_bars"][0]["status"], "blocked")
        steps = {step["key"]: step for step in missing_artifacts.data["release_progress"]["steps"]}
        self.assertEqual(steps["manifest"]["status"], "blocked")
        self.assertEqual(steps["zip"]["status"], "blocked")
        self.assertEqual(steps["verify"]["status"], "blocked")
        self.assertTrue(zip_not_requested.ok)
        self.assertTrue(zip_not_requested.data["writes_release_package"])
        self.assertEqual(zip_not_requested.data["release_progress"]["steps"][4]["status"], "skipped")

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

    def test_dependency_atlas_open_results_keep_fixed_folder_contract(self) -> None:
        path = Path("C:/Repo/docs/generated/dependency-atlas")

        opened = dependency_atlas_open_success_result(path)
        missing = dependency_atlas_open_missing_result(path)
        unavailable = dependency_atlas_open_service_unavailable_result(path)
        failed = dependency_atlas_open_exception_result(path, RuntimeError("blocked"))

        self.assertTrue(opened.ok)
        self.assertEqual(opened.command, "maintenance.dependency_atlas_open_folder")
        self.assertEqual(opened.data["target"], "dependency_atlas_folder")
        self.assertEqual(opened.data["path"], str(path))
        self.assertFalse(opened.data["writes_media"])
        self.assertFalse(opened.data["writes_dependency_atlas"])
        self.assertEqual(missing.severity, "warning")
        self.assertIn("Run Update Atlas", missing.message)
        self.assertEqual(unavailable.errors, ["open_path is required."])
        self.assertIn("blocked", failed.message)


if __name__ == "__main__":
    unittest.main()
