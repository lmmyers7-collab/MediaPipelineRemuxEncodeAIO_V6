from __future__ import annotations

import json
import logging
from pathlib import Path

from mediapipeline_desktop_app.models import CompletedJobRecord


def completed_sidecar_path_from_payload(manifest_path: Path, payload: dict) -> Path:
    output_path_str = payload.get("output_path")
    if output_path_str:
        op = Path(str(output_path_str))
        return op.with_suffix(".pipeline.json")
    return manifest_path


def annotate_completed_output_health(record: CompletedJobRecord) -> None:
    payload = record.payload
    try:
        output_exists = record.output_path.exists()
    except Exception as exc:
        output_exists = False
        payload["_diagnostics_output_health"] = f"output existence check failed: {exc}"
    else:
        payload["_diagnostics_output_health"] = "ok" if output_exists else "completed metadata without media"
    payload["_diagnostics_output_exists"] = bool(output_exists)


def read_completed_manifest_records(
    manifest_path: Path,
    *,
    limit: int | None,
    logger: logging.Logger,
) -> list[CompletedJobRecord]:
    raw = manifest_path.read_text(encoding="utf-8", errors="replace")
    parsed: list[CompletedJobRecord] = []
    for line_no, line in enumerate(raw.splitlines(), start=1):
        line = line.strip().lstrip("\ufeff")
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            logger.warning("Skipping malformed manifest line %d in %s", line_no, manifest_path)
            continue
        if not isinstance(payload, dict):
            continue
        sidecar_path = completed_sidecar_path_from_payload(manifest_path, payload)
        record = CompletedJobRecord(sidecar_path=sidecar_path, payload=payload)
        annotate_completed_output_health(record)
        parsed.append(record)
    parsed.reverse()
    if limit is None:
        return parsed
    return parsed[:limit]
