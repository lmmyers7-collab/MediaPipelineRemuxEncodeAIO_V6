from __future__ import annotations

import logging
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mediapipeline_desktop_app.models import ResolvedPaths
from mediapipeline_desktop_app.service_process_launch_runner import (
    start_audit_for_service,
    start_pipeline_for_service,
    start_rerun_csv_for_service,
)


class CapturingLaunchRunnerService:
    def __init__(self, root: Path) -> None:
        self.app_root = root / "DesktopApp"
        self.workspace_root = root
        self.logger = logging.getLogger("test_service_process_launch_runner")
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


class ProcessLaunchRunnerTests(unittest.TestCase):
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

    def test_pipeline_runner_builds_plan_and_uses_spawn_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            service = CapturingLaunchRunnerService(root)
            resolved = self._resolved(root)
            source = root / "Movie.mkv"

            result = start_pipeline_for_service(
                service,
                resolved,
                mode="validate",
                show_config=True,
                sleep_seconds=0,
                extra_args="",
                show_console=False,
                single_file=str(source),
            )

        self.assertIs(result, service.spawn_call)
        assert service.spawn_call is not None
        self.assertEqual(service.spawn_call["job_kind"], "pipeline")
        self.assertEqual(service.spawn_call["mode"], "validate")
        self.assertFalse(service.spawn_call["show_console"])
        self.assertIn("-ValidateOnly", service.spawn_call["args"])
        self.assertIn("-ShowConfig", service.spawn_call["args"])
        self.assertEqual(service.spawn_call["metadata"]["single_file"], str(source))
        self.assertEqual(service.spawn_call["metadata"]["sleep_seconds"], 1)

    def test_audit_runner_uses_default_report_root_and_spawn_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            service = CapturingLaunchRunnerService(root)
            resolved = self._resolved(root)

            result = start_audit_for_service(
                service,
                resolved,
                library_root=str(root / "Library"),
                include_sidecars=True,
                show_console=True,
            )

        self.assertIs(result, service.spawn_call)
        assert service.spawn_call is not None
        self.assertEqual(service.spawn_call["job_kind"], "audit")
        self.assertEqual(service.spawn_call["mode"], "audit")
        self.assertTrue(service.spawn_call["show_console"])
        self.assertIn("-IncludeSidecars", service.spawn_call["args"])
        self.assertEqual(service.spawn_call["metadata"]["report_root"], str(resolved.audit_reports_path))

    def test_rerun_runner_preserves_csv_policy_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            service = CapturingLaunchRunnerService(root)
            resolved = self._resolved(root)
            csv_path = root / "rerun.csv"
            csv_path.write_text("source_path\nmovie.mkv\n", encoding="utf-8")

            result = start_rerun_csv_for_service(
                service,
                resolved,
                csv_path,
                dry_run=False,
                stage_mode="copy",
                original_mode="keep",
                return_mode="park",
                show_console=False,
            )

        self.assertIs(result, service.spawn_call)
        assert service.spawn_call is not None
        self.assertEqual(service.spawn_call["job_kind"], "rerun_csv")
        self.assertEqual(service.spawn_call["mode"], "run")
        self.assertNotIn("-DryRun", service.spawn_call["args"])
        self.assertEqual(service.spawn_call["metadata"]["csv_path"], str(csv_path))
        self.assertEqual(service.spawn_call["metadata"]["default_stage_mode"], "copy")
        self.assertEqual(service.spawn_call["metadata"]["default_return_mode"], "park")


if __name__ == "__main__":
    unittest.main()
