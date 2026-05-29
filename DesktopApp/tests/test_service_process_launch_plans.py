from __future__ import annotations

import logging
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mediapipeline_desktop_app.models import ResolvedPaths
from app.processes.launch_plans import (
    build_audit_launch_plan,
    build_pipeline_launch_plan,
    build_rerun_csv_launch_plan,
)
from app.processes.lifecycle import ProcessLifecycleServiceMixin


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
        pipeline = root / "Pipeline" / "MediaPipeline_chatgpt.ps1"
        audit = root / "Pipeline" / "Audit-MediaLibrary_chatgpt.ps1"
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
            )

        self.assertEqual(plan.job_kind, "rerun_csv")
        self.assertEqual(plan.mode, "dry_run")
        self.assertIn("-DryRun", plan.args)
        self.assertEqual(plan.metadata["default_stage_mode"], "copy")
        self.assertEqual(plan.metadata["default_original_mode"], "keep")
        self.assertEqual(plan.metadata["default_return_mode"], "park")

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
