from __future__ import annotations

import os
import shlex
import subprocess
from datetime import datetime
from pathlib import Path


def _release_label(workspace_root: Path) -> str:
    version_file = workspace_root / "ops" / "release" / "metadata" / "VERSION"
    if version_file.is_file():
        label = version_file.read_text(encoding="utf-8").strip()
        if label:
            return label
    return "local"


def default_release_destination(workspace_root: Path, *, now: datetime | None = None) -> Path:
    stamp = (now or datetime.now()).strftime("%Y%m%d_%H%M%S")
    label = _release_label(workspace_root)
    return workspace_root.parent / f"MediaPipelineRemuxEncodeAIO_{label}_Portable_{stamp}"


def resolve_release_destination(
    workspace_root: Path,
    destination_root: Path | str | None,
    *,
    now: datetime | None = None,
) -> Path:
    raw_destination = str(destination_root or "").strip()
    if raw_destination:
        return Path(raw_destination).expanduser()
    return default_release_destination(workspace_root, now=now)


def build_release_command_args(
    *,
    powershell_host: str,
    builder: Path,
    destination: Path,
    zip_package: bool,
    verify: bool,
    include_tests: bool,
    include_dev_docs: bool,
    include_optional_tools: bool,
    include_tool_docs: bool,
    keep_personal_config: bool,
    force: bool,
    dry_run: bool,
    include_tauri_preview_binary: bool = False,
) -> list[str]:
    args = [
        powershell_host,
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(builder),
        "-DestinationRoot",
        str(destination),
    ]
    if force:
        args.append("-Force")
    if zip_package:
        args.append("-Zip")
    if verify:
        args.append("-Verify")
    if include_tests:
        args.append("-IncludeTests")
    if include_dev_docs:
        args.append("-IncludeDevDocs")
    if include_optional_tools:
        args.append("-IncludeOptionalTools")
    if include_tool_docs:
        args.append("-IncludeToolDocs")
    if include_tauri_preview_binary:
        args.append("-IncludeTauriPreviewBinary")
    if keep_personal_config:
        args.append("-KeepPersonalConfig")
    if dry_run:
        args.append("-DryRun")
    return args


def release_command_line(args: list[str]) -> str:
    return subprocess.list2cmdline(args) if os.name == "nt" else " ".join(shlex.quote(str(arg)) for arg in args)


def release_artifact_paths(destination: Path) -> tuple[Path, Path]:
    manifest_path = destination / "release_manifest.json"
    zip_path = Path(str(destination).rstrip("\\/") + ".zip")
    return manifest_path, zip_path
