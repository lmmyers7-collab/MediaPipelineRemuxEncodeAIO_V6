from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from mediapipeline.core.maintenance.command_policy import (
    DEPENDENCY_ATLAS_COMMAND,
    dependency_atlas_exception_result,
    dependency_atlas_invalid_result,
    dependency_atlas_open_exception_result,
    dependency_atlas_open_missing_result,
    dependency_atlas_open_service_unavailable_result,
    dependency_atlas_open_success_result,
    dependency_atlas_result,
    dependency_atlas_unavailable_result,
    maintenance_command_blocked_result,
)

if TYPE_CHECKING:
    from mediapipeline.core.kernel.dto_commands import CommandResult


class MaintenanceDependencyAtlasFacadeMixin:
    """Dependency-atlas generation command adapter for the application facade."""

    def run_dependency_atlas(self, request: dict[str, Any]) -> CommandResult:
        generator = getattr(self.service, "generate_dependency_atlas", None)
        if not callable(generator):
            return dependency_atlas_unavailable_result()
        timeout_seconds = self._bounded_timeout_seconds(request.get("timeout_seconds"), default=600, minimum=30, maximum=1800)
        min_edge_count = self._bounded_timeout_seconds(request.get("min_overview_edge_count"), default=4, minimum=1, maximum=50)
        min_files = self._bounded_timeout_seconds(request.get("min_overview_files"), default=2, minimum=1, maximum=50)
        lock, block_message = self._acquire_maintenance_command_lock("Dependency atlas generation")
        if block_message:
            return maintenance_command_blocked_result(DEPENDENCY_ATLAS_COMMAND, block_message)
        try:
            result = generator(
                timeout_seconds=timeout_seconds,
                min_overview_edge_count=min_edge_count,
                min_overview_files=min_files,
            )
        except Exception as exc:
            return dependency_atlas_exception_result(exc)
        finally:
            self._release_maintenance_command_lock(lock)
        if not isinstance(result, dict):
            return dependency_atlas_invalid_result()
        normalized_request = {
            **request,
            "timeout_seconds": timeout_seconds,
            "min_overview_edge_count": min_edge_count,
            "min_overview_files": min_files,
        }
        return dependency_atlas_result(result, normalized_request)

    def open_dependency_atlas_folder(self) -> CommandResult:
        path = self._dependency_atlas_output_dir()
        if not path.exists() or not path.is_dir():
            return dependency_atlas_open_missing_result(path)
        opener = getattr(self.service, "open_path", None)
        if not callable(opener):
            return dependency_atlas_open_service_unavailable_result(path)
        try:
            opener(path)
        except Exception as exc:
            return dependency_atlas_open_exception_result(path, exc)
        return dependency_atlas_open_success_result(path)

    def _dependency_atlas_output_dir(self) -> Path:
        output_dir = getattr(self.service, "dependency_atlas_output_dir", None)
        if callable(output_dir):
            path = output_dir()
            return path if isinstance(path, Path) else Path(path)
        return Path(self.service.workspace_root) / "docs/generated/dependency-atlas"


__all__ = [
    "MaintenanceDependencyAtlasFacadeMixin",
]
