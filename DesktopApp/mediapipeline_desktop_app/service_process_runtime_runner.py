from __future__ import annotations

from pathlib import Path
from typing import Any

from .models import ResolvedPaths
from .service_process_launch_cleanup import prepare_stale_progress_cleanup
from .service_process_runtime_artifacts import (
    clear_runtime_artifact_specs,
    filter_runtime_artifact_specs,
    runtime_artifact_specs,
    runtime_state_root_for_resolved,
    validate_runtime_artifact_target,
)
from .service_runner_protocols import RuntimeArtifactServiceProtocol, RuntimeCleanupServiceProtocol


def runtime_state_root_for_service(service: RuntimeArtifactServiceProtocol, resolved: ResolvedPaths) -> Path | None:
    return runtime_state_root_for_resolved(
        resolved,
        state_root_for_local_base=service._state_root_for_local_base,
    )


def runtime_artifact_specs_for_service(
    service: RuntimeArtifactServiceProtocol,
    resolved: ResolvedPaths,
    *,
    include_pipeline: bool,
    include_audit: bool,
) -> list[tuple[str, Path | None, list[Path]]]:
    return runtime_artifact_specs(
        resolved,
        include_pipeline=include_pipeline,
        include_audit=include_audit,
        state_root_for_local_base=service._state_root_for_local_base,
        normalized_path_key=service._normalized_path_key,
    )


def validate_runtime_artifact_target_for_service(
    service: RuntimeArtifactServiceProtocol,
    label: str,
    path: Path,
    expected_paths: list[Path],
) -> None:
    validate_runtime_artifact_target(label, path, expected_paths, normalized_path_key=service._normalized_path_key)


def clear_runtime_artifacts_for_service(
    service: RuntimeCleanupServiceProtocol,
    resolved: ResolvedPaths,
    *,
    include_pipeline: bool,
    include_audit: bool,
) -> list[str]:
    return clear_runtime_artifact_specs(
        service._runtime_artifact_specs(resolved, include_pipeline=include_pipeline, include_audit=include_audit),
        normalized_path_key=service._normalized_path_key,
    )


def clear_pipeline_progress_artifacts_for_service(service: RuntimeCleanupServiceProtocol, resolved: ResolvedPaths) -> list[str]:
    specs = filter_runtime_artifact_specs(
        service._runtime_artifact_specs(resolved, include_pipeline=True, include_audit=False),
        labels={"pipeline progress", "legacy pipeline progress"},
    )
    return clear_runtime_artifact_specs(specs, normalized_path_key=service._normalized_path_key)


def prepare_pipeline_runtime_for_service(
    service: RuntimeCleanupServiceProtocol,
    resolved: ResolvedPaths,
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


def clear_audit_progress_artifacts_for_service(service: RuntimeCleanupServiceProtocol, resolved: ResolvedPaths) -> list[str]:
    specs = filter_runtime_artifact_specs(
        service._runtime_artifact_specs(resolved, include_pipeline=False, include_audit=True),
        labels={"audit progress"},
    )
    return clear_runtime_artifact_specs(specs, normalized_path_key=service._normalized_path_key)


def prepare_audit_runtime_for_service(
    service: RuntimeCleanupServiceProtocol,
    resolved: ResolvedPaths,
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
