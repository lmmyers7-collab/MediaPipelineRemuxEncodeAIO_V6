from __future__ import annotations

import json
import os
from pathlib import Path
import re
from typing import Any

from mediapipeline.core.paths.contracts import ResolvedPaths


_AUDIT_REPORT_STAMP_RE = re.compile(r"^audit_summary_(?P<stamp>\d{8}(?:_\d{6})?)(?:\.priority)?\.csv$", re.IGNORECASE)


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


def _path_is_inside(child: Path, parent: Path) -> bool:
    try:
        child_text = os.path.normcase(os.path.abspath(str(child)))
        parent_text = os.path.normcase(os.path.abspath(str(parent)))
        return os.path.commonpath([child_text, parent_text]) == parent_text
    except (OSError, ValueError):
        return False


def _audit_progress_payload(folder: Path) -> dict[str, Any]:
    progress_path = folder / "audit_progress.json"
    try:
        payload = json.loads(progress_path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _latest_audit_csv_from_progress(folder: Path, priority_only: bool) -> Path | None:
    payload = _audit_progress_payload(folder)
    completed = payload.get("completed") is True or str(payload.get("status") or "").strip().casefold() in {"complete", "completed"}
    failed = payload.get("failed") is True
    if not completed or failed:
        return None
    key = "latest_priority_csv_path" if priority_only else "latest_csv_path"
    raw_path = str(payload.get(key) or "").strip()
    if not raw_path:
        return None
    candidate = Path(raw_path)
    if not candidate.is_absolute():
        candidate = folder / candidate
    try:
        candidate = candidate.resolve(strict=False)
    except OSError:
        return None
    if not _path_is_inside(candidate, folder):
        return None
    if candidate.name.endswith(".priority.csv") != priority_only:
        return None
    if not candidate.name.lower().startswith("audit_summary_") or candidate.suffix.lower() != ".csv":
        return None
    try:
        if not candidate.exists() or not candidate.is_file():
            return None
    except OSError:
        return None
    return candidate


def _audit_report_sort_key(item: Path) -> tuple[str, float]:
    try:
        mtime = item.stat().st_mtime
    except OSError:
        return "", float("-inf")
    match = _AUDIT_REPORT_STAMP_RE.match(item.name)
    if match:
        return match.group("stamp"), mtime
    return "", mtime


def latest_audit_csv(resolved: ResolvedPaths, priority_only: bool) -> Path | None:
    folder = resolved.audit_reports_path
    if not folder or not folder.exists():
        return None
    progress_csv = _latest_audit_csv_from_progress(folder, priority_only)
    if progress_csv is not None:
        return progress_csv
    selected: Path | None = None
    selected_key: tuple[str, float] = ("", float("-inf"))
    try:
        items = list(folder.glob("audit_summary_*.csv"))
    except OSError:
        return None
    for item in items:
        is_priority_file = item.name.endswith(".priority.csv")
        if is_priority_file != priority_only:
            continue
        sort_key = _audit_report_sort_key(item)
        if sort_key[1] == float("-inf"):
            continue
        if sort_key > selected_key:
            selected = item
            selected_key = sort_key
    return selected


def latest_failure_json(resolved: ResolvedPaths) -> Path | None:
    return latest_matching_file(resolved.failed_reports_path, "round_failures_*.json")
