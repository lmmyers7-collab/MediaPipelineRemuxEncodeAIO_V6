from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root

sys.path.insert(0, str(find_repo_root(Path(__file__)) / "src"))

from mediapipeline.desktop.models import ResolvedPaths
from mediapipeline.core.queue.dry_run import (
    build_queue_dry_run_command,
    format_queue_plan_source_status,
    queue_dry_run_temp_snapshot_path,
    queue_snapshot_file_is_fresh,
)


def _resolved(root: Path, *, powershell_host: str | None = "pwsh") -> ResolvedPaths:
    return ResolvedPaths(
        app_root=root / "DesktopApp",
        workspace_root=root,
        pipeline_path=root / "Pipeline" / "MediaPipeline.ps1",
        config_path=root / "Pipeline" / "config.psd1",
        audit_script_path=root / "Pipeline" / "audit.ps1",
        rerun_script_path=root / "Pipeline" / "rerun.ps1",
        powershell_host=powershell_host,
    )


class QueueDryRunHelperTests(unittest.TestCase):
    def test_queue_dry_run_temp_snapshot_path_embeds_request_id(self) -> None:
        path = Path(r"C:\State\queue_snapshot.json")

        self.assertEqual(
            queue_dry_run_temp_snapshot_path(path, "abc123"),
            Path(r"C:\State\queue_snapshot.abc123.dryrun.json"),
        )

    def test_build_queue_dry_run_command_uses_resolved_paths_and_pwsh_fallback(self) -> None:
        root = Path(r"C:\Bundle")
        temp_snapshot = root / "State" / "queue_snapshot.abc.dryrun.json"

        args = build_queue_dry_run_command(
            _resolved(root, powershell_host=None),
            temp_snapshot_path=temp_snapshot,
        )

        self.assertEqual(args[:4], ["pwsh", "-NoProfile", "-NonInteractive", "-File"])
        self.assertIn(str(root / "Pipeline" / "MediaPipeline.ps1"), args)
        self.assertIn("-EmitQueuePlan", args)
        self.assertIn("-QueuePlanOutPath", args)
        self.assertIn(str(temp_snapshot), args)
        self.assertIn("-ConfigPath", args)
        self.assertIn(str(root / "Pipeline" / "config.psd1"), args)

    def test_queue_snapshot_file_is_fresh_handles_fresh_stale_and_missing(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            snapshot = Path(td) / "queue_snapshot.json"
            snapshot.write_text("{}", encoding="utf-8")
            os.utime(snapshot, (100.0, 100.0))

            self.assertTrue(queue_snapshot_file_is_fresh(snapshot, fresh_seconds=60.0, now=lambda: 130.0))
            self.assertFalse(queue_snapshot_file_is_fresh(snapshot, fresh_seconds=60.0, now=lambda: 170.1))
            self.assertFalse(queue_snapshot_file_is_fresh(Path(td) / "missing.json", fresh_seconds=60.0, now=lambda: 130.0))

    def test_format_queue_plan_source_status_preserves_existing_text_shapes(self) -> None:
        self.assertEqual(
            format_queue_plan_source_status(
                produced_at="2026-05-08T10:00:00",
                request_id="abcdef123456",
                used_dry_run=True,
                fallback_status="",
                record_count=3,
                completed_excluded=2,
            ),
            "Queue plan source: live (dry run abcdef12). 3 runnable, 2 filtered (already-processed / blocked).",
        )
        self.assertEqual(
            format_queue_plan_source_status(
                produced_at="2026-05-08T10:00:00",
                request_id="",
                used_dry_run=False,
                fallback_status="Showing last cached snapshot.",
                record_count=1,
                completed_excluded=0,
            ),
            "Showing last cached snapshot. Queue plan source: snapshot @ 2026-05-08T10:00:00. 1 runnable, 0 filtered (already-processed / blocked).",
        )


if __name__ == "__main__":
    unittest.main()
