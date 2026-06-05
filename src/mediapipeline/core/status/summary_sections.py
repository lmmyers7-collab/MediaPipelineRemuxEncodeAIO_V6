from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any

from mediapipeline.desktop.models import ResolvedPaths


def append_environment_section(lines: list[str], *, resolved: ResolvedPaths, audit_root: str) -> None:
    lines.append(f"Pipeline path    : {resolved.pipeline_path}")
    lines.append(f"Config path      : {resolved.config_path}")
    lines.append(f"Audit script     : {resolved.audit_script_path}")
    lines.append(f"PowerShell host  : {resolved.powershell_host or '(not found)'}")
    lines.append(f"LocalBase        : {resolved.local_base or '(not loaded)'}")
    lines.append(f"SourceMovies     : {resolved.source_movies or '(not loaded)'}")
    lines.append(f"SourceTV         : {resolved.source_tv or '(not loaded)'}")
    lines.append(f"Audit root       : {audit_root or '(not set)'}")
    lines.append(f"Audit reports    : {resolved.audit_reports_path or '(not resolved)'}")
    lines.append(f"Priority markers : {', '.join(resolved.priority_markers)}")


def append_control_flag_states(lines: list[str], *, resolved: ResolvedPaths) -> None:
    for label, path in (
        ("Pause flag", resolved.pause_flag),
        ("Stop flag", resolved.stop_flag),
        ("Rescan flag", resolved.rescan_flag),
    ):
        if path:
            state = "present" if path.exists() else "clear"
            lines.append(f"{label:<16}: {state}")


def append_plain_section(lines: list[str], title: str, underline: str, values: Sequence[str]) -> None:
    if not values:
        return
    lines.extend(["", title, underline])
    lines.extend(values)


def append_progress_section(lines: list[str], *, progress: dict[str, Any] | None, progress_is_stale: bool) -> None:
    if not progress:
        return
    lines.extend(
        [
            "",
            "Progress",
            "--------",
            f"Version          : {progress.get('ProgressVersion', '')}",
            f"Last update      : {progress.get('LastUpdate', '')}",
            f"Status           : {progress.get('Status', '')}",
            f"Stage            : {progress.get('CurrentStage', '')}",
            f"Stage percent    : {progress.get('CurrentStagePercent', '')}",
            f"Route            : {progress.get('CurrentRoute', '')}",
            f"Queue phase      : {progress.get('CurrentQueuePhase', '')}",
            f"Queue position   : {progress.get('CurrentQueueIndex', '')} / {progress.get('CurrentQueueTotal', '')}",
            f"Current file     : {progress.get('CurrentFile', '')}",
            f"Current path     : {progress.get('CurrentFilePath', '')}",
            f"Processed        : {progress.get('TotalProcessed', '')}",
            f"Encoded          : {progress.get('Encoded', '')}",
            f"Remuxed          : {progress.get('Remuxed', '')}",
            f"Failed           : {progress.get('Failed', '')}",
            f"Movies           : {progress.get('Movies', '')}",
            f"TV episodes      : {progress.get('TVEpisodes', '')}",
        ]
    )
    if progress_is_stale:
        lines.append("Progress health  : STALE - pipeline_progress.json is not updating.")


def append_audit_progress_section(
    lines: list[str],
    *,
    audit_progress: dict[str, Any] | None,
    audit_progress_is_stale: bool,
) -> None:
    if not audit_progress:
        return
    lines.extend(
        [
            "",
            "Audit progress",
            "--------------",
            f"Last update      : {audit_progress.get('last_update', '')}",
            f"Status           : {audit_progress.get('status', '')}",
            f"Processed        : {audit_progress.get('processed_files', '')} / {audit_progress.get('total_files', '')}",
            f"Current file     : {audit_progress.get('current_file', '')}",
            f"Current operation: {audit_progress.get('current_operation', '')}",
            f"Progress health  : {'healthy' if audit_progress.get('progress_persistence_healthy', True) else 'write failures'}",
        ]
    )
    if audit_progress_is_stale:
        lines.append("Audit health     : STALE - audit_progress.json is not updating.")


def append_latest_path_section(lines: list[str], title: str, underline: str, path: Path | None) -> None:
    if path:
        lines.extend(["", title, underline, str(path)])
