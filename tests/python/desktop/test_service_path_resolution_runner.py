from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from typing import Any

from mediapipeline.core.storage.constants import APP_STATE_NAME
from mediapipeline.core.paths.layout import first_existing, path_or_none, state_root_for_local_base
from mediapipeline.core.paths.resolution_runner import resolve_paths_for_service


class DummyPathResolutionService:
    def __init__(self, app_root: Path, config_data: dict[str, Any]) -> None:
        self.app_root = app_root
        self.workspace_root = app_root.parent
        self.config_data = config_data
        self.loaded_config_request: tuple[Path, str | None] | None = None
        self.migrated_app_state_paths: list[Path] = []

    def default_audit_script_path(self) -> Path:
        return self.workspace_root / "ops" / "pipeline" / "entrypoints" / "Audit-MediaLibrary.ps1"

    def default_rerun_script_path(self) -> Path:
        return self.workspace_root / "ops" / "pipeline" / "entrypoints" / "Invoke-RerunCsv.ps1"

    def resolve_powershell_host(self) -> str | None:
        return "pwsh-test"

    def load_config_data(self, config_path: Path, powershell_host: str | None) -> dict[str, Any]:
        self.loaded_config_request = (config_path, powershell_host)
        return dict(self.config_data)

    def _state_root_for_local_base(self, local_base: Path) -> Path:
        return state_root_for_local_base(local_base)

    def _migrate_app_state_path(self, preferred_path: Path) -> None:
        self.migrated_app_state_paths.append(preferred_path)

    def _path_or_none(self, value: Any) -> Path | None:
        return path_or_none(value)

    def _first_existing(self, *paths: Path) -> Path:
        return first_existing(*paths)


class ServicePathResolutionRunnerTests(unittest.TestCase):
    def test_resolve_paths_without_local_base_uses_app_audit_fallback_and_priority_markers(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            app_root = Path(temp_dir) / "DesktopApp"
            app_root.mkdir()
            service = DummyPathResolutionService(app_root, {"PriorityMarkers": ["!!", " ", "#"]})

            resolved = resolve_paths_for_service(service, "~/pipeline.ps1", "~/config.psd1")

            self.assertEqual(resolved.app_root, app_root)
            self.assertEqual(resolved.workspace_root, app_root.parent)
            self.assertEqual(resolved.powershell_host, "pwsh-test")
            self.assertEqual(resolved.audit_reports_path, app_root / "AuditReports")
            self.assertEqual(resolved.priority_markers, ["!!", "#"])
            self.assertEqual(service.loaded_config_request, (Path("~/config.psd1").expanduser(), "pwsh-test"))
            self.assertEqual(service.migrated_app_state_paths, [])

    def test_resolve_paths_with_local_base_populates_versioned_state_layout(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            app_root = root / "DesktopApp"
            app_root.mkdir()
            local_base = root / "Scratch"
            state_progress = local_base / "State" / "Progress"
            state_progress.mkdir(parents=True)
            state_progress_progress = state_progress / "pipeline_progress.json"
            state_progress_progress.write_text("{}", encoding="utf-8")
            service = DummyPathResolutionService(
                app_root,
                {
                    "LocalBase": str(local_base),
                    "SourceMovies": str(root / "Movies"),
                    "SourceTV": str(root / "TV"),
                    "PriorityMarkers": ["!", "[NOW]"],
                },
            )

            resolved = resolve_paths_for_service(service, str(root / "Pipeline.ps1"), str(root / "Config.psd1"))

            self.assertEqual(resolved.local_base, local_base)
            self.assertEqual(resolved.state_root, local_base / "State")
            self.assertEqual(resolved.active_jobs_path, local_base / "State" / "ActiveJobs")
            self.assertEqual(resolved.app_state_path, local_base / "State" / "App" / APP_STATE_NAME)
            self.assertEqual(service.migrated_app_state_paths, [resolved.app_state_path])
            self.assertEqual(resolved.source_movies, root / "Movies")
            self.assertEqual(resolved.source_tv, root / "TV")
            self.assertEqual(resolved.log_file, local_base / "pipeline_debug.log")
            self.assertEqual(resolved.progress_file, state_progress_progress)
            self.assertEqual(resolved.event_file, local_base / "State" / "Progress" / "pipeline_events.jsonl")
            self.assertEqual(resolved.pause_flag, local_base / "State" / "Pipeline" / "pipeline_pause.flag")
            self.assertEqual(resolved.failed_reports_path, local_base / "State" / "Failures" / "Reports")
            self.assertEqual(resolved.pending_push_path, local_base / "State" / "PendingServerPush")
            self.assertEqual(resolved.audit_reports_path, local_base / "AuditReports")
            self.assertEqual(resolved.queue_snapshot_path, local_base / "State" / "Progress" / "queue_snapshot.json")
            self.assertEqual(resolved.completed_manifest_path, local_base / "State" / "Completed" / "completed_jobs.jsonl")
            self.assertEqual(resolved.priority_markers, ["!", "[NOW]"])


if __name__ == "__main__":
    unittest.main()
