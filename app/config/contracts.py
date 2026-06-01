from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Protocol

from mediapipeline_desktop_app.models_core import ConfigSaveResult
from mediapipeline_desktop_app.subprocess_runner import CapturedCommandResult, KillTreeCallback


class WarningLogger(Protocol):
    def warning(self, message: object, *args: object, **kwargs: object) -> None: ...


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


class ConfigDocumentServiceProtocol(Protocol):
    logger: WarningLogger

    def _subprocess_kwargs_hidden(self) -> Mapping[str, Any]: ...
    def resolve_powershell_host(self) -> str | None: ...
    def validate_config_values(self, values: dict[str, Any]) -> tuple[list[str], list[str]]: ...


class ConfigSaveServiceProtocol(Protocol):
    logger: WarningLogger

    def _config_backup_path(self, output_path: Path) -> Path: ...
    def config_profile_path(self, config_path: Path, profile_name: str) -> tuple[str, Path]: ...
    def config_profiles_dir(self, config_path: Path) -> Path: ...
    def load_config_data(self, config_path: Path, powershell_host: str | None) -> dict[str, Any]: ...
    def normalize_profile_name(self, raw_name: str) -> str: ...
    def save_config_document(
        self,
        output_path: Path,
        document_text: str,
        create_backup: bool,
        *,
        config_values: dict[str, Any] | None = None,
        powershell_host: str | None = None,
    ) -> ConfigSaveResult: ...
    def validate_config_document_for_save(
        self,
        document_text: str,
        *,
        config_values: dict[str, Any] | None = None,
        powershell_host: str | None = None,
    ) -> tuple[list[str], list[str]]: ...
