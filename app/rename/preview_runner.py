from __future__ import annotations

from pathlib import Path
from typing import Any

from app.shared.protocols import RenamePreviewLoadServiceProtocol, RenamePreviewScriptServiceProtocol, RunCaptureFunc
from app.rename.preview import find_naming_preview_script, load_pipeline_name_previews
from mediapipeline_desktop_app.subprocess_runner import CapturedCommandResult


def naming_preview_script_path_for_service(service: RenamePreviewScriptServiceProtocol) -> Path | None:
    return find_naming_preview_script(
        getattr(service, "workspace_root", None),
        getattr(service, "app_root", None),
    )


def load_pipeline_name_previews_for_service(
    service: RenamePreviewLoadServiceProtocol,
    paths: list[Path],
    *,
    media_kind: str,
    powershell_host: str | None,
    timeout_seconds: int,
    run_capture_func: RunCaptureFunc,
) -> tuple[dict[str, str], str]:
    script_path = service._naming_preview_script_path()
    hidden_kwargs: dict[str, Any] = {}
    hidden_helper = getattr(service, "_subprocess_kwargs_hidden", None)
    if callable(hidden_helper):
        hidden_kwargs = hidden_helper()
    return load_pipeline_name_previews(
        paths,
        media_kind=media_kind,
        powershell_host=powershell_host,
        script_path=script_path,
        timeout_seconds=timeout_seconds,
        hidden_kwargs=hidden_kwargs,
        logger=service.logger,
        run_capture_func=run_capture_func,
    )


def load_pipeline_movie_name_previews_for_service(
    service: RenamePreviewLoadServiceProtocol,
    paths: list[Path],
    *,
    powershell_host: str | None,
    timeout_seconds: int,
    run_capture_func: RunCaptureFunc,
) -> tuple[dict[str, str], str]:
    return load_pipeline_name_previews_for_service(
        service,
        paths,
        media_kind="Movie",
        powershell_host=powershell_host,
        timeout_seconds=timeout_seconds,
        run_capture_func=run_capture_func,
    )


def load_pipeline_tv_name_previews_for_service(
    service: RenamePreviewLoadServiceProtocol,
    paths: list[Path],
    *,
    powershell_host: str | None,
    timeout_seconds: int,
    run_capture_func: RunCaptureFunc,
) -> tuple[dict[str, str], str]:
    return load_pipeline_name_previews_for_service(
        service,
        paths,
        media_kind="TV",
        powershell_host=powershell_host,
        timeout_seconds=timeout_seconds,
        run_capture_func=run_capture_func,
    )


__all__ = [
    "CapturedCommandResult",
    "load_pipeline_movie_name_previews_for_service",
    "load_pipeline_name_previews_for_service",
    "load_pipeline_tv_name_previews_for_service",
    "naming_preview_script_path_for_service",
]
