from __future__ import annotations

from pathlib import Path

from mediapipeline.core.kernel.config_locations import (
    CONFIG_CANONICAL_NAME,
    CONFIG_LEGACY_NAME,
    PER_USER_APP_DIR_NAME,
    user_config_candidates,
    user_config_dir,
)


def first_existing(*paths: Path) -> Path:
    for path in paths:
        if path.exists():
            return path
    return paths[0]


def default_pipeline_path_for_roots(app_root: Path, workspace_root: Path) -> Path:
    return first_existing(
        workspace_root / "ops" / "pipeline" / "entrypoints" / "MediaPipeline.ps1",
        app_root / "entrypoints" / "MediaPipeline.ps1",
    )


def default_config_path_for_roots(app_root: Path, workspace_root: Path) -> Path:
    # Prefer the per-user durable home. The repository/bundle config is a seed
    # and dev fallback because personal configs are gitignored and release
    # hygiene can intentionally exclude them.
    return first_existing(
        *user_config_candidates(),
        workspace_root / "ops" / "pipeline" / "config" / CONFIG_CANONICAL_NAME,
        app_root / "config" / CONFIG_CANONICAL_NAME,
        workspace_root / "ops" / "pipeline" / "config" / CONFIG_LEGACY_NAME,
        app_root / "config" / CONFIG_LEGACY_NAME,
    )


def default_audit_script_path_for_roots(app_root: Path, workspace_root: Path) -> Path:
    return first_existing(
        workspace_root / "ops" / "pipeline" / "entrypoints" / "Audit-MediaLibrary.ps1",
        app_root / "entrypoints" / "Audit-MediaLibrary.ps1",
    )


def default_rerun_script_path_for_roots(app_root: Path, workspace_root: Path) -> Path:
    return first_existing(
        workspace_root / "ops" / "pipeline" / "entrypoints" / "Invoke-RerunCsv.ps1",
        app_root / "entrypoints" / "Invoke-RerunCsv.ps1",
    )


__all__ = [
    "CONFIG_CANONICAL_NAME",
    "CONFIG_LEGACY_NAME",
    "PER_USER_APP_DIR_NAME",
    "default_audit_script_path_for_roots",
    "default_config_path_for_roots",
    "default_pipeline_path_for_roots",
    "default_rerun_script_path_for_roots",
    "first_existing",
    "user_config_candidates",
    "user_config_dir",
]
