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

def _preview_error_payload(
    message: str,
    csv_path: str,
    lifecycle: Any,
    lifecycle_errors: list[str],
    scope: RerunPreviewScope,
    recent: list[dict[str, Any]],
    resolved: ResolvedPaths,
) -> dict[str, Any]:
    counts = _empty_counts()
    errors = [message] + [str(item) for item in lifecycle_errors if str(item).strip()]
    return {
        "ok": False,
        "command": RERUN_PREVIEW_COMMAND,
        "schema_version": RERUN_CSV_PREVIEW_SCHEMA_VERSION,
        "rule_schema_version": RERUN_RULE_DECISION_SCHEMA_VERSION,
        "status": "blocked",
        "severity": "error",
        "message": message,
        "csv_path": csv_path,
        "fieldnames": [],
        "safe_modes": _safe_lifecycle_modes(lifecycle, lifecycle_errors),
        "stage_mode": lifecycle.stage_mode,
        "original_mode": lifecycle.original_mode,
        "return_mode": lifecycle.return_mode,
        "execution_mode": lifecycle.execution_mode,
        "destination_mode": lifecycle.destination_mode,
        "original_policy": lifecycle.original_policy,
        "collision_policy": lifecycle.collision_policy,
        "window_size": lifecycle.window_size,
        "lifecycle": lifecycle.to_mapping(),
        "scope": _scope_mapping(scope),
        "counts": counts,
        "rule_summary": _rule_summary([]),
        "tiles": _preview_tiles(
            csv_path=csv_path,
            counts=counts,
            lifecycle=lifecycle,
            import_root=rerun_import_csv_root(resolved),
            scoped_root=scoped_rerun_csv_root(resolved),
        ),
        "filter_options": _preview_options([]),
        "warnings": errors,
        "errors": errors,
        "rows": [],
        "state_correlation": _empty_state_correlation(),
        "preview_limit": scope.preview_limit,
        "recent_csvs": recent,
        "import_csv_root": str(rerun_import_csv_root(resolved) or ""),
        "scoped_csv_root": str(scoped_rerun_csv_root(resolved) or ""),
        "original_hold_root": str(rerun_original_hold_root(resolved) or ""),
        "touches_media": False,
        "writes_queue": False,
        "writes_file_overrides": False,
    }


def _preview_message(status: str, effective_count: int) -> str:
    if status == "blocked":
        return "CSV rerun preview is blocked until the CSV path, modes, and scoped rows are safe."
    if status == "review":
        return f"CSV rerun preview found {effective_count} scoped row(s) with warnings."
    return f"CSV rerun preview found {effective_count} scoped executable row(s)."


def _empty_state_correlation() -> dict[str, Any]:
    return {
        "schema_version": RERUN_STATE_CORRELATION_SCHEMA_VERSION,
        "status": "not_run",
        "warnings": [],
        "counts": {
            "requested_source_rows": 0,
            "requested_distinct_source_paths": 0,
            "matched_source_rows": 0,
            "matched_distinct_source_paths": 0,
            "completed_matches_scanned": 0,
            "pending_publish_matches_scanned": 0,
            "prior_rerun_matches_scanned": 0,
            "completed_source_rows": 0,
            "pending_publish_source_rows": 0,
            "prior_rerun_source_rows": 0,
        },
        "sources": {
            "completed_manifest_path": "",
            "pending_publish": "",
            "rerun_manifest_root": "",
        },
        "touches_media": False,
        "writes_queue": False,
        "writes_file_overrides": False,
    }


def _empty_counts() -> dict[str, int]:
    return {
        "total_rows": 0,
        "enabled_rows": 0,
        "disabled_rows": 0,
        "effective_scoped_rows": 0,
        "blocked_rows": 0,
        "blocked_mode_rows": 0,
        "blocked_scoped_rows": 0,
        "duplicate_source_rows": 0,
        "duplicate_planned_output_rows": 0,
        "missing_source_rows": 0,
        "relative_source_rows": 0,
        "nonexistent_source_rows": 0,
        "missing_file_rows": 0,
        "source_location_unavailable_rows": 0,
        "source_access_failed_rows": 0,
        "source_missing_rows": 0,
        "source_identity_changed_rows": 0,
        "invalid_extension_rows": 0,
        "warning_rows": 0,
        "rule_blocked_rows": 0,
        "rule_warning_rows": 0,
    }


