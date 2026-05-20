from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mediapipeline_desktop_app.models import ResolvedPaths
from mediapipeline_desktop_app.service_completed_backfill import (
    build_completed_backfill_args,
    completed_backfill_launch_exception_message,
    completed_backfill_result_message,
    completed_backfill_script_path,
    validate_completed_backfill_request,
)
from mediapipeline_desktop_app.subprocess_runner import CapturedCommandResult


def _resolved(root: Path, *, powershell_host: str | None = "pwsh") -> ResolvedPaths:
    return ResolvedPaths(
        app_root=root / "DesktopApp",
        workspace_root=root,
        pipeline_path=root / "Pipeline" / "MediaPipeline.ps1",
        config_path=root / "Pipeline" / "config.psd1",
        audit_script_path=root / "Pipeline" / "audit.ps1",
        rerun_script_path=root / "Pipeline" / "rerun.ps1",
        powershell_host=powershell_host,
        local_base=root / "LocalBase",
    )


class CompletedBackfillHelperTests(unittest.TestCase):
    def test_completed_backfill_script_path_lives_next_to_pipeline_script(self) -> None:
        root = Path(r"C:\Bundle")
        resolved = _resolved(root)

        self.assertEqual(
            completed_backfill_script_path(resolved),
            root / "Pipeline" / "Backfill-CompletedManifest.ps1",
        )

    def test_validate_completed_backfill_request_reports_missing_prerequisites(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            script = root / "Pipeline" / "Backfill-CompletedManifest.ps1"
            script.parent.mkdir()
            script.write_text("param()", encoding="utf-8")
            outsource = root / "Outsource"

            ok, message = validate_completed_backfill_request(
                _resolved(root, powershell_host=None),
                outsource=outsource,
                script_path=script,
            )
            self.assertFalse(ok)
            self.assertIn("PowerShell 7", message)

            no_local = _resolved(root)
            no_local.local_base = None
            ok, message = validate_completed_backfill_request(no_local, outsource=outsource, script_path=script)
            self.assertFalse(ok)
            self.assertIn("LocalBase", message)

            ok, message = validate_completed_backfill_request(_resolved(root), outsource=None, script_path=script)
            self.assertFalse(ok)
            self.assertIn("Outsource path not set", message)

            missing_script = root / "missing.ps1"
            ok, message = validate_completed_backfill_request(_resolved(root), outsource=outsource, script_path=missing_script)
            self.assertFalse(ok)
            self.assertIn(str(missing_script), message)

            ok, message = validate_completed_backfill_request(_resolved(root), outsource=outsource, script_path=script)
            self.assertTrue(ok)
            self.assertEqual(message, "")

    def test_build_completed_backfill_args_includes_dry_run_and_checkpoint(self) -> None:
        root = Path(r"C:\Bundle")
        resolved = _resolved(root)
        script = root / "Pipeline" / "Backfill-CompletedManifest.ps1"
        checkpoint = root / "RunLogs" / "checkpoint.json"

        args = build_completed_backfill_args(
            resolved,
            outsource=root / "Outsource",
            script_path=script,
            dry_run=True,
            checkpoint_path=checkpoint,
        )

        self.assertEqual(args[:4], ["pwsh", "-NoProfile", "-NonInteractive", "-File"])
        self.assertIn(str(script), args)
        self.assertIn("-OutsourceRoot", args)
        self.assertIn(str(root / "Outsource"), args)
        self.assertIn("-LocalBase", args)
        self.assertIn(str(root / "LocalBase"), args)
        self.assertIn("-DryRun", args)
        self.assertIn("-CheckpointPath", args)
        self.assertIn(str(checkpoint), args)

    def test_completed_backfill_result_message_handles_success_timeout_and_failure(self) -> None:
        success = CapturedCommandResult(args=[], returncode=0, stdout="Backfill wrote 1 row.\n", stderr="")
        timeout = CapturedCommandResult(
            args=[],
            returncode=-9,
            stdout="",
            stderr="",
            timed_out=True,
            kill_message="killed process tree",
        )
        failure = CapturedCommandResult(args=[], returncode=3, stdout="", stderr="error detail")

        self.assertEqual(completed_backfill_result_message(success, 120.0), (True, "Backfill wrote 1 row."))
        self.assertEqual(
            completed_backfill_result_message(timeout, 120.0),
            (False, "Backfill timed out after 120s. killed process tree"),
        )
        self.assertEqual(completed_backfill_result_message(failure, 120.0), (False, "Backfill exit 3: error detail"))
        self.assertEqual(
            completed_backfill_launch_exception_message(RuntimeError("boom")),
            "Backfill failed to launch: RuntimeError: boom",
        )


if __name__ == "__main__":
    unittest.main()
