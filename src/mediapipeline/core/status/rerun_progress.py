from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any

from mediapipeline.core.paths.contracts import ResolvedPaths
from mediapipeline.core.status.active_jobs import active_job_detail_rows
from mediapipeline.core.status.progress import is_progress_stale
from mediapipeline.core.status.readers import read_log_tail_file, read_pipeline_events_tail_file, read_progress_file


@dataclass(frozen=True)
class RerunProgressOverlay:
    progress: dict[str, Any]
    pipeline_events: list[dict[str, Any]]
    log_tail: str


def _text_from_mapping(mapping: Mapping[str, Any], *keys: str) -> str:
    for key in keys:
        value = mapping.get(key)
        if value not in (None, ""):
            return str(value).strip()
    return ""


def _metadata(row: Mapping[str, Any]) -> Mapping[str, Any]:
    value = row.get("metadata")
    return value if isinstance(value, Mapping) else {}


def _row_is_active_rerun(row: Mapping[str, Any]) -> bool:
    if _text_from_mapping(row, "job_kind").casefold() != "rerun_csv":
        return False
    if _text_from_mapping(row, "completed_at"):
        return False
    if row.get("return_code") is not None:
        return False
    status_state = _text_from_mapping(row, "status_state").casefold()
    return status_state in {"running", "warning"}


def _launch_rerun_prefix(row: Mapping[str, Any]) -> str:
    launch_id = _text_from_mapping(row, "launch_id", "record_file")
    match = re.match(r"^(?P<date>\d{8})_(?P<time>\d{6})_", launch_id)
    if not match:
        return ""
    return f"rerun_{match.group('date')}_{match.group('time')}_"


def _operator_local_base(resolved: ResolvedPaths) -> Path | None:
    if resolved.local_base is not None:
        return Path(resolved.local_base)
    if resolved.state_root is not None:
        state_root = Path(resolved.state_root)
        if state_root.name.casefold() == "state":
            return state_root.parent
    return None


def _rerun_workspace_root(resolved: ResolvedPaths) -> Path | None:
    local_base = _operator_local_base(resolved)
    if local_base is None:
        return None
    return local_base.parent / f"{local_base.name}_RerunWorkspace"


def _direct_child_root(path: Path) -> Path | None:
    progress_file = path / "State" / "Progress" / "pipeline_progress.json"
    return path if progress_file.exists() else None


def _matching_runtime_children(runtime_state_root: Path, prefix: str) -> list[Path]:
    if not runtime_state_root.exists() or not runtime_state_root.is_dir():
        return []
    pattern = f"{prefix}*" if prefix else "rerun_*"
    try:
        children = [
            child
            for child in runtime_state_root.glob(pattern)
            if child.is_dir() and (child / "State" / "Progress" / "pipeline_progress.json").exists()
        ]
    except OSError:
        return []
    return sorted(children, key=lambda child: child.stat().st_mtime, reverse=True)


def _candidate_child_roots(row: Mapping[str, Any], resolved: ResolvedPaths) -> list[Path]:
    candidates: list[Path] = []
    seen: set[str] = set()
    prefix = _launch_rerun_prefix(row)
    metadata = _metadata(row)

    def add(path: Path) -> None:
        key = str(path.resolve()) if path.exists() else str(path)
        if key not in seen:
            seen.add(key)
            candidates.append(path)

    for key in ("nested_pipeline_local_base", "child_local_base"):
        raw = _text_from_mapping(metadata, key) or _text_from_mapping(row, key)
        if raw:
            direct = _direct_child_root(Path(raw))
            if direct is not None:
                add(direct)

    for key in ("runtime_state_root",):
        raw = _text_from_mapping(metadata, key) or _text_from_mapping(row, key)
        if raw:
            runtime_root = Path(raw)
            direct = _direct_child_root(runtime_root)
            if direct is not None:
                add(direct)
            for child in _matching_runtime_children(runtime_root, prefix):
                add(child)

    workspace_raw = _text_from_mapping(metadata, "rerun_workspace_root") or _text_from_mapping(row, "rerun_workspace_root")
    workspace_roots = [Path(workspace_raw)] if workspace_raw else []
    workspace_root = _rerun_workspace_root(resolved)
    if workspace_root is not None:
        workspace_roots.append(workspace_root)

    for workspace in workspace_roots:
        direct = _direct_child_root(workspace)
        if direct is not None:
            add(direct)
        for child in _matching_runtime_children(workspace / "RuntimeState", prefix):
            add(child)

    return candidates


def _has_current_item(progress: Mapping[str, Any]) -> bool:
    for key in ("CurrentFilePath", "CurrentFileDisplay", "CurrentFile"):
        text = _text_from_mapping(progress, key)
        if text and text.casefold() not in {"none", "null", "idle", "n/a"}:
            return True
    return False


def _child_log_tail(child_root: Path) -> str:
    log_file = child_root / "pipeline_debug.log"
    if not log_file.exists():
        return ""
    return read_log_tail_file(log_file)


def _read_child_overlay(
    row: Mapping[str, Any],
    child_root: Path,
    *,
    fallback_log_tail: str,
    logger: Any,
    stale_check: Callable[[dict[str, Any] | None], bool],
) -> RerunProgressOverlay | None:
    progress_file = child_root / "State" / "Progress" / "pipeline_progress.json"
    progress = read_progress_file(progress_file, logger)
    if not progress or stale_check(progress) or not _has_current_item(progress):
        return None

    launch_id = _text_from_mapping(row, "launch_id", "record_file")
    enriched = dict(progress)
    enriched["ActiveJobKind"] = "rerun_csv"
    enriched["RerunParentLaunchId"] = launch_id
    enriched["RerunChildLocalBase"] = str(child_root)
    enriched["RerunProgressFile"] = str(progress_file)
    enriched["ProgressSource"] = "rerun_child_pipeline_progress"

    event_file = child_root / "State" / "Progress" / "pipeline_events.jsonl"
    pipeline_events = read_pipeline_events_tail_file(event_file, logger=logger)
    log_tail = _child_log_tail(child_root) or fallback_log_tail
    return RerunProgressOverlay(progress=enriched, pipeline_events=pipeline_events, log_tail=log_tail)


def active_rerun_progress_overlay(
    resolved: ResolvedPaths,
    *,
    fallback_log_tail: str,
    logger: Any,
    stale_check: Callable[[dict[str, Any] | None], bool] = is_progress_stale,
) -> RerunProgressOverlay | None:
    for row in active_job_detail_rows(resolved.active_jobs_path):
        if not _row_is_active_rerun(row):
            continue
        for child_root in _candidate_child_roots(row, resolved):
            overlay = _read_child_overlay(
                row,
                child_root,
                fallback_log_tail=fallback_log_tail,
                logger=logger,
                stale_check=stale_check,
            )
            if overlay is not None:
                return overlay
    return None


__all__ = ["RerunProgressOverlay", "active_rerun_progress_overlay"]
