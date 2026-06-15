from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root

sys.path.insert(0, str(find_repo_root(Path(__file__)) / "src"))

from mediapipeline.desktop.application import MediaPipelineApplicationFacade
from mediapipeline.desktop.models import ResolvedPaths
from tests.python.desktop.test_application_facade import DummyFacadeService, _resolved


class ApplicationFacadeMaintenanceTests(unittest.TestCase):
    def test_maintenance_workspace_structures_environment_health_rows(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            facade = MediaPipelineApplicationFacade(DummyFacadeService(root), app_version="v5-test")
            resolved = _resolved(root)

            maintenance = facade.get_maintenance_workspace(resolved).to_mapping()

        self.assertEqual(maintenance["schema_version"], "desktop_maintenance_workspace.v1")
        self.assertEqual(maintenance["ok_count"], 2)
        self.assertEqual(maintenance["missing_count"], 0)
        self.assertEqual(maintenance["warning_count"], 1)
        self.assertEqual(maintenance["rows"][0]["row_key"], "powershell_pwsh")
        self.assertTrue(maintenance["rows"][0]["required"])
        self.assertEqual(maintenance["rows"][0]["operator_status"], "ready")
        self.assertEqual(maintenance["rows"][0]["dry_run_impact"], "ready")
        self.assertEqual(maintenance["rows"][0]["tool_kind"], "powershell_host")
        self.assertIn("PowerShell host", maintenance["rows"][0]["capability"])
        self.assertIn("recommended_diagnostics_actions", maintenance["rows"][0])
        self.assertEqual(maintenance["rows"][2]["status"], "warning")
        self.assertTrue(maintenance["rows"][2]["optional"])
        self.assertFalse(maintenance["rows"][2]["required"])
        self.assertEqual(maintenance["rows"][2]["operator_status"], "review")
        self.assertEqual(maintenance["rows"][2]["dry_run_impact"], "review_before_release")
        self.assertTrue(any(action["target"] == "run_logs" for action in maintenance["rows"][2]["recommended_diagnostics_actions"]))
        self.assertEqual(maintenance["toolchain_evidence"]["schema_version"], "desktop_maintenance_toolchain_evidence.v1")
        self.assertEqual(maintenance["toolchain_evidence"]["operator_status"], "review")
        self.assertEqual(maintenance["toolchain_evidence"]["optional_review_count"], 1)
        self.assertIn("Toolchain readiness: review", "\n".join(maintenance["toolchain_evidence"]["summary_lines"]))
        self.assertEqual(maintenance["health_progress"]["schema_version"], "desktop_maintenance_health_progress.v1")
        self.assertEqual(maintenance["health_progress"]["mode"], "stepped")
        self.assertTrue(any(step["id"] == "powershell" for step in maintenance["health_progress"]["steps"]))
        self.assertTrue(any(step["id"] == "gpu_telemetry" and step["status"] == "warning" for step in maintenance["health_progress"]["steps"]))
        self.assertEqual(maintenance["progress_bars"][0]["id"], "maintenance_health")

    def test_release_dry_run_forces_dry_run_and_reports_plan_counts(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")

            result = facade.run_release_dry_run(
                {
                    "destination_root": str(root / "Deploy"),
                    "zip_package": True,
                    "verify": True,
                    "include_optional_tools": True,
                    "timeout_seconds": 99999,
                }
            )

        self.assertTrue(result.ok)
        self.assertEqual(result.command, "maintenance.release_dry_run")
        self.assertIn("12 file(s) would be copied", result.message)
        self.assertFalse(result.data["manifest_exists"])
        self.assertFalse(result.data["zip_exists"])
        self.assertEqual(result.data["release_progress"]["schema_version"], "desktop_release_package_progress.v1")
        self.assertEqual(result.data["progress_bars"][0]["id"], "release_package")
        self.assertEqual(service.release_build_calls[-1]["destination_root"], str(root / "Deploy"))
        self.assertTrue(service.release_build_calls[-1]["dry_run"])
        self.assertEqual(service.release_build_calls[-1]["timeout_seconds"], 1800)
        self.assertTrue(service.release_build_calls[-1]["include_optional_tools"])

    def test_release_build_requires_confirmation_and_creates_deployment_result(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)

            unconfirmed = facade.run_release_build(
                resolved,
                {
                    "destination_root": str(root.parent / "Deploy"),
                    "zip_package": True,
                    "verify": True,
                },
            )
            confirmed = facade.run_release_build(
                resolved,
                {
                    "destination_root": str(root.parent / "Deploy"),
                    "zip_package": True,
                    "verify": True,
                    "force": True,
                    "include_tauri_preview_binary": True,
                    "confirm_create": True,
                    "timeout_seconds": 99999,
                },
            )

        self.assertFalse(unconfirmed.ok)
        self.assertEqual(unconfirmed.command, "maintenance.release_build")
        self.assertIn("requires explicit confirmation", unconfirmed.message)
        self.assertTrue(confirmed.ok)
        self.assertEqual(confirmed.command, "maintenance.release_build")
        self.assertFalse(confirmed.data["dry_run"])
        self.assertTrue(confirmed.data["manifest_exists"])
        self.assertTrue(confirmed.data["zip_exists"])
        self.assertTrue(confirmed.data["writes_release_package"])
        self.assertEqual(confirmed.data["release_progress"]["schema_version"], "desktop_release_package_progress.v1")
        self.assertEqual(confirmed.data["progress_bars"][0]["id"], "release_package")
        self.assertFalse(service.release_build_calls[-1]["dry_run"])
        self.assertTrue(service.release_build_calls[-1]["force"])
        self.assertTrue(service.release_build_calls[-1]["include_tauri_preview_binary"])
        self.assertEqual(service.release_build_calls[-1]["timeout_seconds"], 14400)

    def test_dependency_atlas_command_updates_tooling_artifact_result(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")

            result = facade.run_dependency_atlas(
                {
                    "timeout_seconds": 99999,
                    "min_overview_edge_count": 5,
                    "min_overview_files": 3,
                }
            )

        self.assertTrue(result.ok)
        self.assertEqual(result.command, "maintenance.dependency_atlas")
        self.assertTrue(result.data["writes_dependency_atlas"])
        self.assertFalse(result.data["writes_media"])
        self.assertEqual(result.data["modules"], "377")
        self.assertEqual(result.data["dependency_atlas_progress"]["schema_version"], "desktop_dependency_atlas_progress.v1")
        self.assertEqual(result.data["progress_bars"][0]["id"], "dependency_atlas")
        self.assertEqual(service.dependency_atlas_calls[-1]["timeout_seconds"], 1800)
        self.assertEqual(service.dependency_atlas_calls[-1]["min_overview_edge_count"], 5)
        self.assertEqual(service.dependency_atlas_calls[-1]["min_overview_files"], 3)

    def test_dependency_atlas_open_folder_uses_backend_workspace_path(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            atlas_dir = root / "docs/generated/dependency-atlas"
            atlas_dir.mkdir(parents=True)
            service = DummyFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")

            result = facade.open_dependency_atlas_folder()

        self.assertTrue(result.ok)
        self.assertEqual(result.command, "maintenance.dependency_atlas_open_folder")
        self.assertEqual(result.data["target"], "dependency_atlas_folder")
        self.assertEqual(result.data["path"], str(atlas_dir))
        self.assertFalse(result.data["writes_media"])
        self.assertFalse(result.data["writes_dependency_atlas"])
        self.assertEqual(service.opened_paths, [atlas_dir])

    def test_maintenance_dry_run_commands_share_backend_command_lock(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)
            backfill_calls: list[dict[str, object]] = []

            def fake_backfill(resolved_arg: ResolvedPaths, **kwargs: object) -> tuple[bool, str]:
                backfill_calls.append({"resolved": resolved_arg, **kwargs})
                return True, "Backfill dry run complete.\n  Sidecars ingested : 1\n  Skipped (bad JSON): 0"

            service.backfill_completed_manifest = fake_backfill  # type: ignore[attr-defined]

            self.assertTrue(facade._maintenance_command_lock.acquire(blocking=False))  # type: ignore[attr-defined]
            try:
                release = facade.run_release_dry_run({"destination_root": str(root / "Deploy")}).to_mapping()
                backfill = facade.run_completed_backfill_dry_run(resolved, {}).to_mapping()
                atlas = facade.run_dependency_atlas({}).to_mapping()
            finally:
                facade._maintenance_command_lock.release()  # type: ignore[attr-defined]

        self.assertFalse(release["ok"])
        self.assertFalse(backfill["ok"])
        self.assertFalse(atlas["ok"])
        self.assertEqual(release["command"], "maintenance.release_dry_run")
        self.assertEqual(backfill["command"], "maintenance.completed_backfill_dry_run")
        self.assertEqual(atlas["command"], "maintenance.dependency_atlas")
        self.assertEqual(release["severity"], "warning")
        self.assertEqual(backfill["severity"], "warning")
        self.assertEqual(atlas["severity"], "warning")
        self.assertIn("another maintenance command is already in progress", release["message"])
        self.assertIn("another maintenance command is already in progress", backfill["message"])
        self.assertIn("another maintenance command is already in progress", atlas["message"])
        self.assertEqual(service.release_build_calls, [])
        self.assertEqual(service.dependency_atlas_calls, [])
        self.assertEqual(backfill_calls, [])
