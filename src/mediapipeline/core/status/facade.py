"""Status-facing health, snapshot, and telemetry facade adapter."""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING

from mediapipeline.core.observability.status_policy import (
    application_capabilities,
    snapshot_counts,
    snapshot_latest_paths,
    snapshot_progress_bars,
    snapshot_recent_events,
    snapshot_warnings,
    telemetry_fields,
)
from mediapipeline.core.rename.policy import rename_cleaning_policy_from_resolved
from mediapipeline.core.status.active_jobs import worker_progress_payload
from mediapipeline.core.status.eta import eta_payload
from mediapipeline.core.status.ffmpeg_progress import ffmpeg_progress_payload
from mediapipeline.core.status.presentation import build_current_work
from mediapipeline.core.status.runtime_health import runtime_reliability_counters
from mediapipeline.core.status.run_monitor import (
    read_backend_correlated_run_monitor_projection,
    unavailable_run_monitor_projection,
)
from mediapipeline.core.status.rerun_completion import csv_rerun_completion_summary
from mediapipeline.core.status.progress import TERMINAL_PROGRESS_STAGES, datetime_is_stale
from mediapipeline.core.processes.path_evidence import configured_path_health, path_health_warning_lines
from mediapipeline.core.kernel.dto_status import AppSnapshotDto, HealthDto, TelemetryDto
from mediapipeline.core.paths.contracts import ResolvedPaths

if TYPE_CHECKING:
    from mediapipeline.core.status.contracts import Snapshot
    from mediapipeline.core.telemetry.contracts import TelemetrySnapshot


def _snapshot_type() -> type:
    return import_module("mediapipeline.core.status.contracts").Snapshot


def _telemetry_snapshot_type() -> type:
    return import_module("mediapipeline.core.telemetry.contracts").TelemetrySnapshot


class StatusFacadeMixin:
    """Health, snapshot, and telemetry query adapter for application facades."""

    service: object
    app_name: str
    app_version: str

    def get_health(self, resolved: ResolvedPaths | None = None) -> HealthDto:
        app_root = ""
        workspace_root = ""
        warnings: list[str] = []
        if resolved is not None:
            app_root = str(resolved.app_root)
            workspace_root = str(resolved.workspace_root)
            if not resolved.powershell_host:
                warnings.append("PowerShell host is not resolved.")
        else:
            app_root = str(getattr(self.service, "app_root", "") or "")
            workspace_root = str(getattr(self.service, "workspace_root", "") or "")
        return HealthDto(
            app_name=self.app_name,
            app_version=self.app_version,
            status="ok",
            app_root=app_root,
            workspace_root=workspace_root,
            capabilities=application_capabilities(),
            warnings=warnings,
        )

    def get_snapshot(self, resolved: ResolvedPaths, audit_root: str = "") -> AppSnapshotDto:
        build_snapshot = getattr(self.service, "build_snapshot", None)
        if not callable(build_snapshot):
            raise RuntimeError("Application facade service does not support build_snapshot().")
        snapshot = build_snapshot(resolved, audit_root)
        if not isinstance(snapshot, _snapshot_type()):
            raise RuntimeError("Application facade service returned an invalid snapshot.")
        return self.snapshot_to_dto(snapshot)

    def get_run_monitor(self, resolved: ResolvedPaths, *, run_id: str = "") -> dict[str, object]:
        state_root = resolved.state_root
        if state_root is None and resolved.run_monitor_path is not None:
            state_root = resolved.run_monitor_path.parent
        if state_root is None:
            return unavailable_run_monitor_projection(
                reason_code="state_root_unavailable",
                backend_activity_state="unavailable",
            )
        return read_backend_correlated_run_monitor_projection(
            state_root,
            resolved.active_jobs_path,
            run_id=run_id or None,
            pid_alive=getattr(self, "_active_job_pid_is_alive", None),
        )

    def snapshot_to_dto(self, snapshot: Snapshot) -> AppSnapshotDto:
        progress = dict(snapshot.progress or {})
        audit_progress = dict(snapshot.audit_progress or {})
        observed_pipeline_state = self._pipeline_state(snapshot)
        stale_progress = observed_pipeline_state == "stale"
        pipeline_state = "idle" if stale_progress else observed_pipeline_state
        worker_progress = worker_progress_payload(snapshot.resolved.active_jobs_path, progress, snapshot.log_tail)
        warnings = snapshot_warnings(snapshot)
        warnings.extend(path_health_warning_lines(configured_path_health(snapshot.resolved)))
        read_health = progress.get("ReadHealth") if isinstance(progress.get("ReadHealth"), dict) else None
        stage = str(progress.get("CurrentStage") or "").strip().casefold()
        progress_health = dict(read_health or {})
        if not progress_health:
            progress_health = {
                "schema_version": "desktop_progress_read_health.v1",
                "status": "available" if progress else "absent",
                "available": bool(progress),
                "source_present": bool(progress),
            }
        progress_health["terminal"] = stage in TERMINAL_PROGRESS_STAGES
        progress_health["terminal_evidence_stale"] = bool(
            progress_health["terminal"]
            and datetime_is_stale(str(progress.get("LastUpdate") or ""), 5.0)
        )
        progress_health["stale_evidence"] = stale_progress
        if progress_health.get("available") is False:
            warnings.append(
                "Pipeline progress is unavailable or invalid; idle/current work cannot be inferred from this evidence."
            )
        progress_bars = snapshot_progress_bars(snapshot, pipeline_state=pipeline_state)
        if stale_progress:
            progress_bars = [bar for bar in progress_bars if bar.get("source") != "pipeline_progress.json"]
        recent_events = snapshot_recent_events(snapshot)
        current_work = (
            build_current_work({}, pipeline_state="idle")
            if stale_progress
            else build_current_work(
                progress,
                movie_cleaning_policy=rename_cleaning_policy_from_resolved(snapshot.resolved),
                pipeline_events=recent_events,
                progress_bars=progress_bars,
                pipeline_state=pipeline_state,
            )
        )
        counts = snapshot_counts(progress)
        counts["long_run_reliability"] = runtime_reliability_counters(snapshot.resolved, progress=progress)
        return AppSnapshotDto(
            app_version=self.app_version,
            activity="No active work reported." if stale_progress else str(snapshot.current_activity or ""),
            pipeline_state=pipeline_state,
            status_summary=str(snapshot.status_summary or ""),
            current_work=current_work,
            counts=counts,
            progress=progress,
            progress_health=progress_health,
            audit_progress=audit_progress,
            worker_progress=worker_progress,
            ffmpeg_progress=ffmpeg_progress_payload(progress, snapshot.log_tail, worker_progress=worker_progress),
            eta=eta_payload(worker_progress, progress=progress),
            progress_bars=progress_bars,
            recent_events=recent_events,
            latest_paths=snapshot_latest_paths(snapshot),
            warnings=warnings,
            csv_rerun_summary=csv_rerun_completion_summary(snapshot.resolved),
        )

    def get_cached_telemetry(self) -> TelemetryDto:
        getter = getattr(self.service, "get_cached_telemetry", None)
        if not callable(getter):
            return TelemetryDto(error="Telemetry service is not available.")
        telemetry = getter()
        if not isinstance(telemetry, _telemetry_snapshot_type()):
            return TelemetryDto(error="Telemetry service returned an invalid snapshot.")
        return self.telemetry_to_dto(telemetry)

    def telemetry_to_dto(self, telemetry: TelemetrySnapshot) -> TelemetryDto:
        return TelemetryDto(**telemetry_fields(telemetry))

__all__ = [
    "StatusFacadeMixin",
]
