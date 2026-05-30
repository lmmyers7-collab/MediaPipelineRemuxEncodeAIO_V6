from __future__ import annotations

from pathlib import Path

from .layout import first_existing


def default_pipeline_path_for_roots(app_root: Path, workspace_root: Path) -> Path:
    return first_existing(
        workspace_root / "Pipeline" / "MediaPipeline.ps1",
        app_root / "Pipeline" / "MediaPipeline.ps1",
        workspace_root / "MediaPipeline.ps1",
        app_root / "MediaPipeline.ps1",
    )


def default_config_path_for_roots(app_root: Path, workspace_root: Path) -> Path:
    # Prefer the V7 convention (no brand-smell suffix); fall back to the
    # legacy `_chatgpt` name so operators with an existing local config
    # keep working until they rename. Remove the legacy entries one release
    # after every active operator has migrated.
    return first_existing(
        workspace_root / "Pipeline" / "MediaPipeline_config.psd1",
        app_root / "Pipeline" / "MediaPipeline_config.psd1",
        workspace_root / "MediaPipeline_config.psd1",
        app_root / "MediaPipeline_config.psd1",
        workspace_root / "Pipeline" / "MediaPipeline_config_chatgpt.psd1",
        app_root / "Pipeline" / "MediaPipeline_config_chatgpt.psd1",
        workspace_root / "MediaPipeline_config_chatgpt.psd1",
        app_root / "MediaPipeline_config_chatgpt.psd1",
    )


def default_audit_script_path_for_roots(app_root: Path, workspace_root: Path) -> Path:
    return first_existing(
        workspace_root / "Pipeline" / "Audit-MediaLibrary.ps1",
        app_root / "Pipeline" / "Audit-MediaLibrary.ps1",
        workspace_root / "Audit-MediaLibrary.ps1",
        app_root / "Audit-MediaLibrary.ps1",
    )


def default_rerun_script_path_for_roots(app_root: Path, workspace_root: Path) -> Path:
    return first_existing(
        workspace_root / "Pipeline" / "Invoke-RerunCsv.ps1",
        app_root / "Pipeline" / "Invoke-RerunCsv.ps1",
        workspace_root / "Invoke-RerunCsv.ps1",
        app_root / "Invoke-RerunCsv.ps1",
    )
