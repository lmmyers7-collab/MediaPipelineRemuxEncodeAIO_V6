from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any

from mediapipeline.core.paths.contracts import ResolvedPaths
from mediapipeline.core.status.summary_sections import (
    append_audit_progress_section,
    append_control_flag_states,
    append_environment_section,
    append_latest_path_section,
    append_plain_section,
    append_progress_section,
)


def build_status_summary(
    *,
    resolved: ResolvedPaths,
    progress: dict[str, Any] | None,
    audit_progress: dict[str, Any] | None,
    audit_root: str,
    latest_failure_report: Path | None,
    latest_failure_json: Path | None,
    latest_audit_csv: Path | None,
    latest_priority_csv: Path | None,
    active_jobs: Sequence[str] = (),
    recent_errors: Sequence[str] = (),
    event_summary: Sequence[str] = (),
    progress_is_stale: bool = False,
    audit_progress_is_stale: bool = False,
) -> str:
    lines: list[str] = []
    append_environment_section(lines, resolved=resolved, audit_root=audit_root)
    append_control_flag_states(lines, resolved=resolved)
    append_plain_section(lines, "Active jobs", "-----------", active_jobs)
    append_progress_section(lines, progress=progress, progress_is_stale=progress_is_stale)
    append_audit_progress_section(
        lines,
        audit_progress=audit_progress,
        audit_progress_is_stale=audit_progress_is_stale,
    )
    append_plain_section(lines, "Recent errors", "-------------", recent_errors)
    append_plain_section(lines, "Recent pipeline events", "----------------------", event_summary)
    append_latest_path_section(lines, "Latest failure report", "---------------------", latest_failure_report)
    append_latest_path_section(lines, "Latest failure JSON", "-------------------", latest_failure_json)
    append_latest_path_section(lines, "Latest audit CSV", "----------------", latest_audit_csv)
    append_latest_path_section(lines, "Latest priority audit CSV", "-------------------------", latest_priority_csv)

    return "\n".join(lines)
