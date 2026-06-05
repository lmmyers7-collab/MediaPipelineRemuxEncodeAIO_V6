from __future__ import annotations

from pathlib import Path
from typing import Protocol

from .launch_cleanup import prepare_stale_progress_cleanup
from .runtime_artifacts import (
    RuntimeArtifactSpec,
    clear_runtime_artifact_specs,
    filter_runtime_artifact_specs,
    runtime_artifact_specs,
    runtime_state_root_for_resolved,
    validate_runtime_artifact_target,
)


class WarningLogger(Protocol):
    def warning(self, message: object, *args: object, **kwargs: object) -> None: ...


class RuntimeResolvedPaths(Protocol):
    local_base: Path | None
    state_root: Path | None
    progress_file: Path | None
    pause_flag: Path | None
    stop_flag: Path | None
    rescan_flag: Path | None
    audit_reports_path: Path | None


class RuntimeArtifactService(Protocol):
    def _state_root_for_local_base(self, local_base: Path) -> Path: ...

    def _normalized_path_key(self, path: Path) -> str: ...


class RuntimeCleanupService(RuntimeArtifactService, Protocol):
    logger: WarningLogger

    def _runtime_artifact_specs(
        self,
        resolved: RuntimeResolvedPaths,
        *,
        include_pipeline: bool,
        include_audit: bool,
    ) -> list[RuntimeArtifactSpec]: ...

    def _clear_pipeline_progress_artifacts(self, resolved: RuntimeResolvedPaths) -> list[str]: ...

    def _clear_audit_progress_artifacts(self, resolved: RuntimeResolvedPaths) -> list[str]: ...

    def read_progress(self, resolved: RuntimeResolvedPaths) -> dict[str, object]: ...

    def is_progress_stale(self, progress: dict[str, object], *, stale_after_seconds: float) -> bool: ...

    def read_audit_progress(self, resolved: RuntimeResolvedPaths) -> dict[str, object]: ...

    def is_audit_progress_stale(self, progress: dict[str, object], *, stale_after_seconds: float) -> bool: ...

    def find_related_pipeline_processes(self, resolved: RuntimeResolvedPaths) -> list[object]: ...


def runtime_state_root_for_service(service: RuntimeArtifactService, resolved: RuntimeResolvedPaths) -> Path | None:
    return runtime_state_root_for_resolved(
        resolved,
        state_root_for_local_base=service._state_root_for_local_base,
    )


def runtime_artifact_specs_for_service(
    service: RuntimeArtifactService,
    resolved: RuntimeResolvedPaths,
    *,
    include_pipeline: bool,
    include_audit: bool,
) -> list[RuntimeArtifactSpec]:
    return runtime_artifact_specs(
        resolved,
        include_pipeline=include_pipeline,
        include_audit=include_audit,
        state_root_for_local_base=service._state_root_for_local_base,
        normalized_path_key=service._normalized_path_key,
    )


def validate_runtime_artifact_target_for_service(
    service: RuntimeArtifactService,
    label: str,
    path: Path,
    expected_paths: list[Path],
) -> None:
    validate_runtime_artifact_target(label, path, expected_paths, normalized_path_key=service._normalized_path_key)


def clear_runtime_artifacts_for_service(
    service: RuntimeCleanupService,
    resolved: RuntimeResolvedPaths,
    *,
    include_pipeline: bool,
    include_audit: bool,
) -> list[str]:
    return clear_runtime_artifact_specs(
        service._runtime_artifact_specs(resolved, include_pipeline=include_pipeline, include_audit=include_audit),
        normalized_path_key=service._normalized_path_key,
    )


def clear_pipeline_progress_artifacts_for_service(service: RuntimeCleanupService, resolved: RuntimeResolvedPaths) -> list[str]:
    specs = filter_runtime_artifact_specs(
        service._runtime_artifact_specs(resolved, include_pipeline=True, include_audit=False),
        labels={"pipeline progress", "legacy pipeline progress"},
    )
    return clear_runtime_artifact_specs(specs, normalized_path_key=service._normalized_path_key)


def prepare_pipeline_runtime_for_service(
    service: RuntimeCleanupService,
    resolved: RuntimeResolvedPaths,
    *,
    stale_after_seconds: float,
) -> list[str]:
    progress = service.read_progress(resolved)
    return prepare_stale_progress_cleanup(
        progress_label="pipeline",
        is_stale=service.is_progress_stale(progress, stale_after_seconds=stale_after_seconds),
        find_related_processes=lambda: service.find_related_pipeline_processes(resolved),
        clear_artifacts=lambda: service._clear_pipeline_progress_artifacts(resolved),
        logger=service.logger,
    )


def clear_audit_progress_artifacts_for_service(service: RuntimeCleanupService, resolved: RuntimeResolvedPaths) -> list[str]:
    specs = filter_runtime_artifact_specs(
        service._runtime_artifact_specs(resolved, include_pipeline=False, include_audit=True),
        labels={"audit progress"},
    )
    return clear_runtime_artifact_specs(specs, normalized_path_key=service._normalized_path_key)


def prepare_audit_runtime_for_service(
    service: RuntimeCleanupService,
    resolved: RuntimeResolvedPaths,
    *,
    stale_after_seconds: float,
) -> list[str]:
    audit_progress = service.read_audit_progress(resolved)
    return prepare_stale_progress_cleanup(
        progress_label="audit",
        is_stale=service.is_audit_progress_stale(audit_progress, stale_after_seconds=stale_after_seconds),
        find_related_processes=lambda: service.find_related_pipeline_processes(resolved),
        clear_artifacts=lambda: service._clear_audit_progress_artifacts(resolved),
        logger=service.logger,
    )
