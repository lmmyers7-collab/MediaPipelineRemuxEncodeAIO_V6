from __future__ import annotations

from pathlib import Path
from typing import Any

from mediapipeline_desktop_app.contracts import ContractError, PipelineEvent, ProgressState
from app.shared.protocols import WarningLogger
from app.shared.utils import _read_json_file, _tail_jsonl_file, _tail_text_file


def _warning(logger: WarningLogger | None, message: str, *args: object) -> None:
    if logger is not None:
        logger.warning(message, *args)


def read_progress_file(progress_file: Path | None, logger: WarningLogger | None = None) -> dict[str, Any] | None:
    if not progress_file or not progress_file.exists():
        return None
    try:
        payload = _read_json_file(progress_file)
        return ProgressState.from_mapping(payload).to_mapping()
    except ContractError as exc:
        _warning(logger, "Progress contract invalid for %s: %s", progress_file, exc)
        return None
    except Exception as exc:
        _warning(logger, "Progress read failed for %s: %s", progress_file, exc)
        return None


def read_audit_progress_file(audit_reports_path: Path | None, logger: WarningLogger | None = None) -> dict[str, Any] | None:
    if not audit_reports_path:
        return None
    progress_path = audit_reports_path / "audit_progress.json"
    if not progress_path.exists():
        return None
    try:
        return _read_json_file(progress_path)
    except Exception as exc:
        _warning(logger, "Audit progress read failed for %s: %s", progress_path, exc)
        return None


def read_log_tail_file(log_file: Path | None, line_count: int = 150) -> str:
    if not log_file or not log_file.exists():
        return "No pipeline_debug.log found yet."
    try:
        text = _tail_text_file(log_file, line_count=line_count, encoding="utf-8")
    except Exception as exc:
        return f"Failed to read log tail.\n{exc}"
    return text if text else "(log is empty)"


def read_pipeline_events_tail_file(
    event_file: Path | None,
    line_count: int = 100,
    logger: WarningLogger | None = None,
) -> list[dict[str, Any]]:
    if not event_file or not event_file.exists():
        return []
    try:
        raw_events = _tail_jsonl_file(event_file, line_count=line_count, encoding="utf-8")
        events: list[dict[str, Any]] = []
        invalid_count = 0
        for raw_event in raw_events:
            try:
                events.append(PipelineEvent.from_mapping(raw_event).to_mapping())
            except ContractError:
                invalid_count += 1
        if invalid_count:
            _warning(logger, "Skipped %s invalid pipeline event record(s) in %s.", invalid_count, event_file)
        return events
    except Exception as exc:
        _warning(logger, "Pipeline event read failed for %s: %s", event_file, exc)
        return []
