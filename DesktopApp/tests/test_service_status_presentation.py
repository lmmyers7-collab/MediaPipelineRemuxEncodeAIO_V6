from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mediapipeline_desktop_app.models import ResolvedPaths
from mediapipeline_desktop_app.service_status import StatusServiceMixin
from mediapipeline_desktop_app.service_status_presentation import build_current_activity


def _resolved(root: Path) -> ResolvedPaths:
    return ResolvedPaths(
        app_root=root,
        workspace_root=root,
        pipeline_path=root / "pipeline.ps1",
        config_path=root / "config.psd1",
        audit_script_path=root / "audit.ps1",
        rerun_script_path=root / "rerun.ps1",
        powershell_host=None,
    )


class StatusPresentationCurrentActivityTests(unittest.TestCase):
    def test_build_current_activity_uses_structured_event_fallback(self) -> None:
        events = [
            {
                "event_type": "tool_completed",
                "stage": "encode",
                "route": "encode",
                "status": "failed",
                "source_path": r"C:\Media\Movies\Example Movie.mkv",
                "data": {},
            }
        ]

        self.assertEqual(build_current_activity(None, events), "Example Movie.mkv | encode failed")

    def test_build_current_activity_keeps_progress_authoritative_over_events(self) -> None:
        events = [
            {
                "event_type": "tool_completed",
                "stage": "encode",
                "route": "encode",
                "status": "failed",
                "source_path": r"C:\Media\Movies\Event Movie.mkv",
                "data": {},
            }
        ]

        text = build_current_activity(
            {"CurrentStage": "encode", "CurrentStagePercent": 25, "CurrentFile": "Progress Movie.mkv"},
            events,
        )

        self.assertEqual(text, "Progress Movie | encode 25%")

    def test_build_current_activity_reports_idle_without_progress_or_events(self) -> None:
        self.assertEqual(build_current_activity(None, []), "No active work reported.")

    def test_status_service_wrapper_preserves_log_ignored_behavior(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            resolved = _resolved(Path(td))
            service = StatusServiceMixin()

            text = service._build_current_activity(resolved, None, "2026-04-30 [INFO] encode: 44%", [])

        self.assertEqual(text, "No active work reported.")


if __name__ == "__main__":
    unittest.main()
