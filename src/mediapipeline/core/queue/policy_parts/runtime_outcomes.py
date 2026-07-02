"""Queue runtime outcome application helpers."""

from __future__ import annotations

from typing import Any
from collections.abc import Iterable

from mediapipeline.core.observability.runtime_outcomes import runtime_outcome_index, source_identity_key

from .operator_guidance import queue_row_operator_guidance

def queue_apply_runtime_outcomes(rows: list[dict[str, Any]], events: Iterable[Any]) -> list[dict[str, Any]]:
    outcome_index = runtime_outcome_index(events)
    if not outcome_index:
        return rows
    for row in rows:
        source_key = source_identity_key(row.get("source_path"))
        if not source_key:
            continue
        outcome = outcome_index.get(source_key)
        if outcome is None:
            continue
        row.update(outcome)
        row.update(queue_row_operator_guidance(row))
    return rows
