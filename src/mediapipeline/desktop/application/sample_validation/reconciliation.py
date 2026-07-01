from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from mediapipeline.core.paths.contracts import ResolvedPaths
from mediapipeline.core.sample_validation import reconciliation as _core_reconciliation

COMPLETED_MANIFEST_RECENT_RECORD_LIMIT = _core_reconciliation.COMPLETED_MANIFEST_RECENT_RECORD_LIMIT
COMPLETED_MANIFEST_TARGET_SCAN_MAX_BYTES = _core_reconciliation.COMPLETED_MANIFEST_TARGET_SCAN_MAX_BYTES
COMPLETED_MANIFEST_TARGET_SCAN_MAX_ROWS = _core_reconciliation.COMPLETED_MANIFEST_TARGET_SCAN_MAX_ROWS
SAMPLE_VALIDATION_CURRENT_EVIDENCE_SCHEMA = _core_reconciliation.SAMPLE_VALIDATION_CURRENT_EVIDENCE_SCHEMA
SAMPLE_VALIDATION_RECONCILIATION_SCHEMA = _core_reconciliation.SAMPLE_VALIDATION_RECONCILIATION_SCHEMA
SAMPLE_VALIDATION_TEXT_MAX_CHARS = _core_reconciliation.SAMPLE_VALIDATION_TEXT_MAX_CHARS


def sample_validation_current_evidence_payload(resolved: ResolvedPaths, record: Mapping[str, Any]) -> dict[str, Any]:
    return _core_reconciliation.sample_validation_current_evidence_payload(resolved, record)


def sample_validation_reconciliation_payload(
    resolved: ResolvedPaths,
    records: list[Mapping[str, Any]],
    *,
    artifact_errors: list[str] | None = None,
) -> dict[str, Any]:
    previous_recent_limit = _core_reconciliation.COMPLETED_MANIFEST_RECENT_RECORD_LIMIT
    previous_scan_bytes = _core_reconciliation.COMPLETED_MANIFEST_TARGET_SCAN_MAX_BYTES
    previous_scan_rows = _core_reconciliation.COMPLETED_MANIFEST_TARGET_SCAN_MAX_ROWS
    _core_reconciliation.COMPLETED_MANIFEST_RECENT_RECORD_LIMIT = COMPLETED_MANIFEST_RECENT_RECORD_LIMIT
    _core_reconciliation.COMPLETED_MANIFEST_TARGET_SCAN_MAX_BYTES = COMPLETED_MANIFEST_TARGET_SCAN_MAX_BYTES
    _core_reconciliation.COMPLETED_MANIFEST_TARGET_SCAN_MAX_ROWS = COMPLETED_MANIFEST_TARGET_SCAN_MAX_ROWS
    try:
        return _core_reconciliation.sample_validation_reconciliation_payload(
            resolved,
            records,
            artifact_errors=artifact_errors,
        )
    finally:
        _core_reconciliation.COMPLETED_MANIFEST_RECENT_RECORD_LIMIT = previous_recent_limit
        _core_reconciliation.COMPLETED_MANIFEST_TARGET_SCAN_MAX_BYTES = previous_scan_bytes
        _core_reconciliation.COMPLETED_MANIFEST_TARGET_SCAN_MAX_ROWS = previous_scan_rows

__all__ = [
    "COMPLETED_MANIFEST_RECENT_RECORD_LIMIT",
    "COMPLETED_MANIFEST_TARGET_SCAN_MAX_BYTES",
    "COMPLETED_MANIFEST_TARGET_SCAN_MAX_ROWS",
    "SAMPLE_VALIDATION_CURRENT_EVIDENCE_SCHEMA",
    "SAMPLE_VALIDATION_RECONCILIATION_SCHEMA",
    "SAMPLE_VALIDATION_TEXT_MAX_CHARS",
    "sample_validation_current_evidence_payload",
    "sample_validation_reconciliation_payload",
]
