from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .service_status_presentation import pipeline_event_data
from .service_utils import _read_json_file


def format_recent_error_summary(
    resolved: object,
    pipeline_events: list[dict[str, Any]],
    log_tail: str,
    latest_failure_json: Path | None,
    *,
    max_items: int = 8,
) -> list[str]:
    rows: list[str] = []
    for event in reversed(pipeline_events):
        data = pipeline_event_data(event)
        status = str(event.get("status") or "").strip().lower()
        event_type = str(event.get("event_type") or "").strip()
        error_code = str(data.get("error_code") or event.get("error_code") or "").strip()
        error_text = str(data.get("error") or data.get("reason") or event.get("error") or "").strip()
        if not (status in {"error", "failed", "failure"} or "failure" in event_type.lower() or error_code or error_text):
            continue
        stage = str(event.get("stage") or data.get("stage") or "").strip()
        source_path = str(event.get("source_path") or data.get("source_path") or "").strip()
        parts = [part for part in (event_type, status, stage, error_code) if part]
        label = " | ".join(parts) if parts else "pipeline error"
        if source_path:
            label = f"{label} | {Path(source_path).name}"
        if error_text:
            label = f"{label} | {error_text}"
        rows.append(label)
        if len(rows) >= max_items:
            return rows

    if latest_failure_json and latest_failure_json.exists():
        try:
            raw = _read_json_file(latest_failure_json)
            if isinstance(raw, list):
                for item in reversed(raw[-max_items:]):
                    if not isinstance(item, dict):
                        continue
                    code = str(item.get("ErrorCode") or "").strip()
                    stage = str(item.get("Stage") or "").strip()
                    reason = str(item.get("Reason") or "").strip()
                    source = str(item.get("SourcePath") or "").strip()
                    label = " | ".join(
                        part
                        for part in (code or "failure", stage, Path(source).name if source else "", reason)
                        if part
                    )
                    rows.append(label)
                    if len(rows) >= max_items:
                        return rows
        except Exception as exc:
            rows.append(f"Latest failure JSON unreadable: {exc}")

    for line in reversed(str(log_tail or "").splitlines()):
        text = line.strip()
        if not text:
            continue
        if re.search(r"\b(ERROR|FATAL)\b", text, flags=re.IGNORECASE):
            rows.append(text)
            if len(rows) >= max_items:
                break

    _ = resolved
    return rows or ["No recent pipeline errors found in events, failure JSON, or log tail."]