def _row_has_blocked_mode(row: RerunCsvRow) -> bool:
    return any("blocked source-mutating" in reason for reason in row.blocked_reasons)


def _row_has_reason(row: RerunCsvRow, reason: str) -> bool:
    return reason in row.blocked_reasons or reason in row.warning_reasons


def _row_reason_contains(row: RerunCsvRow, needle: str) -> bool:
    return any(needle in reason for reason in (*row.blocked_reasons, *row.warning_reasons))


def _row_source_health_code(row: RerunCsvRow) -> str:
    return str(row.source_health.code if row.source_health is not None else "")


def _preview_counts(rows: list[RerunCsvRow], scoped: list[RerunCsvRow], blocked_in_scope: int) -> dict[str, int]:
    return {
        "total_rows": len(rows),
        "enabled_rows": sum(1 for row in rows if row.enabled),
        "disabled_rows": sum(1 for row in rows if not row.enabled),
        "effective_scoped_rows": len(scoped),
        "blocked_rows": sum(1 for row in rows if row.blocked_reasons),
        "blocked_mode_rows": sum(1 for row in rows if _row_has_blocked_mode(row)),
        "blocked_scoped_rows": blocked_in_scope,
        "duplicate_source_rows": sum(1 for row in rows if row.duplicate_source),
        "duplicate_planned_output_rows": sum(1 for row in rows if row.duplicate_planned_output),
        "missing_source_rows": sum(1 for row in rows if not row.source_path),
        "relative_source_rows": sum(1 for row in rows if _row_has_reason(row, "relative source_path")),
        "nonexistent_source_rows": sum(1 for row in rows if _row_source_health_code(row) == "source_missing"),
        "missing_file_rows": sum(1 for row in rows if _row_source_health_code(row) == "source_missing"),
        "source_location_unavailable_rows": sum(
            1 for row in rows if _row_source_health_code(row) == "source_location_unavailable"
        ),
        "source_access_failed_rows": sum(1 for row in rows if _row_source_health_code(row) == "source_access_failed"),
        "source_missing_rows": sum(1 for row in rows if _row_source_health_code(row) == "source_missing"),
        "source_identity_changed_rows": sum(
            1 for row in rows if _row_source_health_code(row) == "source_identity_changed"
        ),
        "invalid_extension_rows": sum(1 for row in rows if _row_has_reason(row, "invalid media extension")),
        "warning_rows": sum(1 for row in rows if row.warning_reasons),
        "rule_blocked_rows": sum(1 for row in rows if row.rule_decision.status == "blocked"),
        "rule_warning_rows": sum(1 for row in rows if row.rule_decision.status == "warning"),
    }


def _rule_summary(rows: list[RerunCsvRow]) -> dict[str, Any]:
    decisions = [row.rule_decision for row in rows]
    return {
        "schema_version": RERUN_RULE_DECISION_SCHEMA_VERSION,
        "counts": rerun_rule_counts(decisions),
        "blocked_rows": sum(1 for decision in decisions if decision.status == "blocked"),
        "warning_rows": sum(1 for decision in decisions if decision.status == "warning"),
        "replacement_eligible_rows": sum(1 for decision in decisions if decision.replacement_eligible),
    }


def _option_counts(rows: list[RerunCsvRow], attr_name: str) -> list[dict[str, Any]]:
    counts: dict[str, int] = {}
    labels: dict[str, str] = {}
    for row in rows:
        text = str(getattr(row, attr_name) or "")
        for token in _split_option_tokens(text):
            key = token.casefold()
            counts[key] = counts.get(key, 0) + 1
            labels.setdefault(key, token)
    return [
        {"value": labels[key], "label": labels[key], "count": count}
        for key, count in sorted(counts.items(), key=lambda item: (-item[1], labels[item[0]].casefold()))
    ]


