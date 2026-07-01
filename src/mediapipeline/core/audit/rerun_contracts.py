from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Protocol

from mediapipeline.core.paths.contracts import ResolvedPaths
from mediapipeline.core.kernel.runtime.subprocess_runner import CapturedCommandResult, KillTreeCallback


class RerunWarningLogger(Protocol):
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


class RerunMetadataServiceProtocol(Protocol):
    app_root: Path
    workspace_root: Path
    logger: RerunWarningLogger

    def _build_launch_environment(self) -> Mapping[str, str]: ...
    def _first_existing(self, *paths: Path) -> Path: ...
    def _rerun_source_metadata_script_path(self, resolved: ResolvedPaths) -> Path: ...
    def _subprocess_kwargs_hidden(self) -> Mapping[str, Any]: ...


class RerunCsvExportServiceProtocol(Protocol):
    def _load_rerun_source_metadata(
        self,
        resolved: ResolvedPaths,
        source_paths: list[Path],
    ) -> dict[str, dict[str, Any]]: ...
