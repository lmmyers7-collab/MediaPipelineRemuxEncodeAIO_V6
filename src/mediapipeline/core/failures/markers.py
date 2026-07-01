from __future__ import annotations

from pathlib import Path
from typing import Any

from mediapipeline.core.failures.contracts import FailureRecord

FAILURE_MARKER_KEY_MAP = {
    "source_full_path": "SourcePath",
    "stage": "Stage",
    "reason": "Reason",
    "classification": "Classification",
    "error_code": "ErrorCode",
    "artifact_path": "ArtifactPath",
    "recorded_at": "RecordedAt",
    "suggested_action": "SuggestedAction",
    "suggested_rename": "SuggestedRename",
    "repro_path": "ReproPath",
    "retry_count": "RetryCount",
    "retry_limit": "RetryLimit",
    "escalated": "Escalated",
}


def normalize_failure_marker_payload(raw: dict[str, Any]) -> dict[str, Any]:
    return {FAILURE_MARKER_KEY_MAP.get(key, key): value for key, value in raw.items()}


def failure_record_from_marker_payload(marker_file: Path, raw: Any) -> FailureRecord | None:
    if not isinstance(raw, dict):
        return None
    return FailureRecord(source_json=marker_file, payload=normalize_failure_marker_payload(raw))
