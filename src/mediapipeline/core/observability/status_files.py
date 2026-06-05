from __future__ import annotations

from pathlib import Path

from mediapipeline.desktop.models import ResolvedPaths


def latest_matching_file(folder: Path | None, pattern: str) -> Path | None:
    if not folder or not folder.exists():
        return None
    selected: Path | None = None
    selected_mtime = float("-inf")
    try:
        items = list(folder.glob(pattern))
    except OSError:
        return None
    for item in items:
        try:
            mtime = item.stat().st_mtime
        except OSError:
            continue
        if mtime > selected_mtime:
            selected = item
            selected_mtime = mtime
    return selected


def latest_audit_csv(resolved: ResolvedPaths, priority_only: bool) -> Path | None:
    folder = resolved.audit_reports_path
    if not folder or not folder.exists():
        return None
    selected: Path | None = None
    selected_mtime = float("-inf")
    try:
        items = list(folder.glob("audit_summary_*.csv"))
    except OSError:
        return None
    for item in items:
        is_priority_file = item.name.endswith(".priority.csv")
        if is_priority_file != priority_only:
            continue
        try:
            mtime = item.stat().st_mtime
        except OSError:
            continue
        if mtime > selected_mtime:
            selected = item
            selected_mtime = mtime
    return selected


def latest_failure_json(resolved: ResolvedPaths) -> Path | None:
    return latest_matching_file(resolved.failed_reports_path, "round_failures_*.json")
