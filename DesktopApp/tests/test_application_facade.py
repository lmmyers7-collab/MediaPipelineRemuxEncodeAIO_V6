from __future__ import annotations

import csv
from datetime import datetime, timedelta
import io
import json
import logging
import os
import re
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from urllib.parse import quote
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mediapipeline_desktop_app.api import LocalApiServer
from mediapipeline_desktop_app.api.command_journal import CommandJournal
from app.api.commands_process import LocalApiProcessCommandPayloadMixin
from mediapipeline_desktop_app.api.contract import LOCAL_API_ROUTE_CONTRACT
from mediapipeline_desktop_app.api.contract_command import LOCAL_API_COMMAND_ROUTE_CONTRACT
from mediapipeline_desktop_app.api.contract_read import LOCAL_API_READ_ROUTE_CONTRACT
from mediapipeline_desktop_app.api.handler import build_local_api_handler_class
from mediapipeline_desktop_app.api.http_helpers import (
    content_type_for,
    query_bool,
    query_int,
    query_value,
    read_json_body,
    request_authorized,
    resolve_asset_path,
)
from mediapipeline_desktop_app.api.routes import GET_ROUTE_HANDLERS, POST_ROUTE_HANDLERS
from mediapipeline_desktop_app.api.static_files import local_api_bootstrap, read_static_asset, render_index
from mediapipeline_desktop_app.application import CommandResult, MediaPipelineApplicationFacade
from mediapipeline_desktop_app.local_api_main import BOOTSTRAP_SCHEMA_VERSION, bootstrap_payload, build_backend
from mediapipeline_desktop_app.models import AuditRecord, ConfigSaveResult, FailureRecord, ResolvedPaths, Snapshot, TelemetrySnapshot
from app.schedule.app_state import AppStateScheduleServiceMixin
from app.completed.service import CompletedJobsServiceMixin
from app.publish.pending_service import PendingPublishServiceMixin
from app.processes.lifecycle import ProcessLifecycleServiceMixin
from app.queue.service import QueueServiceMixin
from app.rename.service import RenameServiceMixin
from mediapipeline_desktop_app.subprocess_runner import CapturedCommandResult


def _render_static_index_html(static_root: Path) -> str:
    response = render_index(
        static_root,
        {"token": "test-token", "appVersion": "v5-test", "shellSurface": "webview"},
    )
    if response.status != 200:
        raise AssertionError(f"index render failed with status {response.status}: {response.body!r}")
    return response.body.decode("utf-8")


