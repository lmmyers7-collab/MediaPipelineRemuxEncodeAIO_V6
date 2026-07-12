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

def rerun_csv_preview_payload(
    resolved: ResolvedPaths,
    request: Mapping[str, Any],
    *,
    service: Any | None = None,
) -> dict[str, Any]:
    csv_text = _clean_text(request.get("csv_path"))
    request_dict = dict(request)
    lifecycle = rerun_lifecycle_from_request(request_dict)
    lifecycle_errors = rerun_lifecycle_errors(lifecycle)
    stage_mode = lifecycle.stage_mode
    original_mode = lifecycle.original_mode
    return_mode = lifecycle.return_mode
    scope = rerun_preview_scope_from_request(request)
    recent = recent_rerun_csv_candidates(resolved, service)

    if not csv_text:
        return _preview_error_payload("CSV path is required.", csv_text, lifecycle, lifecycle_errors, scope, recent, resolved)

    csv_path = Path(csv_text)
    if not csv_path.exists() or not csv_path.is_file():
        return _preview_error_payload(f"CSV not found: {csv_path}", csv_text, lifecycle, lifecycle_errors, scope, recent, resolved)

    try:
        csv_result = _read_rerun_csv_rows(csv_path)
    except Exception as exc:
        return _preview_error_payload(f"CSV could not be read: {exc}", csv_text, lifecycle, lifecycle_errors, scope, recent, resolved)

    fieldnames = list(csv_result.get("fieldnames") or [])
    raw_rows = list(csv_result.get("rows") or [])
    csv_errors = _csv_structure_errors(
        fieldnames=fieldnames,
        rows=raw_rows,
        read_errors=list(csv_result.get("errors") or []),
    )
    source_path_destination = rerun_source_path_destination_requested(lifecycle)
    rows = _classify_rows(
        raw_rows,
        default_stage_mode=stage_mode,
        default_original_mode=original_mode,
        default_return_mode=return_mode,
        valid_extensions=_valid_extension_set(resolved),
        resolved=resolved,
        source_path_destination=source_path_destination,
    )
    scoped = scoped_rerun_rows(rows, scope)
    scoped_keys = {row.row_index for row in scoped}
    blocked_in_scope = sum(1 for row in scoped if row.blocked_reasons)
    unsafe_defaults = bool(lifecycle_errors)
    state_correlation, state_matches = build_rerun_state_correlation(
        resolved,
        (row.source_path for row in rows),
        service=service,
    )
    preview_rows = [
        _preview_row(
            row,
            in_scope=row.row_index in scoped_keys,
            state_match=state_matches.get(rerun_state_path_key(row.source_path)),
        )
        for row in rows[:scope.preview_limit]
    ]
    warnings = _preview_warnings(rows, scoped, unsafe_defaults, fieldnames)
    for item in csv_errors:
        if item not in warnings:
            warnings.append(item)
    warnings.extend(lifecycle_errors)
    status = _status_for_preview(
        csv_error="; ".join(lifecycle_errors + csv_errors),
        unsafe_default_modes=unsafe_defaults,
        effective_rows=scoped,
        blocked_in_scope=blocked_in_scope,
    )
    counts = _preview_counts(rows, scoped, blocked_in_scope)
    return {
        "ok": status != "blocked",
        "command": RERUN_PREVIEW_COMMAND,
        "schema_version": RERUN_CSV_PREVIEW_SCHEMA_VERSION,
        "rule_schema_version": RERUN_RULE_DECISION_SCHEMA_VERSION,
        "status": status,
        "severity": "error" if status == "blocked" else "warning" if status == "review" else "ok",
        "message": _preview_message(status, len(scoped)),
        "csv_path": str(csv_path),
        "fieldnames": fieldnames,
        "safe_modes": _safe_lifecycle_modes(lifecycle, lifecycle_errors),
        "stage_mode": stage_mode,
        "original_mode": original_mode,
        "return_mode": return_mode,
        "execution_mode": lifecycle.execution_mode,
        "destination_mode": lifecycle.destination_mode,
        "original_policy": lifecycle.original_policy,
        "collision_policy": lifecycle.collision_policy,
        "window_size": lifecycle.window_size,
        "lifecycle": lifecycle.to_mapping(),
        "scope": _scope_mapping(scope),
        "counts": counts,
        "rule_summary": _rule_summary(rows),
        "tiles": _preview_tiles(
            csv_path=csv_path,
            counts=counts,
            lifecycle=lifecycle,
            import_root=rerun_import_csv_root(resolved),
            scoped_root=scoped_rerun_csv_root(resolved),
        ),
        "filter_options": _preview_options(rows),
        "warnings": warnings,
        "errors": lifecycle_errors + csv_errors + [
            item
            for item in warnings
            if status == "blocked"
            and (
                "blocked" in item
                or "No effective" in item
                or "missing source_path" in item
                or "relative source_path" in item
                or "source file not found" in item
                or "invalid media extension" in item
                or "duplicate source_path" in item
                or "duplicate planned output path" in item
                or "final output destination" in item
                or "configured output root" in item
            )
        ],
        "rows": preview_rows,
        "state_correlation": state_correlation,
        "preview_limit": scope.preview_limit,
        "recent_csvs": recent,
        "import_csv_root": str(rerun_import_csv_root(resolved) or ""),
        "scoped_csv_root": str(scoped_rerun_csv_root(resolved) or ""),
        "original_hold_root": str(rerun_original_hold_root(resolved) or ""),
        "touches_media": False,
        "writes_queue": False,
        "writes_file_overrides": False,
    }

__all__ = (
    "rerun_csv_preview_payload",
)
