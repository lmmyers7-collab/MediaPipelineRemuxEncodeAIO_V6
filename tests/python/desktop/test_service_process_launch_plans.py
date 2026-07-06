from __future__ import annotations

import logging
import sys
import tempfile
import unittest
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root
from typing import Any

sys.path.insert(0, str(find_repo_root(Path(__file__)) / "src"))

from mediapipeline.desktop.models import ResolvedPaths
from mediapipeline.core.processes.launch_plans import (
    build_audit_launch_plan,
    build_pipeline_launch_plan,
    build_rerun_csv_launch_plan,
)
from mediapipeline.core.processes.lifecycle import ProcessLifecycleServiceMixin


class CapturingLaunchService(ProcessLifecycleServiceMixin):
    def __init__(self, root: Path) -> None:
        self.app_root = root / "DesktopApp"
        self.workspace_root = root
        self.logger = logging.getLogger("test_service_process_launch_plans")
        self.logger.addHandler(logging.NullHandler())
        self.spawn_call: dict[str, Any] | None = None

    def _spawn(
        self,
        args: list[str],
        show_console: bool,
        *,
        resolved: ResolvedPaths | None = None,
        job_kind: str = "process",
        mode: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self.spawn_call = {
            "args": args,
            "show_console": show_console,
            "resolved": resolved,
            "job_kind": job_kind,
            "mode": mode,
            "metadata": metadata or {},
        }
        return self.spawn_call


class ProcessLaunchPlanTests(unittest.TestCase):
    def _resolved(self, root: Path) -> ResolvedPaths:
        pipeline = root / "Pipeline" / "MediaPipeline.ps1"
        audit = root / "Pipeline" / "Audit-MediaLibrary.ps1"
        rerun = root / "Pipeline" / "Invoke-RerunCsv.ps1"
        config = root / "Pipeline" / "MediaPipeline_config_chatgpt.psd1"
        for path in (pipeline, audit, rerun, config):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("# test", encoding="utf-8")
        return ResolvedPaths(
            app_root=root / "DesktopApp",
            workspace_root=root,
            pipeline_path=pipeline,
            config_path=config,
            audit_script_path=audit,
            rerun_script_path=rerun,
            powershell_host="pwsh",
            audit_reports_path=root / "LocalBase" / "AuditReports",
        )

    def test_pipeline_plan_preserves_mode_flags_extra_args_and_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            resolved = self._resolved(root)

            plan = build_pipeline_launch_plan(
                resolved,
                mode="drain_pending_pushes",
                show_config=True,
                sleep_seconds=0,
                extra_args="-NoDeleteSource -Example value",
                single_file=str(root / "Movie.mkv"),
            )

        self.assertEqual(plan.job_kind, "pipeline")
        self.assertEqual(plan.mode, "drain_pending_pushes")
        self.assertIn("-DrainPendingPushes", plan.args)
        self.assertIn("-ShowConfig", plan.args)
        self.assertIn("-SingleFile", plan.args)
        self.assertIn("-NoDeleteSource", plan.args)
        self.assertEqual(plan.args[plan.args.index("-SleepSeconds") + 1], "1")
        self.assertEqual(plan.metadata["sleep_seconds"], 1)
        self.assertEqual(plan.metadata["extra_args"], "-NoDeleteSource -Example value")

    def test_pipeline_plan_reports_invalid_extra_args_before_launch(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            resolved = self._resolved(Path(td))

            with self.assertRaisesRegex(RuntimeError, "Extra arguments could not be parsed"):
                build_pipeline_launch_plan(
                    resolved,
                    mode="once",
                    show_config=False,
                    sleep_seconds=1,
                    extra_args='"unterminated',
                )

    def test_audit_plan_uses_report_root_config_and_sidecar_flag(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            resolved = self._resolved(root)

            plan = build_audit_launch_plan(
                resolved,
                library_root=str(root / "Library"),
                include_sidecars=True,
                default_report_root=root / "DefaultReports",
            )

        self.assertEqual(plan.job_kind, "audit")
        self.assertEqual(plan.mode, "audit")
        self.assertIn("-IncludeSidecars", plan.args)
        self.assertIn("-ConfigPath", plan.args)
        self.assertEqual(plan.metadata["report_root"], str(resolved.audit_reports_path))
        self.assertTrue(plan.metadata["include_sidecars"])

    def test_audit_plan_uses_library_roots_argument_for_multi_root_audit(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            resolved = self._resolved(root)
            first = str(root / "DriveA")
            second = str(root / "DriveB")

            plan = build_audit_launch_plan(
                resolved,
                library_root=first,
                library_roots=[first, second],
                include_sidecars=False,
                default_report_root=root / "DefaultReports",
            )

        self.assertIn("-LibraryRoots", plan.args)
        self.assertNotIn("-LibraryRoot", plan.args)
        roots_index = plan.args.index("-LibraryRoots")
        self.assertEqual(plan.args[roots_index + 1:roots_index + 3], [first, second])
        self.assertEqual(plan.metadata["library_roots"], [first, second])
        self.assertEqual(plan.metadata["library_root_count"], 2)

    def test_rerun_plan_sets_dry_run_mode_and_csv_policy_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            resolved = self._resolved(root)
            csv_path = root / "rerun.csv"
            csv_path.write_text("source_path\nmovie.mkv\n", encoding="utf-8")

            plan = build_rerun_csv_launch_plan(
                resolved,
                csv_path,
                dry_run=True,
                stage_mode="copy",
                original_mode="keep",
                return_mode="park",
                execution_mode="windowed",
                destination_mode="pending_publish",
                original_policy="hold_then_delete_after_publish",
                collision_policy="suffix",
                window_size=3,
                confirm_replace_final=True,
                confirm_source_overwrite=True,
                confirm_original_policy=True,
                confirm_delete_original=True,
            )

        self.assertEqual(plan.job_kind, "rerun_csv")
        self.assertEqual(plan.mode, "dry_run")
        self.assertIn("-DryRun", plan.args)
        self.assertIn("-ExecutionMode", plan.args)
        self.assertIn("windowed", plan.args)
        self.assertIn("-DestinationMode", plan.args)
        self.assertIn("pending_publish", plan.args)
        self.assertNotIn("-OriginalPolicy", plan.args)
        self.assertNotIn("-ConfirmOriginalPolicy", plan.args)
        self.assertNotIn("-ConfirmDeleteOriginal", plan.args)
        self.assertIn("-WindowSize", plan.args)
        self.assertIn("3", plan.args)
        self.assertIn("-ConfirmReplaceFinal", plan.args)
        self.assertIn("-ConfirmSourceOverwrite", plan.args)
        self.assertEqual(plan.metadata["default_stage_mode"], "copy")
        self.assertEqual(plan.metadata["default_original_mode"], "keep")
        self.assertEqual(plan.metadata["default_return_mode"], "park")
        self.assertEqual(plan.metadata["execution_mode"], "windowed")
        self.assertEqual(plan.metadata["destination_mode"], "pending_publish")
        self.assertEqual(plan.metadata["original_policy"], "keep")
        self.assertFalse(plan.metadata["confirm_original_policy"])
        self.assertFalse(plan.metadata["confirm_delete_original"])
        self.assertEqual(plan.metadata["window_size"], 3)
        self.assertTrue(plan.metadata["confirm_replace_final"])
        self.assertTrue(plan.metadata["confirm_source_overwrite"])

    def test_rerun_plan_sets_plan_only_mode_without_dry_run_flag(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            resolved = self._resolved(root)
            csv_path = root / "rerun.csv"
            csv_path.write_text("source_path\nmovie.mkv\n", encoding="utf-8")

            plan = build_rerun_csv_launch_plan(
                resolved,
                csv_path,
                dry_run=False,
                plan_only=True,
                stage_mode="copy",
                original_mode="keep",
                return_mode="park",
            )

        self.assertEqual(plan.job_kind, "rerun_csv")
        self.assertEqual(plan.mode, "plan_only")
        self.assertIn("-PlanOnly", plan.args)
        self.assertNotIn("-DryRun", plan.args)
        self.assertTrue(plan.metadata["plan_only"])
        self.assertFalse(plan.metadata["dry_run"])

    def test_process_service_start_pipeline_uses_launch_plan_and_existing_spawn_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            service = CapturingLaunchService(root)
            resolved = self._resolved(root)

            result = service.start_pipeline(
                resolved,
                mode="validate",
                show_config=False,
                sleep_seconds=5,
                extra_args="",
                show_console=False,
            )

        self.assertIs(result, service.spawn_call)
        assert service.spawn_call is not None
        self.assertEqual(service.spawn_call["job_kind"], "pipeline")
        self.assertEqual(service.spawn_call["mode"], "validate")
        self.assertIn("-ValidateOnly", service.spawn_call["args"])


if __name__ == "__main__":
    unittest.main()
