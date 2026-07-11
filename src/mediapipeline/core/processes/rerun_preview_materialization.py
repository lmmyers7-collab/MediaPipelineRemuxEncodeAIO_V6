"""CSV rerun preview, scoping, and scoped CSV materialization helpers."""

from __future__ import annotations

import csv
import hashlib
import io
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime, UTC
from pathlib import Path, PureWindowsPath
from types import SimpleNamespace
from typing import Any

from mediapipeline.core.audit.rerun_csv import (
    planned_output_key_for_rerun_row,
    rerun_output_container_from_config,
)
from mediapipeline.core.network.library_roots import claim_library_fields_for_record
from mediapipeline.core.network.rerun_handoff import (
    network_rerun_handoff_for_row,
    network_rerun_handoff_root_evidence,
)
from mediapipeline.core.paths.contracts import ResolvedPaths
from mediapipeline.core.paths.layout import valid_extensions_from_config
from mediapipeline.core.processes.file_io import atomic_write_text
from mediapipeline.core.processes.rerun_policy import (
    RERUN_DESTINATION_MODES,
    RERUN_EXECUTION_MODES,
    RERUN_ORIGINAL_POLICIES,
    RERUN_FINAL_OUTPUT_ROOT_ERROR,
    RERUN_FINAL_OUTPUT_ROOT_UNAVAILABLE,
    rerun_destination_replaces_final,
    rerun_final_output_for_row,
    rerun_final_output_root_violation,
    rerun_lifecycle_errors,
    rerun_lifecycle_from_request,
    rerun_source_path_destination_requested,
)
from mediapipeline.core.processes.rerun_rules import (
    RERUN_RULE_CSV_COLUMNS,
    RERUN_RULE_DECISION_SCHEMA_VERSION,
    RerunRuleDecision,
    classify_rerun_rule,
    rerun_rule_counts,
    rerun_rule_csv_values,
)
from mediapipeline.core.processes.rerun_state_correlation import (
    RERUN_STATE_CORRELATION_SCHEMA_VERSION,
    build_rerun_state_correlation,
    rerun_state_path_key,
)


RERUN_CSV_PREVIEW_SCHEMA_VERSION = "desktop_rerun_csv_preview.v1"
RERUN_NETWORK_CSV_PREVIEW_SCHEMA_VERSION = "desktop_rerun_network_preview.v1"
RERUN_NETWORK_CSV_PREVIEW_ROW_SCHEMA_VERSION = "desktop_rerun_network_preview_row.v1"
RERUN_SCOPED_CSV_SCHEMA_VERSION = "desktop_rerun_scoped_csv.v1"
RERUN_PREVIEW_COMMAND = "rerun.preview"
RERUN_NETWORK_PREVIEW_COMMAND = "rerun.network_preview"
RERUN_CSV_DEFAULT_PREVIEW_LIMIT = 50
RERUN_CSV_MAX_PREVIEW_LIMIT = 200
RERUN_CSV_MAX_FIRST_N = 5000
RERUN_CSV_SOURCE_PATH_HEADERS = ("source_path", "Path", "SourcePath")


from mediapipeline.core.processes.rerun_preview_support import *  # noqa: F403
from mediapipeline.core.processes.rerun_preview_presentation import *  # noqa: F403

def request_needs_scoped_csv(request: Mapping[str, Any], preview: Mapping[str, Any]) -> bool:
    scope = rerun_preview_scope_from_request(request)
    counts = preview.get("counts") if isinstance(preview, Mapping) else {}
    total = int((counts or {}).get("total_rows") or 0)
    effective = int((counts or {}).get("effective_scoped_rows") or 0)
    return (
        not scope.enabled_only
        or scope.skip_blocked
        or scope.skip_warning_rows
        or scope.first_n > 0
        or bool(scope.issue_filters)
        or bool(scope.bucket_filters)
        or effective != total
    )


def materialize_scoped_rerun_csv(
    resolved: ResolvedPaths,
    request: Mapping[str, Any],
    *,
    preview: Mapping[str, Any] | None = None,
    service: Any | None = None,
) -> dict[str, Any]:
    payload = dict(preview or rerun_csv_preview_payload(resolved, request, service=service))
    csv_path = Path(str(payload.get("csv_path") or ""))
    if payload.get("status") == "blocked":
        raise RuntimeError(str(payload.get("message") or "CSV rerun preview is blocked."))
    csv_result = _read_rerun_csv_rows(csv_path)
    fieldnames = list(csv_result.get("fieldnames") or [])
    raw_rows = list(csv_result.get("rows") or [])
    csv_errors = _csv_structure_errors(
        fieldnames=fieldnames,
        rows=raw_rows,
        read_errors=list(csv_result.get("errors") or []),
    )
    if csv_errors:
        raise RuntimeError("; ".join(csv_errors))
    rows = _classify_rows(
        raw_rows,
        default_stage_mode=str(payload.get("stage_mode") or "copy"),
        default_original_mode=str(payload.get("original_mode") or "keep"),
        default_return_mode=str(payload.get("return_mode") or "park"),
        valid_extensions=_valid_extension_set(resolved),
        resolved=resolved,
        source_path_destination=bool((payload.get("lifecycle") or {}).get("confirm_source_overwrite"))
        and rerun_destination_replaces_final(
            str(payload.get("destination_mode") or ""),
            str(payload.get("collision_policy") or ""),
        ),
    )
    scoped = scoped_rerun_rows(rows, rerun_preview_scope_from_request(request))
    if not scoped:
        raise RuntimeError("No scoped rows are available for CSV rerun.")
    output_root = _scoped_csv_root(resolved)
    if output_root is None:
        raise RuntimeError("State root is unavailable; cannot materialize scoped rerun CSV.")
    source_digest = hashlib.sha256(str(csv_path).encode("utf-8", errors="replace")).hexdigest()[:12]
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = output_root / f"rerun_scoped_{stamp}_{source_digest}.csv"
    if not fieldnames:
        fieldnames = sorted({key for row in raw_rows for key in row})
    for column in RERUN_RULE_CSV_COLUMNS:
        if column not in fieldnames:
            fieldnames.append(column)
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    for row in scoped:
        output_row = {key: row.row.get(key, "") for key in fieldnames}
        output_row.update(rerun_rule_csv_values(row.rule_decision))
        writer.writerow(output_row)
    atomic_write_text(output_path, buffer.getvalue(), encoding="utf-8")
    return {
        "schema_version": RERUN_SCOPED_CSV_SCHEMA_VERSION,
        "source_csv_path": str(csv_path),
        "scoped_csv_path": str(output_path),
        "row_count": len(scoped),
        "scope": payload.get("scope") or _scope_mapping(rerun_preview_scope_from_request(request)),
        "touches_media": False,
        "writes_queue": False,
        "writes_file_overrides": False,
    }

__all__ = (
    "request_needs_scoped_csv",
    "materialize_scoped_rerun_csv",
)

