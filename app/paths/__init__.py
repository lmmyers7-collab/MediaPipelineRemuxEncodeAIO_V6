"""Path selection, normalization, and boundary helpers."""

from .defaults import (
    default_audit_script_path_for_roots,
    default_config_path_for_roots,
    default_pipeline_path_for_roots,
    default_rerun_script_path_for_roots,
)
from .host import resolve_powershell_host_for_service, subprocess_kwargs_hidden
from .layout import (
    PathBoundaryCheck,
    ensure_path_boundary_safe_for_mutation,
    first_existing,
    normalized_path_key,
    path_boundary_check,
    path_or_none,
    path_within_root,
    state_root_for_local_base,
    valid_extensions_from_config,
)

__all__ = [
    "PathBoundaryCheck",
    "default_audit_script_path_for_roots",
    "default_config_path_for_roots",
    "default_pipeline_path_for_roots",
    "default_rerun_script_path_for_roots",
    "ensure_path_boundary_safe_for_mutation",
    "first_existing",
    "normalized_path_key",
    "path_boundary_check",
    "path_or_none",
    "path_within_root",
    "resolve_powershell_host_for_service",
    "state_root_for_local_base",
    "subprocess_kwargs_hidden",
    "valid_extensions_from_config",
]
