from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from .service_release_plan import (
    build_release_command_args,
    default_release_destination,
    release_artifact_paths,
    release_command_line,
    resolve_release_destination,
)
from .service_release_result import release_result_payload
from .service_utils import _read_json_file
from .subprocess_runner import run_capture


class ReleasePackageServiceMixin:
    def default_release_builder_path(self) -> Path:
        return self._first_existing(
            self.workspace_root / "Build-MediaPipelineRemuxEncodeAIO-Release.ps1",
            self.app_root / "Build-MediaPipelineRemuxEncodeAIO-Release.ps1",
        )

    def default_release_destination(self) -> Path:
        return default_release_destination(self.workspace_root)

    def build_release_package(
        self,
        *,
        destination_root: Path | str | None,
        zip_package: bool,
        verify: bool,
        include_tests: bool,
        include_dev_docs: bool,
        include_optional_tools: bool,
        include_tool_docs: bool,
        keep_personal_config: bool,
        force: bool,
        dry_run: bool,
        timeout_seconds: int = 7200,
    ) -> dict[str, Any]:
        powershell_host = self.resolve_powershell_host()
        if not powershell_host:
            raise RuntimeError("PowerShell host could not be resolved.")
        builder = self.default_release_builder_path()
        if not builder.exists():
            raise FileNotFoundError(f"Release builder not found: {builder}")

        destination = resolve_release_destination(self.workspace_root, destination_root)
        args = build_release_command_args(
            powershell_host=powershell_host,
            builder=builder,
            destination=destination,
            zip_package=zip_package,
            verify=verify,
            include_tests=include_tests,
            include_dev_docs=include_dev_docs,
            include_optional_tools=include_optional_tools,
            include_tool_docs=include_tool_docs,
            keep_personal_config=keep_personal_config,
            force=force,
            dry_run=dry_run,
        )

        command_line = release_command_line(args)
        self.logger.info("Release build requested: %s", command_line)
        started = time.monotonic()
        result = run_capture(
            args,
            cwd=str(self.workspace_root),
            env=self._build_launch_environment(),
            encoding="utf-8",
            errors="replace",
            timeout_seconds=max(30, int(timeout_seconds)),
            extra_popen_kwargs=self._subprocess_kwargs_hidden(),
            label="release build",
            kill_tree=getattr(self, "kill_process_tree", None),
        )

        manifest_path, zip_path = release_artifact_paths(destination)
        manifest: Any | None = None
        if manifest_path.exists():
            try:
                manifest = _read_json_file(manifest_path)
            except Exception as exc:
                self.logger.warning("Release manifest read failed: %s", exc)
                manifest = None

        return release_result_payload(
            result=result,
            command_line=command_line,
            destination=destination,
            manifest_path=manifest_path,
            zip_path=zip_path,
            dry_run=dry_run,
            elapsed_seconds=time.monotonic() - started,
            manifest=manifest,
        )

    def _stringify_process_output(self, value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, bytes):
            return value.decode("utf-8", errors="replace")
        return str(value)