def _rule_option_counts(rows: list[RerunCsvRow]) -> list[dict[str, Any]]:
    counts: dict[str, int] = {}
    labels: dict[str, str] = {}
    for row in rows:
        key = row.rule_decision.rule_id
        counts[key] = counts.get(key, 0) + 1
        labels.setdefault(key, row.rule_decision.label)
    return [
        {"value": key, "label": labels[key], "count": count}
        for key, count in sorted(counts.items(), key=lambda item: (-item[1], labels[item[0]].casefold()))
    ]


def _preview_options(rows: list[RerunCsvRow]) -> dict[str, Any]:
    return {
        "issue_filters": _option_counts(rows, "issue_text"),
        "bucket_filters": _option_counts(rows, "bucket_text"),
        "rule_filters": _rule_option_counts(rows),
        "status_filters": [
            {"value": "ready", "label": "Ready"},
            {"value": "warning", "label": "Warning"},
            {"value": "blocked", "label": "Blocked"},
            {"value": "filtered", "label": "Filtered"},
        ],
        "execution_modes": [{"value": value, "label": value.replace("_", " ").title()} for value in RERUN_EXECUTION_MODES],
        "destination_modes": [{"value": value, "label": value.replace("_", " ").title()} for value in RERUN_DESTINATION_MODES],
        "original_policies": [{"value": value, "label": value.replace("_", " ").title()} for value in RERUN_ORIGINAL_POLICIES],
    }


def _preview_tiles(
    *,
    csv_path: Path | str,
    counts: dict[str, int],
    lifecycle: Any,
    import_root: Path | None,
    scoped_root: Path | None,
) -> list[dict[str, Any]]:
    executable = max(0, int(counts.get("effective_scoped_rows", 0)) - int(counts.get("blocked_scoped_rows", 0)))
    scratch_rows = int(counts.get("total_rows", 0))
    if lifecycle.execution_mode == "one_at_a_time":
        scratch_rows = min(1, executable)
    elif lifecycle.execution_mode == "windowed":
        scratch_rows = min(int(lifecycle.window_size or 1), executable)
    csv_text = str(csv_path or "").strip()
    return [
        {"key": "csv_selected", "label": "CSV", "value": "selected" if csv_text else "missing", "detail": csv_text},
        {"key": "rows", "label": "Rows", "value": int(counts.get("total_rows", 0))},
        {"key": "executable_rows", "label": "Executable", "value": executable},
        {"key": "blockers", "label": "Blockers", "value": int(counts.get("blocked_rows", 0))},
        {"key": "warnings", "label": "Warnings", "value": int(counts.get("warning_rows", 0))},
        {"key": "policy", "label": "Policy", "value": lifecycle.original_policy, "detail": lifecycle.collision_policy},
        {"key": "execution_mode", "label": "Execution", "value": lifecycle.execution_mode, "detail": f"window={lifecycle.window_size}"},
        {"key": "destination", "label": "Destination", "value": lifecycle.destination_mode},
        {"key": "scratch_estimate", "label": "Scratch", "value": f"{scratch_rows} staged row(s)", "detail": "Bounded by execution mode."},
        {"key": "phase", "label": "Phase", "value": "preview"},
        {"key": "evidence", "label": "Evidence", "value": "backend", "detail": f"import={import_root or ''}; scoped={scoped_root or ''}"},
    ]