class DummyFacadeService(AppStateScheduleServiceMixin):
    def __init__(self, root: Path) -> None:
        self.app_root = root
        self.workspace_root = root
        self.app_state_path = root / "desktop_app_state.json"
        self.logger = logging.getLogger("test_application_facade")
        self.telemetry = TelemetrySnapshot(
            collected_at=datetime(2026, 5, 7, 21, 0, 0),
            cpu_percent=12.0,
            memory_percent=44.0,
            gpu_encoder_percent=0.0,
            gpu_name="NVIDIA GPU",
            gpu_count=1,
            gpu_rows=[{"index": "0", "name": "NVIDIA GPU", "encoder_percent": 0.0}],
            source="nvidia-smi",
        )
        self.snapshot: Snapshot | None = None
        self.opened_paths: list[Path] = []
        self.saved_config_calls: list[dict[str, object]] = []
        self.release_build_calls: list[dict[str, object]] = []
        self.dependency_atlas_calls: list[dict[str, object]] = []
        self._completed_history_cache_key: str | None = None
        self._completed_history_cache_limit_key = ""
        self._completed_history_cached_at = 0.0
        self._completed_history_manifest_mtime = 0.0
        self._completed_history_records = []

    def build_snapshot(self, resolved: ResolvedPaths, audit_root: str) -> Snapshot:
        _ = audit_root
        if self.snapshot is not None:
            return self.snapshot
        return Snapshot(
            resolved=resolved,
            current_activity="Current activity: Ready.",
            status_summary="Status OK",
            log_tail="log line",
            progress={
                "ProgressVersion": 2,
                "Status": "Processing",
                "CurrentQueueIndex": 2,
                "CurrentQueueTotal": 5,
                "TotalProcessed": 10,
                "Encoded": 3,
                "Remuxed": 7,
                "Failed": 1,
                "Movies": 4,
                "TVEpisodes": 6,
            },
            audit_progress=None,
            latest_failure_report=resolved.workspace_root / "failures.txt",
            latest_failure_json=resolved.workspace_root / "failures.json",
            latest_audit_csv=None,
            latest_priority_csv=None,
            pipeline_events=[
                {
                    "schema_version": "pipeline_event.v1",
                    "event_id": "event-1",
                    "event_type": "job_started",
                    "timestamp": "2026-05-07T21:00:00-04:00",
                    "created_at": "2026-05-07T21:00:00-04:00",
                    "data": {"display_name": "Movie.mkv"},
                }
            ],
        )

    def get_cached_telemetry(self) -> TelemetrySnapshot:
        return self.telemetry

    def format_diagnostics_error_summary(self, snapshot: Snapshot) -> str:
        _ = snapshot
        return "No recent pipeline errors found."

    def format_diagnostics_event_summary(self, snapshot: Snapshot) -> str:
        return "\n".join(str(event.get("event_type") or "") for event in snapshot.pipeline_events)

    def _format_active_job_summary(self, resolved: ResolvedPaths) -> list[str]:
        _ = resolved
        return ["pipeline once: active (pid 1234) launched 2026-05-07T21:00:00-04:00"]

    def launch_log_summary(self) -> str:
        return "stdout: run.stdout.log | stderr: run.stderr.log"

    def validate_config_values(self, values: dict) -> tuple[list[str], list[str]]:
        warnings = ["LocalBase shares a volume with SourceTV."] if values.get("LocalBase") and values.get("SourceTV") else []
        return [], warnings

    def serialize_psd1_document(self, values: dict) -> str:
        lines = ["@{"]
        for key, value in sorted(values.items()):
            escaped = str(value).replace("'", "''")
            lines.append(f"    {key} = '{escaped}'")
        lines.extend(["}", ""])
        return "\n".join(lines)

    def save_config_document(
        self,
        output_path: Path,
        document_text: str,
        create_backup: bool,
        *,
        config_values: dict | None = None,
        powershell_host: str | None = None,
    ) -> ConfigSaveResult:
        self.saved_config_calls.append(
            {
                "output_path": output_path,
                "document_text": document_text,
                "create_backup": create_backup,
                "config_values": dict(config_values or {}),
                "powershell_host": powershell_host,
            }
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        backup_path = output_path.parent / "ConfigBackups" / f"{output_path.stem}.backup{output_path.suffix}" if create_backup and output_path.exists() else None
        if backup_path is not None:
            backup_path.parent.mkdir(parents=True, exist_ok=True)
            backup_path.write_text(output_path.read_text(encoding="utf-8"), encoding="utf-8")
        output_path.write_text(document_text, encoding="utf-8")
        return ConfigSaveResult(output_path=output_path, backup_path=backup_path)

    def list_config_profiles(self, config_path: Path) -> list[str]:
        _ = config_path
        return ["Default", "DirectPlay"]

    def check_environment_health(self, resolved: ResolvedPaths) -> list[tuple[str, bool, str]]:
        return [
            ("PowerShell (pwsh)", bool(resolved.powershell_host), str(resolved.powershell_host or "")),
            ("ffmpeg", True, str(self.workspace_root / "Pipeline" / "Tools" / "ffmpeg" / "bin" / "ffmpeg.exe")),
            ("nvidia-smi (optional)", False, "Not found - GPU encoder telemetry unavailable"),
        ]

    def latest_failure_json(self, resolved: ResolvedPaths) -> Path | None:
        path = resolved.workspace_root / "failures.json"
        return path if path.exists() else None

    def latest_failure_report(self, resolved: ResolvedPaths) -> Path | None:
        path = resolved.workspace_root / "failures.txt"
        return path if path.exists() else None

    def load_failure_records(self, json_path: Path) -> list[FailureRecord]:
        raw = json.loads(Path(json_path).read_text(encoding="utf-8"))
        if not isinstance(raw, list):
            raise RuntimeError("failure json must be a list")
        return [FailureRecord(source_json=Path(json_path), payload=item) for item in raw if isinstance(item, dict)]

    def load_failure_marker_records(self, resolved: ResolvedPaths) -> list[FailureRecord]:
        markers_path = resolved.failed_markers_path
        if not markers_path or not markers_path.exists():
            return []
        key_map = {
            "source_full_path": "SourcePath",
            "stage": "Stage",
            "reason": "Reason",
            "classification": "Classification",
            "error_code": "ErrorCode",
            "artifact_path": "ArtifactPath",
            "recorded_at": "RecordedAt",
            "suggested_action": "SuggestedAction",
            "suggested_rename": "SuggestedRename",
            "repro_path": "ReproPath",
            "retry_count": "RetryCount",
            "retry_limit": "RetryLimit",
            "escalated": "Escalated",
        }
        records: list[FailureRecord] = []
        for marker_file in sorted(markers_path.glob("*.json")):
            raw = json.loads(marker_file.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                records.append(FailureRecord(source_json=marker_file, payload={key_map.get(str(key), str(key)): value for key, value in raw.items()}))
        return records

    def latest_audit_csv(self, resolved: ResolvedPaths, priority_only: bool) -> Path | None:
        candidates = (
            ["audit_priority_latest.csv", "audit_summary_latest.csv"]
            if priority_only
            else ["audit_summary_latest.csv", "audit_priority_latest.csv"]
        )
        for name in candidates:
            path = resolved.workspace_root / name
            if path.exists():
                return path
        return None

    def load_audit_records(self, csv_path: Path) -> list[AuditRecord]:
        with Path(csv_path).open("r", encoding="utf-8", errors="replace", newline="") as handle:
            reader = csv.DictReader(handle)
            return [
                AuditRecord(source_csv=Path(csv_path), row={str(key): str(value or "") for key, value in row.items() if key is not None})
                for row in reader
            ]

    def build_release_package(self, **kwargs: object) -> dict[str, object]:
        self.release_build_calls.append(dict(kwargs))
        destination = Path(str(kwargs.get("destination_root") or self.workspace_root.parent / "MediaPipeline_Deployable_DryRun"))
        dry_run = bool(kwargs.get("dry_run", True))
        stdout = "\n".join(
            [
                f"Source      : {self.workspace_root}",
                f"Destination : {destination}",
                "Copy files  : 12",
                "Exclude     : 3",
                "",
                "Dry run only. No files copied." if dry_run else "Release build complete.",
            ]
        )
        return {
            "success": True,
            "timed_out": False,
            "returncode": 0,
            "command": "pwsh -File scripts\\release\\build.ps1" + (" -DryRun" if dry_run else ""),
            "stdout": stdout,
            "stderr": "",
            "destination_root": str(destination),
            "manifest_path": str(destination / "release_manifest.json"),
            "manifest_exists": not dry_run,
            "zip_path": str(destination) + ".zip",
            "zip_exists": (not dry_run) and bool(kwargs.get("zip_package", True)),
            "dry_run": dry_run,
            "elapsed_seconds": 1.25,
            "manifest": {"schema_version": "mediapipeline_release_manifest.v1"} if not dry_run else None,
        }

    def generate_dependency_atlas(self, **kwargs: object) -> dict[str, object]:
        self.dependency_atlas_calls.append(dict(kwargs))
        assets_dir = self.workspace_root / "V6_dependency_atlas_assets"
        return {
            "success": True,
            "timed_out": False,
            "returncode": 0,
            "command": "python scripts\\dev\\generate_dependency_atlas.py",
            "stdout": "\n".join(
                [
                    "Graphviz dot: C:\\Program Files\\Graphviz\\bin\\dot.exe",
                    "Modules: 377",
                    "Module edges: 839",
                    "Domains: 47",
                    "Domain edges: 170",
                    "Detail diagrams: 46",
                    "HTML local links checked: 144",
                    f"Open: {self.workspace_root / 'V6_dependency_atlas.html'}",
                ]
            ),
            "stderr": "",
            "elapsed_seconds": 2.5,
            "atlas_html": str(self.workspace_root / "V6_dependency_atlas.html"),
            "atlas_png": str(self.workspace_root / "V6_dependency_atlas.png"),
            "atlas_svg": str(self.workspace_root / "V6_dependency_atlas.svg"),
            "assets_dir": str(assets_dir),
            "summary_csv": str(assets_dir / "dependency_summary.csv"),
            "domain_edges_csv": str(assets_dir / "dependency_edges.csv"),
            "module_edges_csv": str(assets_dir / "dependency_module_edges.csv"),
            "html_exists": True,
            "png_exists": True,
            "svg_exists": True,
            "summary_csv_exists": True,
            "domain_edges_csv_exists": True,
            "module_edges_csv_exists": True,
        }

    def open_path(self, path: Path | str | None) -> None:
        if path is None:
            raise FileNotFoundError("Path does not exist: <none>")
        target = Path(path)
        if not target.exists():
            raise FileNotFoundError(f"Path does not exist: {target}")
        self.opened_paths.append(target)


class DummyProc:
    def __init__(self, pid: int = 24680) -> None:
        self.pid = pid


class DummyWorkflowFacadeService(DummyFacadeService, QueueServiceMixin, RenameServiceMixin, PendingPublishServiceMixin, CompletedJobsServiceMixin, ProcessLifecycleServiceMixin):
    def prepare_pipeline_runtime_for_launch(self, resolved: ResolvedPaths) -> list[str]:
        _ = resolved
        return ["runtime ready"]

    def prepare_pipeline_control_flags_for_launch(self, resolved: ResolvedPaths) -> list[str]:
        _ = resolved
        return ["control flags ready"]

    def start_pipeline(
        self,
        resolved: ResolvedPaths,
        mode: str,
        show_config: bool,
        sleep_seconds: int,
        extra_args: str,
        show_console: bool,
        single_file: str | None = None,
    ) -> DummyProc:
        self.started_pipeline = {
            "resolved": resolved,
            "mode": mode,
            "show_config": show_config,
            "sleep_seconds": sleep_seconds,
            "extra_args": extra_args,
            "show_console": show_console,
            "single_file": single_file,
        }
        return DummyProc()

    def prepare_audit_runtime_for_launch(self, resolved: ResolvedPaths) -> list[str]:
        _ = resolved
        return ["audit runtime ready"]

    def start_audit(
        self,
        resolved: ResolvedPaths,
        library_root: str,
        include_sidecars: bool,
        show_console: bool,
    ) -> DummyProc:
        self.started_audit = {
            "resolved": resolved,
            "library_root": library_root,
            "include_sidecars": include_sidecars,
            "show_console": show_console,
        }
        return DummyProc(24681)

    def start_rerun_csv(
        self,
        resolved: ResolvedPaths,
        csv_path: Path,
        *,
        dry_run: bool,
        stage_mode: str,
        original_mode: str,
        return_mode: str,
        show_console: bool,
    ) -> DummyProc:
        self.started_rerun = {
            "resolved": resolved,
            "csv_path": csv_path,
            "dry_run": dry_run,
            "stage_mode": stage_mode,
            "original_mode": original_mode,
            "return_mode": return_mode,
            "show_console": show_console,
        }
        return DummyProc(24682)


def _resolved(root: Path) -> ResolvedPaths:
    return ResolvedPaths(
        app_root=root,
        workspace_root=root,
        pipeline_path=root / "pipeline.ps1",
        config_path=root / "config.psd1",
        audit_script_path=root / "audit.ps1",
        rerun_script_path=root / "rerun.ps1",
        powershell_host=str(root / "pwsh.exe"),
            active_jobs_path=root / "State" / "ActiveJobs",
            pause_flag=root / "State" / "Pipeline" / "pipeline_pause.flag",
            stop_flag=root / "State" / "Pipeline" / "pipeline_stop.flag",
            rescan_flag=root / "State" / "Pipeline" / "pipeline_rescan.flag",
    )

if __name__ == "__main__":
    unittest.main()


