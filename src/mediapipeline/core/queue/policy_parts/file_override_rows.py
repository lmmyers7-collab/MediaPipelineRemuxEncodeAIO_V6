"""Queue file-override artifact annotation helpers."""

from __future__ import annotations

from typing import Any, Mapping

from mediapipeline.core.queue.file_overrides import FILE_OVERRIDE_BATCH_METADATA_KEY, resolve_file_override_match

from .row_identity import _queue_normalized_path_key

def _queue_file_override_artifact_row(row: Mapping[str, Any]) -> bool:
    values = (
        row.get("source_path"),
        row.get("relative_path"),
        row.get("display_name"),
        row.get("name"),
    )
    for value in values:
        key = _queue_normalized_path_key(value)
        if key.endswith(".override.json") or key.endswith("/override.json") or key == "override.json":
            return True
    return False

def _annotate_queue_file_override(
    row: dict[str, Any],
    file_override_manifest: Mapping[str, Any] | None,
) -> None:
    if file_override_manifest is None or _queue_file_override_artifact_row(row):
        return
    source_path = str(row.get("source_path") or "").strip()
    if not source_path:
        row["has_file_override"] = False
        return
    match = resolve_file_override_match(dict(file_override_manifest), source_path)
    entry = match.get("entry")
    row["has_file_override"] = isinstance(entry, dict)
    if not row["has_file_override"]:
        return
    row["file_override_path"] = str(match.get("matched_path") or "")
    row["file_override_scope"] = str(match.get("scope") or "")
    batch = entry.get(FILE_OVERRIDE_BATCH_METADATA_KEY) if isinstance(entry, Mapping) else None
    if isinstance(batch, Mapping):
        row["file_override_origin"] = str(batch.get("origin") or "")
        row["file_override_batch_id"] = str(batch.get("batch_id") or "")
        row["file_override_batch_label"] = str(batch.get("batch_label") or "")
        row["file_override_batch_scope"] = str(batch.get("batch_scope") or "")
