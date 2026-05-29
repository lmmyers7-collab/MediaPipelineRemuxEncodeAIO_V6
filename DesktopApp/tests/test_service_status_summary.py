from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mediapipeline_desktop_app.models import ResolvedPaths
from app.status.service import StatusServiceMixin
from app.status.summary import build_status_summary


def _resolved(root: Path, **overrides: object) -> ResolvedPaths:
    values = {
        "app_root": root,
        "workspace_root": root,
        "pipeline_path": root / "pipeline.ps1",
        "config_path": root / "config.psd1",
        "audit_script_path": root / "audit.ps1",
        "rerun_script_path": root / "rerun.ps1",
        "powershell_host": None,
        "local_base": root / "LocalBase",
        "source_movies": root / "Source" / "Movies",
        "source_tv": root / "Source" / "TV",
        "audit_reports_path": root / "AuditReports",
        "priority_markers": ["!", "#"],
    }
    values.update(overrides)
    return ResolvedPaths(**values)


class StatusSummaryService(StatusServiceMixin):
    def __init__(self) -> None:
        self.calls: list[str] = []

    def _format_active_job_summary(self, resolved: ResolvedPaths, *, max_items: int = 6) -> list[str]:
        self.calls.append("active")
        return ["pipeline continuous: active (pid 123)"]

    def _format_recent_error_summary(
        self,
        resolved: ResolvedPaths,
        pipeline_events: list[dict[str, object]],
        log_tail: str,
        latest_failure_json: Path | None,
        *,
        max_items: int = 8,
    ) -> list[str]:
        self.calls.append(f"errors:{log_tail}")
        return ["FFMPEG_FAILED | encode | Movie.mkv | failed"]

    def _format_pipeline_event_summary(self, events: list[dict[str, object]], *, max_items: int = 8) -> list[str]:
        self.calls.append("events")
        return ["tool_completed | failed | encode | ffmpeg | Movie.mkv"]

    def read_log_tail(self, resolved: ResolvedPaths, line_count: int = 150) -> str:
        self.calls.append(f"log:{line_count}")
        return "ERROR tail"

    def is_progress_stale(self, progress: dict[str, object] | None, *, stale_after_seconds: float = 5.0) -> bool:
        self.calls.append("progress_stale")
        return True

    def is_audit_progress_stale(self, audit_progress: dict[str, object] | None, *, stale_after_seconds: float = 5.0) -> bool:
        self.calls.append("audit_stale")
        return True


class StatusSummaryHelperTests(unittest.TestCase):
    def test_build_status_summary_reports_paths_flags_and_latest_reports(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            pause_flag = root / "pause.flag"
            pause_flag.write_text("pause", encoding="utf-8")
            stop_flag = root / "stop.flag"
            resolved = _resolved(root, pause_flag=pause_flag, stop_flag=stop_flag)
            failure_txt = root / "round_failures.txt"
            failure_json = root / "round_failures.json"
            audit_csv = root / "audit_summary.csv"
            priority_csv = root / "audit_summary.priority.csv"

            text = build_status_summary(
                resolved=resolved,
                progress=None,
                audit_progress=None,
                audit_root=str(root / "Audit"),
                latest_failure_report=failure_txt,
                latest_failure_json=failure_json,
                latest_audit_csv=audit_csv,
                latest_priority_csv=priority_csv,
            )

        self.assertIn("Pipeline path    :", text)
        self.assertIn("Priority markers : !, #", text)
        self.assertIn("Pause flag      : present", text)
        self.assertIn("Stop flag       : clear", text)
        self.assertIn("Latest failure report", text)
        self.assertIn(str(priority_csv), text)

    def test_build_status_summary_reports_progress_audit_errors_and_events(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            resolved = _resolved(root)

            text = build_status_summary(
                resolved=resolved,
                progress={
                    "ProgressVersion": 2,
                    "LastUpdate": "2026-05-08T12:00:00",
                    "Status": "Encoding",
                    "CurrentStage": "encode",
                    "CurrentStagePercent": 25,
                    "CurrentRoute": "encode",
                    "CurrentQueuePhase": "TV",
                    "CurrentQueueIndex": 1,
                    "CurrentQueueTotal": 3,
                    "CurrentFile": "Episode.mkv",
                    "CurrentFilePath": str(root / "Episode.mkv"),
                    "TotalProcessed": 4,
                    "Encoded": 1,
                    "Remuxed": 2,
                    "Failed": 1,
                    "Movies": 0,
                    "TVEpisodes": 4,
                },
                audit_progress={
                    "last_update": "2026-05-08T12:00:00",
                    "status": "scanning",
                    "processed_files": 2,
                    "total_files": 9,
                    "current_file": "Movie.mkv",
                    "current_operation": "probe",
                    "progress_persistence_healthy": False,
                },
                audit_root="",
                latest_failure_report=None,
                latest_failure_json=None,
                latest_audit_csv=None,
                latest_priority_csv=None,
                active_jobs=["pipeline continuous: active (pid 123)"],
                recent_errors=["FFMPEG_FAILED | encode | Episode.mkv | failed"],
                event_summary=["tool_completed | failed | encode | ffmpeg | Episode.mkv"],
                progress_is_stale=True,
                audit_progress_is_stale=True,
            )

        self.assertIn("Active jobs", text)
        self.assertIn("Progress health  : STALE - pipeline_progress.json is not updating.", text)
        self.assertIn("Audit health     : STALE - audit_progress.json is not updating.", text)
        self.assertIn("Progress health  : write failures", text)
        self.assertIn("Recent errors", text)
        self.assertIn("Recent pipeline events", text)

    def test_status_service_wrapper_preserves_summary_collaborators(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            service = StatusSummaryService()
            text = service._build_status_summary(
                resolved=_resolved(root),
                progress={"Status": "Encoding"},
                audit_progress={"status": "scanning"},
                pipeline_events=[{"event_type": "tool_completed"}],
                audit_root=str(root / "Audit"),
                latest_failure_report=None,
                latest_failure_json=root / "round_failures.json",
                latest_audit_csv=None,
                latest_priority_csv=None,
            )

        self.assertIn("pipeline continuous: active", text)
        self.assertIn("FFMPEG_FAILED", text)
        self.assertIn("tool_completed | failed", text)
        self.assertIn("Progress health  : STALE", text)
        self.assertIn("Audit health     : STALE", text)
        self.assertIn("log:80", service.calls)
        self.assertIn("errors:ERROR tail", service.calls)
        self.assertIn("active", service.calls)


if __name__ == "__main__":
    unittest.main()
