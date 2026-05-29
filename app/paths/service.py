from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from mediapipeline_desktop_app.models import ResolvedPaths
from app.paths.defaults import (
    default_audit_script_path_for_roots,
    default_config_path_for_roots,
    default_pipeline_path_for_roots,
    default_rerun_script_path_for_roots,
)
from app.paths.host import resolve_powershell_host_for_service, subprocess_kwargs_hidden
from app.paths.layout import (
    first_existing,
    normalized_path_key,
    path_or_none,
    path_within_root,
    state_root_for_local_base,
    valid_extensions_from_config,
)
from app.paths.resolution_runner import resolve_paths_for_service
from app.storage.state_migration import migrate_app_state_path_for_service


class PathResolutionServiceMixin:
    def resolve_powershell_host(self) -> str | None:
        return resolve_powershell_host_for_service(self, which_func=shutil.which)

    def _subprocess_kwargs_hidden(self) -> dict[str, Any]:
        return subprocess_kwargs_hidden()

    def _first_existing(self, *paths: Path) -> Path:
        return first_existing(*paths)

    def _state_root_for_local_base(self, local_base: Path) -> Path:
        return state_root_for_local_base(local_base)

    def _migrate_app_state_path(self, preferred_path: Path) -> None:
        migrate_app_state_path_for_service(self, preferred_path)

    def default_pipeline_path(self) -> Path:
        return default_pipeline_path_for_roots(self.app_root, self.workspace_root)

    def default_config_path(self) -> Path:
        return default_config_path_for_roots(self.app_root, self.workspace_root)

    def default_audit_script_path(self) -> Path:
        return default_audit_script_path_for_roots(self.app_root, self.workspace_root)

    def default_rerun_script_path(self) -> Path:
        return default_rerun_script_path_for_roots(self.app_root, self.workspace_root)

    def resolve_paths(self, pipeline_path: str, config_path: str) -> ResolvedPaths:
        return resolve_paths_for_service(self, pipeline_path, config_path)

    def _path_or_none(self, value: Any) -> Path | None:
        return path_or_none(value)

    def get_valid_extensions(self, resolved: ResolvedPaths) -> list[str]:
        return valid_extensions_from_config(resolved.config_data)

    def _normalized_path_key(self, path: Path) -> str:
        return normalized_path_key(path)

    def _path_within_root(self, path: Path, root: Path) -> bool:
        return path_within_root(path, root)
