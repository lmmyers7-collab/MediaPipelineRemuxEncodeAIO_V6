from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Protocol

from mediapipeline_desktop_app.subprocess_runner import CapturedCommandResult, KillTreeCallback


class WarningLogger(Protocol):
    def warning(self, message: object, *args: object, **kwargs: object) -> None: ...


class ExceptionWarningLogger(WarningLogger, Protocol):
    def exception(self, message: object, *args: object, **kwargs: object) -> None: ...


class RunCaptureFunc(Protocol):
    def __call__(
        self,
        args: Sequence[str],
        *,
        timeout_seconds: float,
        cwd: str | Path | None = None,
        env: Mapping[str, str] | None = None,
        extra_popen_kwargs: Mapping[str, Any] | None = None,
        encoding: str | None = None,
        errors: str | None = None,
        hidden: bool = True,
        label: str = "process",
        kill_tree: KillTreeCallback | None = None,
    ) -> CapturedCommandResult: ...


class PowerShellHostServiceProtocol(Protocol):
    app_root: Path
    workspace_root: Path


class RenamePreviewScriptServiceProtocol(PowerShellHostServiceProtocol, Protocol):
    pass


class RenamePreviewLoadServiceProtocol(Protocol):
    logger: WarningLogger

    def _naming_preview_script_path(self) -> Path | None: ...
    def _subprocess_kwargs_hidden(self) -> Mapping[str, Any]: ...


class RenamePlannerServiceProtocol(Protocol):
    def parse_rename_number(
        self,
        raw: str | int,
        *,
        label: str,
        prefix_pattern: str,
        minimum: int,
        maximum: int,
    ) -> int: ...
    def _movie_filter_options_are_default(self, options: dict[str, bool] | None) -> bool: ...
    def _load_pipeline_movie_name_previews(
        self,
        paths: list[Path],
        *,
        powershell_host: str | None = None,
    ) -> tuple[dict[str, str], str]: ...
    def _load_pipeline_tv_name_previews(
        self,
        paths: list[Path],
        *,
        powershell_host: str | None = None,
    ) -> tuple[dict[str, str], str]: ...
    def _casefold_path(self, path: Path) -> str: ...
    def normalize_plex_filename_component(self, value: str, remove_terms: list[str] | None = None) -> str: ...
    def _apply_tv_episode_title_template(self, file_name: str, *, include_episode_title: bool) -> str: ...
    def _build_tv_rename_name(
        self,
        source: Path,
        *,
        show_name: str,
        season_number: int,
        episode_number: int,
        remove_terms: list[str] | None,
        include_episode_title: bool,
    ) -> str: ...
    def _build_auto_tv_rename_name(
        self,
        source: Path,
        *,
        season_number: int,
        remove_terms: list[str] | None,
        include_episode_title: bool,
    ) -> str: ...
    def _clean_pipeline_movie_name(
        self,
        file_name: str,
        remove_terms: list[str] | None,
        movie_filter_options: dict[str, bool] | None,
        movie_filter_terms: dict[str, list[str]] | None = None,
    ) -> str: ...
    def _build_movie_rename_name(
        self,
        source: Path,
        *,
        movie_title: str,
        movie_year: str,
        remove_terms: list[str] | None,
        movie_filter_options: dict[str, bool] | None,
        movie_filter_terms: dict[str, list[str]] | None = None,
    ) -> str: ...
    def _normalise_manual_final_name(self, source: Path, manual_name: str) -> str: ...
    def _resolve_same_file(self, left: Path, right: Path) -> bool: ...
    def _plan_sidecar_moves(self, source: Path, destination: Path) -> list[dict[str, str]]: ...


class RenameApplyServiceProtocol(Protocol):
    logger: ExceptionWarningLogger

    def _build_rename_operations(self, plan: list[dict[str, Any]]) -> list[dict[str, Any]]: ...
    def _write_rename_undo_manifest(self, manifest: dict[str, Any], *, root: Path | None = None) -> Path: ...
    def _rename_path_case_safe(self, source: Path, destination: Path) -> None: ...
    def _resolve_same_file(self, left: Path, right: Path) -> bool: ...
    def _pipeline_sidecar_paths_for_destination(self, destination: Path) -> list[Path]: ...
    def _update_pipeline_sidecar_after_rename(self, path: Path, payload: dict[str, Any], destination: Path) -> None: ...
    def rename_override_sidecar_path(self, destination: Path) -> Path: ...
    def _update_rename_sidecar_metadata(self, path: Path, payload: dict[str, Any]) -> None: ...
    def _rollback_rename_operations(self, operations: list[dict[str, Path | str]]) -> list[str]: ...