def _preview_warnings(rows: list[RerunCsvRow], scoped: list[RerunCsvRow], unsafe_defaults: bool, fieldnames: list[str]) -> list[str]:
    warnings: list[str] = []
    if not fieldnames:
        warnings.append("CSV has no header columns.")
    if unsafe_defaults:
        warnings.append("Selected lifecycle policy is blocked until required confirmations and supported modes are present.")
    if not scoped:
        warnings.append("No effective scoped rows are available for rerun.")
    blocked = sum(1 for row in rows if _row_has_blocked_mode(row))
    if blocked:
        warnings.append(f"{blocked} row(s) have blocked source-mutating or in-place policy.")
    missing = sum(1 for row in rows if not row.source_path)
    if missing:
        warnings.append(f"{missing} row(s) are missing source_path.")
    relative = sum(1 for row in rows if _row_has_reason(row, "relative source_path"))
    if relative:
        warnings.append(f"{relative} row(s) use relative source_path values.")
    unavailable = sum(1 for row in rows if _row_source_health_code(row) == "source_location_unavailable")
    if unavailable:
        warnings.append(
            f"{unavailable} row(s) are waiting because their configured source location is unavailable."
        )
    access_failed = sum(1 for row in rows if _row_source_health_code(row) == "source_access_failed")
    if access_failed:
        warnings.append(f"{access_failed} row(s) are waiting because the source access probe failed.")
    missing_file = sum(1 for row in rows if _row_source_health_code(row) == "source_missing")
    if missing_file:
        warnings.append(
            f"{missing_file} row(s) reference source files that were not found beneath reachable source roots."
        )
    identity_changed = sum(1 for row in rows if _row_source_health_code(row) == "source_identity_changed")
    if identity_changed:
        warnings.append(
            f"{identity_changed} row(s) are blocked because source identity changed after the CSV was planned."
        )
    invalid_extension = sum(1 for row in rows if _row_has_reason(row, "invalid media extension"))
    if invalid_extension:
        warnings.append(f"{invalid_extension} row(s) use invalid media extensions.")
    duplicate = sum(1 for row in rows if row.duplicate_source)
    if duplicate:
        warnings.append(f"{duplicate} row(s) are blocked because they share a duplicate source_path.")
    duplicate_planned_output = sum(1 for row in rows if row.duplicate_planned_output)
    if duplicate_planned_output:
        warnings.append(f"{duplicate_planned_output} row(s) are blocked because they share a duplicate planned output path.")
    rule_blocked = sum(1 for row in rows if row.rule_decision.status == "blocked")
    if rule_blocked:
        warnings.append(f"{rule_blocked} row(s) are blocked by backend CSV rerun rule policy.")
    rule_warning = sum(1 for row in rows if row.rule_decision.status == "warning")
    if rule_warning:
        warnings.append(f"{rule_warning} row(s) have backend CSV rerun rule warnings.")
    destination_blocked = sum(
        1
        for row in rows
        if _row_reason_contains(row, RERUN_FINAL_OUTPUT_ROOT_ERROR)
        or _row_reason_contains(row, RERUN_FINAL_OUTPUT_ROOT_UNAVAILABLE)
    )
    if destination_blocked:
        warnings.append(f"{destination_blocked} row(s) have final output destinations outside configured output roots.")
    disabled = sum(1 for row in rows if not row.enabled)
    if disabled:
        warnings.append(f"{disabled} row(s) are disabled in the CSV.")
    return warnings


def _scope_mapping(scope: RerunPreviewScope) -> dict[str, Any]:
    issue_filter = ", ".join(scope.issue_filters)
    bucket_filter = ", ".join(scope.bucket_filters)
    return {
        "enabled_only": scope.enabled_only,
        "skip_blocked": scope.skip_blocked,
        "skip_warning_rows": scope.skip_warning_rows,
        "first_n": scope.first_n,
        "issue_filter": issue_filter,
        "bucket_filter": bucket_filter,
        "issue_filters": list(scope.issue_filters),
        "bucket_filters": list(scope.bucket_filters),
        "preview_limit": scope.preview_limit,
    }


def _scoped_csv_root(resolved: ResolvedPaths) -> Path | None:
    return scoped_rerun_csv_root(resolved)

__all__ = (
    "_preview_error_payload",
    "_preview_message",
    "_empty_state_correlation",
    "_empty_counts",
    "_row_has_blocked_mode",
    "_row_has_reason",
    "_row_reason_contains",
    "_preview_counts",
    "_rule_summary",
    "_option_counts",
    "_rule_option_counts",
    "_preview_options",
    "_preview_tiles",
    "_preview_warnings",
    "_scope_mapping",
    "_scoped_csv_root",
)
