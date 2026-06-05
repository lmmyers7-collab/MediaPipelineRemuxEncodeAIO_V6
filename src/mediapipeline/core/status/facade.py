"""Status-facing health, snapshot, and telemetry facade adapter."""

from __future__ import annotations

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
from mediapipeline.core.processes.path_evidence import configured_path_health, path_health_warning_lines
from mediapipeline.desktop.application.dto_status import AppSnapshotDto, HealthDto, TelemetryDto
from mediapipeline.desktop.models import ResolvedPaths, Snapshot, TelemetrySnapshot


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
        if not isinstance(snapshot, Snapshot):
            raise RuntimeError("Application facade service returned an invalid snapshot.")
        return self.snapshot_to_dto(snapshot)

    def snapshot_to_dto(self, snapshot: Snapshot) -> AppSnapshotDto:
        progress = dict(snapshot.progress or {})
        audit_progress = dict(snapshot.audit_progress or {})
        pipeline_state = self._pipeline_state(snapshot)
        worker_progress = worker_progress_payload(snapshot.resolved.active_jobs_path, progress, snapshot.log_tail)
        warnings = snapshot_warnings(snapshot)
        warnings.extend(path_health_warning_lines(configured_path_health(snapshot.resolved)))
        return AppSnapshotDto(
            app_version=self.app_version,
            activity=str(snapshot.current_activity or ""),
            pipeline_state=pipeline_state,
            status_summary=str(snapshot.status_summary or ""),
            current_work=build_current_work(
                progress,
                movie_cleaning_policy=rename_cleaning_policy_from_resolved(snapshot.resolved),
            ),
            counts=snapshot_counts(progress),
            progress=progress,
            audit_progress=audit_progress,
            worker_progress=worker_progress,
            ffmpeg_progress=ffmpeg_progress_payload(progress, snapshot.log_tail, worker_progress=worker_progress),
            eta=eta_payload(worker_progress, progress=progress),
            progress_bars=snapshot_progress_bars(snapshot, pipeline_state=pipeline_state),
            recent_events=snapshot_recent_events(snapshot),
            latest_paths=snapshot_latest_paths(snapshot),
            warnings=warnings,
        )

    def get_cached_telemetry(self) -> TelemetryDto:
        getter = getattr(self.service, "get_cached_telemetry", None)
        if not callable(getter):
            return TelemetryDto(error="Telemetry service is not available.")
        telemetry = getter()
        if not isinstance(telemetry, TelemetrySnapshot):
            return TelemetryDto(error="Telemetry service returned an invalid snapshot.")
        return self.telemetry_to_dto(telemetry)

    def telemetry_to_dto(self, telemetry: TelemetrySnapshot) -> TelemetryDto:
        return TelemetryDto(**telemetry_fields(telemetry))

__all__ = [
    "StatusFacadeMixin",
]
