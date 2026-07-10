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


@dataclass(frozen=True)
class RerunCsvRow:
    row_index: int
    row: dict[str, str]
    enabled: bool
    source_path: str
    stage_mode: str
    original_mode: str
    return_mode: str
    issue_text: str
    bucket_text: str
    warning_reasons: tuple[str, ...]
    blocked_reasons: tuple[str, ...]
    rule_decision: RerunRuleDecision
    duplicate_source: bool = False
    planned_output_key: str = ""
    final_output_path: str = ""
    final_output_source_field: str = ""
    duplicate_planned_output: bool = False
    duplicate_planned_output_first_row_index: int | None = None


@dataclass(frozen=True)
class RerunPreviewScope:
    enabled_only: bool
    skip_blocked: bool
    skip_warning_rows: bool
    first_n: int
    issue_filters: tuple[str, ...]
    bucket_filters: tuple[str, ...]
    preview_limit: int


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def _row_value(row: Mapping[str, Any], *names: str, default: str = "") -> str:
    lowered = {str(key).casefold(): value for key, value in row.items()}
    for name in names:
        value = lowered.get(name.casefold())
        text = _clean_text(value)
        if text:
            return text
    return default


def _normalize_choice(value: Any, default: str) -> str:
    text = _clean_text(value or default).casefold().replace(" ", "_")
    return text or default


def _bool_from_csv(value: Any, default: bool = False) -> bool:
    text = _clean_text(value).casefold()
    if not text:
        return default
    return text in {"1", "true", "yes", "y", "on", "enabled", "run"}


def _bool_from_request(value: Any, default: bool) -> bool:
    return value if isinstance(value, bool) else default


def _bounded_int(value: Any, *, default: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return min(maximum, max(minimum, parsed))


def _filter_values(value: Any) -> tuple[str, ...]:
    if isinstance(value, (list, tuple, set)):
        raw_items = value
    else:
        raw_items = str(value or "").replace(";", ",").replace("|", ",").split(",")
    values: list[str] = []
    seen: set[str] = set()
    for item in raw_items:
        text = _clean_text(item)
        if not text:
            continue
        key = text.casefold()
        if key in seen:
            continue
        seen.add(key)
        values.append(text)
    return tuple(values)


def _split_option_tokens(text: str) -> list[str]:
    normalized = _clean_text(text)
    if not normalized:
        return []
    return [
        token.strip()
        for token in normalized.replace(";", ",").replace("|", ",").split(",")
        if token.strip()
    ]


def rerun_preview_scope_from_request(request: Mapping[str, Any]) -> RerunPreviewScope:
    scope = request.get("scope")
    raw_scope = scope if isinstance(scope, Mapping) else request
    first_n_raw = raw_scope.get("first_n")
    try:
        first_n = int(first_n_raw)
    except (TypeError, ValueError):
        first_n = 0
    if first_n < 0:
        first_n = 0
    first_n = min(RERUN_CSV_MAX_FIRST_N, first_n)
    return RerunPreviewScope(
        enabled_only=_bool_from_request(raw_scope.get("enabled_only"), True),
        skip_blocked=_bool_from_request(raw_scope.get("skip_blocked"), False),
        skip_warning_rows=_bool_from_request(raw_scope.get("skip_warning_rows"), False),
        first_n=first_n,
        issue_filters=_filter_values(raw_scope.get("issue_filters", raw_scope.get("issue_filter"))),
        bucket_filters=_filter_values(raw_scope.get("bucket_filters", raw_scope.get("bucket_filter"))),
        preview_limit=_bounded_int(
            raw_scope.get("preview_limit"),
            default=RERUN_CSV_DEFAULT_PREVIEW_LIMIT,
            minimum=1,
            maximum=RERUN_CSV_MAX_PREVIEW_LIMIT,
        ),
    )


def _filter_matches(text: str, filters: tuple[str, ...]) -> bool:
    if not filters:
        return True
    haystack = text.casefold()
    tokens = [item.strip().casefold() for item in filters if item.strip()]
    return any(token in haystack for token in tokens)


def read_rerun_csv_rows(csv_path: Path) -> tuple[list[str], list[dict[str, str]]]:
    result = _read_rerun_csv_rows(csv_path)
    return result["fieldnames"], result["rows"]


def _read_rerun_csv_rows(csv_path: Path) -> dict[str, Any]:
    errors: list[str] = []
    rows: list[dict[str, str]] = []
    with csv_path.open("r", encoding="utf-8-sig", errors="replace", newline="") as handle:
        reader = csv.DictReader(handle, strict=True)
        fieldnames = [str(name) for name in (reader.fieldnames or []) if name is not None]
        for row_number, row in enumerate(reader, start=2):
            if None in row:
                errors.append(f"malformed CSV row {row_number}: extra column value without a header")
            rows.append({str(key): str(value or "") for key, value in row.items() if key is not None})
    return {"fieldnames": fieldnames, "rows": rows, "errors": errors}


def _csv_structure_errors(
    *,
    fieldnames: Iterable[str],
    rows: Iterable[Mapping[str, Any]],
    read_errors: Iterable[str],
) -> list[str]:
    errors = [str(item).strip() for item in read_errors if str(item).strip()]
    names = [str(name or "").strip() for name in fieldnames]
    if not any(names):
        errors.append("CSV has no header columns.")
    elif not _fieldnames_include_source_path(names):
        errors.append("CSV is missing source_path header.")
    if not list(rows):
        errors.append("CSV contains no data rows.")
    deduped: list[str] = []
    seen: set[str] = set()
    for item in errors:
        key = item.casefold()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def _fieldnames_include_source_path(fieldnames: Iterable[str]) -> bool:
    headers = {str(name).casefold() for name in fieldnames}
    return any(name.casefold() in headers for name in RERUN_CSV_SOURCE_PATH_HEADERS)


def _valid_extension_set(resolved: ResolvedPaths) -> set[str]:
    raw = valid_extensions_from_config(dict(getattr(resolved, "config_data", {}) or {}))
    values: set[str] = set()
    for item in raw:
        text = str(item or "").strip().lower()
        if not text:
            continue
        values.add(text if text.startswith(".") else f".{text}")
    return values


def _is_absolute_source_path(source_path: str) -> bool:
    text = str(source_path or "").strip()
    if not text:
        return False
    try:
        return Path(text).is_absolute() or PureWindowsPath(text).is_absolute()
    except (OSError, ValueError):
        return False


def _source_file_exists(source_path: str) -> bool:
    try:
        return Path(source_path).is_file()
    except (OSError, ValueError):
        return False


def _source_extension(source_path: str) -> str:
    try:
        return Path(source_path).suffix.lower()
    except (OSError, ValueError):
        return ""


def _classify_rows(
    rows: Iterable[Mapping[str, Any]],
    *,
    default_stage_mode: str,
    default_original_mode: str,
    default_return_mode: str,
    valid_extensions: set[str] | None = None,
    resolved: ResolvedPaths | None = None,
    source_path_destination: bool = False,
) -> list[RerunCsvRow]:
    source_counts: dict[str, int] = {}
    raw_rows = list(rows)
    for row in raw_rows:
        source_path = _row_value(row, "source_path", "Path", "SourcePath")
        if source_path:
            key = source_path.casefold()
            source_counts[key] = source_counts.get(key, 0) + 1

    config_data = getattr(resolved, "config_data", None)
    output_container = rerun_output_container_from_config(config_data if isinstance(config_data, Mapping) else None)
    planned_output_keys: list[str] = []
    planned_output_counts: dict[str, int] = {}
    planned_output_first_index: dict[str, int] = {}
    for index, row in enumerate(raw_rows):
        source_path = _row_value(row, "source_path", "Path", "SourcePath")
        enabled = _bool_from_csv(_row_value(row, "enabled", "rerun_enabled", "Enabled", default="true"), True)
        row_stage_override = _normalize_choice(_row_value(row, "stage_mode", "StageMode", default=""), "")
        row_original_override = _normalize_choice(
            _row_value(row, "post_success_original", "original_mode", "OriginalMode", default=""),
            "",
        )
        row_return_override = _normalize_choice(_row_value(row, "return_mode", "ReturnMode", default=""), "")
        safe_row_modes = not (
            (row_stage_override and row_stage_override != "copy")
            or (row_original_override and row_original_override != "keep")
            or (row_return_override and row_return_override != "park")
        )
        source_ok = bool(source_path and _is_absolute_source_path(source_path) and _source_file_exists(source_path))
        extension_ok = bool(
            source_ok and (valid_extensions is None or _source_extension(source_path) in valid_extensions)
        )
        duplicate_source = bool(source_path and source_counts.get(source_path.casefold(), 0) > 1)
        planned_key = planned_output_key_for_rerun_row(row, output_container=output_container)
        planned_output_keys.append(planned_key)
        if not (enabled and safe_row_modes and source_ok and extension_ok and not duplicate_source and planned_key):
            continue
        planned_output_counts[planned_key] = planned_output_counts.get(planned_key, 0) + 1
        planned_output_first_index.setdefault(planned_key, index)

    classified: list[RerunCsvRow] = []
    for index, row in enumerate(raw_rows):
        source_path = _row_value(row, "source_path", "Path", "SourcePath")
        enabled = _bool_from_csv(_row_value(row, "enabled", "rerun_enabled", "Enabled", default="true"), True)
        row_stage_override = _normalize_choice(_row_value(row, "stage_mode", "StageMode", default=""), "")
        row_original_override = _normalize_choice(
            _row_value(row, "post_success_original", "original_mode", "OriginalMode", default=""),
            "",
        )
        row_return_override = _normalize_choice(_row_value(row, "return_mode", "ReturnMode", default=""), "")
        stage_mode = _normalize_choice(_row_value(row, "stage_mode", "StageMode", default=default_stage_mode), "copy")
        original_mode = _normalize_choice(
            _row_value(row, "post_success_original", "original_mode", "OriginalMode", default=default_original_mode),
            "keep",
        )
        return_mode = _normalize_choice(_row_value(row, "return_mode", "ReturnMode", default=default_return_mode), "park")
        issue_text = _row_value(row, "audit_issue_codes", "IssueCodes", "NonSidecarIssueCodes", "PrimaryIssueCode")
        bucket_text = _row_value(row, "effective_bucket", "EffectiveBucket", "Bucket", "priority_fix_level", "PriorityFixLevel")
        warnings: list[str] = []
        blockers: list[str] = []
        source_is_absolute: bool | None = None
        source_exists: bool | None = None
        source_extension_valid: bool | None = None
        duplicate_source = bool(source_path and source_counts.get(source_path.casefold(), 0) > 1)
        planned_output_key = planned_output_keys[index] if index < len(planned_output_keys) else ""
        duplicate_planned_output = bool(
            planned_output_key and planned_output_counts.get(planned_output_key, 0) > 1
        )
        if not enabled:
            warnings.append("disabled row")
        if not source_path:
            blockers.append("missing source_path")
        elif not _is_absolute_source_path(source_path):
            source_is_absolute = False
            blockers.append("relative source_path")
        else:
            source_is_absolute = True
            source_exists = _source_file_exists(source_path)
            if not source_exists:
                blockers.append("source file not found")
            else:
                source_extension_valid = valid_extensions is None or _source_extension(source_path) in valid_extensions
                if not source_extension_valid:
                    blockers.append("invalid media extension")
        if duplicate_source:
            blockers.append("duplicate source_path")
        if duplicate_planned_output:
            blockers.append(f"duplicate planned output path: {planned_output_key}")
        if (
            (row_stage_override and row_stage_override != "copy")
            or (row_original_override and row_original_override != "keep")
            or (row_return_override and row_return_override != "park")
        ):
            blockers.append("blocked source-mutating or in-place mode")
        rule_decision = classify_rerun_rule(
            row,
            source_path=source_path,
            source_exists=source_exists,
            is_absolute_source=source_is_absolute,
            valid_extension=source_extension_valid,
            duplicate_source=duplicate_source,
        )
        for reason in rule_decision.blocked_reasons:
            if reason not in blockers:
                blockers.append(reason)
        for reason in rule_decision.warning_reasons:
            if reason not in warnings:
                warnings.append(reason)
        final_output_field, final_output_path = rerun_final_output_for_row(
            row,
            source_path=source_path,
            source_path_destination=source_path_destination,
        )
        if resolved is not None:
            if final_output_path:
                violation = rerun_final_output_root_violation(
                    resolved,
                    row,
                    source_path=source_path,
                    final_output_path=final_output_path,
                    final_output_field=final_output_field,
                    confirm_source_overwrite=source_path_destination,
                )
                if violation and violation not in blockers:
                    blockers.append(violation)
        classified.append(
            RerunCsvRow(
                row_index=index,
                row={str(key): str(value or "") for key, value in row.items()},
                enabled=enabled,
                source_path=source_path,
                stage_mode=stage_mode,
                original_mode=original_mode,
                return_mode=return_mode,
                issue_text=issue_text,
                bucket_text=bucket_text,
                warning_reasons=tuple(warnings),
                blocked_reasons=tuple(blockers),
                rule_decision=rule_decision,
                duplicate_source=duplicate_source,
                planned_output_key=planned_output_key,
                final_output_path=final_output_path,
                final_output_source_field=final_output_field,
                duplicate_planned_output=duplicate_planned_output,
                duplicate_planned_output_first_row_index=planned_output_first_index.get(planned_output_key),
            )
        )
    return classified


def _safe_lifecycle_modes(lifecycle: Any, lifecycle_errors: list[str]) -> bool:
    return lifecycle.stage_mode == "copy" and lifecycle.original_mode == "keep" and not lifecycle_errors


def _row_in_scope(row: RerunCsvRow, scope: RerunPreviewScope) -> bool:
    if scope.enabled_only and not row.enabled:
        return False
    if scope.skip_blocked and row.blocked_reasons:
        return False
    if scope.skip_warning_rows and row.warning_reasons:
        return False
    if not _filter_matches(row.issue_text, scope.issue_filters):
        return False
    if not _filter_matches(row.bucket_text, scope.bucket_filters):
        return False
    return True


def scoped_rerun_rows(rows: list[RerunCsvRow], scope: RerunPreviewScope) -> list[RerunCsvRow]:
    scoped = [row for row in rows if _row_in_scope(row, scope)]
    if scope.first_n > 0:
        scoped = scoped[:scope.first_n]
    return scoped


def _row_status(row: RerunCsvRow, in_scope: bool) -> str:
    if row.blocked_reasons:
        return "blocked"
    if not in_scope:
        return "filtered"
    if row.warning_reasons:
        return "warning"
    return "ready"


def _source_stat_fields(source_path: str) -> dict[str, Any]:
    if not source_path:
        return {"source_size": 0, "source_mtime_utc": ""}
    try:
        stat = Path(source_path).stat()
    except OSError:
        return {"source_size": 0, "source_mtime_utc": ""}
    return {
        "source_size": stat.st_size,
        "source_mtime_utc": datetime.fromtimestamp(stat.st_mtime, UTC).isoformat(),
    }


def _preview_row(
    row: RerunCsvRow,
    *,
    in_scope: bool,
    state_match: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    reasons = list(row.blocked_reasons) + list(row.warning_reasons)
    state = dict(state_match or {})
    rule = row.rule_decision.to_mapping()
    final_output_field = row.final_output_source_field
    final_output_path = row.final_output_path
    return {
        "row_index": row.row_index,
        "enabled": row.enabled,
        "status": _row_status(row, in_scope),
        "in_scope": in_scope,
        "source_path": row.source_path,
        **_source_stat_fields(row.source_path),
        "source_identity_v2": _row_value(row.row, "source_identity_v2", "SourceIdentityV2"),
        "source_identity_v2_algorithm": _row_value(row.row, "source_identity_v2_algorithm", "SourceIdentityV2Algorithm"),
        "library_id": _row_value(row.row, "library_id", "LibraryId"),
        "media_kind": _row_value(row.row, "media_kind", "MediaKind", "MediaType"),
        "audit_issue_codes": _row_value(row.row, "audit_issue_codes", "IssueCodes", "PrimaryIssueCode"),
        "issue": row.issue_text,
        "bucket": row.bucket_text,
        "stage_mode": row.stage_mode,
        "original_mode": row.original_mode,
        "return_mode": row.return_mode,
        "lookup_title": _row_value(row.row, "lookup_title", "LookupTitle"),
        "relative_path": _row_value(row.row, "relative_path", "RelativePath"),
        "planned_output_key": row.planned_output_key,
        "final_output_path": final_output_path,
        "final_output_source": (
            "source_path"
            if final_output_field == "source_path"
            else "csv_completed_output"
            if final_output_path
            else ""
        ),
        "final_output_source_field": final_output_field,
        "duplicate_planned_output": row.duplicate_planned_output,
        "duplicate_planned_output_first_row_index": row.duplicate_planned_output_first_row_index,
        "reason": "; ".join(reasons),
        "rerun_rule_id": row.rule_decision.rule_id,
        "rerun_rule_label": row.rule_decision.label,
        "rerun_rule_status": row.rule_decision.status,
        "rerun_rule_reason": row.rule_decision.reason,
        "rerun_rule_destination_behavior": row.rule_decision.destination_behavior,
        "rerun_rule_replacement_eligible": row.rule_decision.replacement_eligible,
        "rerun_rule_required_confirmations": list(row.rule_decision.required_confirmations),
        "rerun_rule_runtime_options": dict(row.rule_decision.runtime_options),
        "rerun_rule_evidence": dict(row.rule_decision.evidence),
        "rule_decision": rule,
        "state_flags": list(state.get("flags") or []),
        "state_evidence": list(state.get("evidence") or []),
    }


def _recent_csv_entry(path: Path, *, label: str, source: str) -> dict[str, Any] | None:
    try:
        if not path.exists() or not path.is_file():
            return None
        stat = path.stat()
    except OSError:
        return None
    return {
        "csv_key": hashlib.sha256(str(path).encode("utf-8", errors="replace")).hexdigest()[:20],
        "label": label,
        "source": source,
        "path": str(path),
        "size_bytes": int(stat.st_size),
        "modified_at": datetime.fromtimestamp(stat.st_mtime, UTC).isoformat(),
    }


def rerun_import_csv_root(resolved: ResolvedPaths) -> Path | None:
    if resolved.state_root is not None:
        return resolved.state_root / "Rerun" / "ImportCsv"
    if resolved.local_base is not None:
        return resolved.local_base / "State" / "Rerun" / "ImportCsv"
    return None


def scoped_rerun_csv_root(resolved: ResolvedPaths) -> Path | None:
    if resolved.state_root is not None:
        return resolved.state_root / "Rerun" / "ScopedCsv"
    if resolved.local_base is not None:
        return resolved.local_base / "State" / "Rerun" / "ScopedCsv"
    return None


def rerun_original_hold_root(resolved: ResolvedPaths) -> Path | None:
    if resolved.state_root is not None:
        return resolved.state_root / "Rerun" / "OriginalHold"
    if resolved.local_base is not None:
        return resolved.local_base / "State" / "Rerun" / "OriginalHold"
    return None


def recent_rerun_csv_candidates(resolved: ResolvedPaths, service: Any | None = None, *, limit: int = 8) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    seen: set[str] = set()

    def add(path: Path | None, *, label: str, source: str) -> None:
        if path is None:
            return
        key = str(path).casefold()
        if key in seen:
            return
        entry = _recent_csv_entry(path, label=label, source=source)
        if entry is None:
            return
        seen.add(key)
        entries.append(entry)

    for root, pattern, source in (
        (rerun_import_csv_root(resolved), "audit_rerun_export_*.csv", "rerun_import"),
        (scoped_rerun_csv_root(resolved), "rerun_scoped_*.csv", "scoped_rerun"),
    ):
        if root is None:
            continue
        try:
            paths = sorted(Path(root).glob(pattern), key=lambda item: item.stat().st_mtime, reverse=True)
        except OSError:
            continue
        for path in paths[:limit]:
            add(path, label=path.name, source=source)

    return sorted(entries, key=lambda item: str(item.get("modified_at") or ""), reverse=True)[:limit]


def _status_for_preview(*, csv_error: str, unsafe_default_modes: bool, effective_rows: list[RerunCsvRow], blocked_in_scope: int) -> str:
    if csv_error or unsafe_default_modes or not effective_rows or blocked_in_scope:
        return "blocked"
    if any(row.warning_reasons for row in effective_rows):
        return "review"
    return "ready"


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


def _network_preview_row_key(csv_path: str, row: Mapping[str, Any]) -> str:
    raw = "|".join(
        [
            _clean_text(csv_path),
            _clean_text(row.get("row_index")),
            _clean_text(row.get("source_path")),
            _clean_text(row.get("planned_output_key")),
        ]
    )
    return hashlib.sha256(raw.encode("utf-8", errors="replace")).hexdigest()[:24]


def _network_reason_parts(row: Mapping[str, Any]) -> list[str]:
    return [
        item.strip()
        for item in _clean_text(row.get("reason")).split(";")
        if item.strip()
    ]


def _network_source_mapping(resolved: ResolvedPaths, row: Mapping[str, Any]) -> dict[str, Any]:
    source_path = _clean_text(row.get("source_path"))
    if not source_path or _clean_text(row.get("status")) == "blocked":
        return {
            "status": "blocked",
            "ready": False,
            "method": "",
            "library_id": "",
            "relative_path": "",
            "requires_worker_path_map": False,
            "coordinator_source_path": source_path,
            "reason": "Source path is not eligible for a worker claim.",
        }

    record = SimpleNamespace(
        source_path=source_path,
        library_id=_clean_text(row.get("library_id")),
        relative_path=_clean_text(row.get("relative_path")),
    )
    library_id, relative_path = claim_library_fields_for_record(
        record,
        getattr(resolved, "config_data", {}) or {},
    )
    if library_id and relative_path:
        return {
            "status": "library_relative",
            "ready": True,
            "method": "library_id_relative_path",
            "library_id": library_id,
            "relative_path": relative_path,
            "requires_worker_path_map": False,
            "coordinator_source_path": source_path,
            "reason": "Source can be claimed with library_id and relative_path.",
        }
    return {
        "status": "worker_path_map_required",
        "ready": True,
        "method": "coordinator_source_path",
        "library_id": "",
        "relative_path": "",
        "requires_worker_path_map": True,
        "coordinator_source_path": source_path,
        "reason": "No configured LibraryProfiles root matched; worker path mapping would be required.",
    }


def _network_output_handoff(
    row: Mapping[str, Any],
    root_evidence: Mapping[str, Any],
    row_key: str,
) -> dict[str, Any]:
    return network_rerun_handoff_for_row(
        root_evidence,
        row_key=row_key,
        planned_output_key=_clean_text(row.get("planned_output_key")),
    )


def _network_destination_policy(row: Mapping[str, Any]) -> dict[str, Any]:
    reasons = _network_reason_parts(row)
    behavior = _clean_text(row.get("rerun_rule_destination_behavior"))
    confirmations = [
        _clean_text(item)
        for item in (row.get("rerun_rule_required_confirmations") or [])
        if _clean_text(item)
    ]
    risk_codes: list[str] = []
    if confirmations:
        risk_codes.append("confirmation_required")
    if behavior:
        risk_codes.append(f"destination_behavior:{behavior}")
    if any("outside configured output root" in reason or "configured output root" in reason for reason in reasons):
        risk_codes.append("destination_root_blocked")
    status = "blocked" if "destination_root_blocked" in risk_codes else "review" if risk_codes else "ready"
    return {
        "status": status,
        "risk_codes": risk_codes,
        "destination_behavior": behavior,
        "replacement_eligible": row.get("rerun_rule_replacement_eligible") is True,
        "required_confirmations": confirmations,
        "reason": "; ".join(reasons),
    }


def _network_preview_row(
    csv_path: str,
    resolved: ResolvedPaths,
    row: Mapping[str, Any],
    root_evidence: Mapping[str, Any],
) -> dict[str, Any]:
    local_status = _clean_text(row.get("status"))
    in_scope = row.get("in_scope") is True
    enabled = row.get("enabled") is True
    skipped = not in_scope or local_status == "filtered" or not enabled
    blocked = local_status == "blocked"
    reasons = _network_reason_parts(row)
    duplicate_source = any("duplicate source_path" in reason for reason in reasons)
    duplicate_planned = row.get("duplicate_planned_output") is True
    row_key = _network_preview_row_key(csv_path, row)
    source_mapping = _network_source_mapping(resolved, row)
    output_handoff = _network_output_handoff(row, root_evidence, row_key)
    destination_policy = _network_destination_policy(row)
    claim_blockers: list[str] = []
    if blocked:
        claim_blockers.append("local_preview_blocked")
    if skipped:
        claim_blockers.append("row_not_in_network_preview_scope")
    if source_mapping.get("ready") is not True:
        claim_blockers.append("source_mapping_not_ready")
    claimable = local_status in {"ready", "warning"} and not skipped and source_mapping.get("ready") is True
    start_blockers = list(claim_blockers)
    if output_handoff.get("ready") is not True:
        start_blockers.extend(str(item) for item in output_handoff.get("blockers") or [])
        if not output_handoff.get("blockers"):
            start_blockers.append("output_handoff_not_ready")
    return {
        "schema_version": RERUN_NETWORK_CSV_PREVIEW_ROW_SCHEMA_VERSION,
        "row_key": row_key,
        "row_index": row.get("row_index"),
        "source_path": _clean_text(row.get("source_path")),
        "enabled": enabled,
        "in_scope": in_scope,
        "local_preview_status": local_status,
        "claimable": claimable,
        "start_ready": claimable and output_handoff.get("ready") is True,
        "blocked": blocked,
        "skipped": skipped,
        "duplicate": duplicate_source or duplicate_planned,
        "duplicate_source": duplicate_source,
        "duplicate_planned_output": duplicate_planned,
        "duplicate_planned_output_first_row_index": row.get("duplicate_planned_output_first_row_index"),
        "claim_blockers": claim_blockers,
        "start_blockers": start_blockers,
        "source_mapping": source_mapping,
        "output_handoff": output_handoff,
        "destination_policy": destination_policy,
        "rule_decision": row.get("rule_decision") or {},
        "rerun_rule_id": _clean_text(row.get("rerun_rule_id")),
        "rerun_rule_label": _clean_text(row.get("rerun_rule_label")),
        "rerun_rule_status": _clean_text(row.get("rerun_rule_status")),
        "rerun_rule_reason": _clean_text(row.get("rerun_rule_reason")),
        "rerun_rule_destination_behavior": _clean_text(row.get("rerun_rule_destination_behavior")),
        "rerun_rule_replacement_eligible": row.get("rerun_rule_replacement_eligible") is True,
        "rerun_rule_required_confirmations": [
            _clean_text(item)
            for item in (row.get("rerun_rule_required_confirmations") or [])
            if _clean_text(item)
        ],
        "rerun_rule_runtime_options": dict(row.get("rerun_rule_runtime_options") or {}),
        "source_size": row.get("source_size") or 0,
        "source_mtime_utc": _clean_text(row.get("source_mtime_utc")),
        "source_identity_v2": _clean_text(row.get("source_identity_v2")),
        "source_identity_v2_algorithm": _clean_text(row.get("source_identity_v2_algorithm")),
        "media_kind": _clean_text(row.get("media_kind")),
        "audit_issue_codes": _clean_text(row.get("audit_issue_codes")),
        "final_output_path": _clean_text(row.get("final_output_path")),
        "final_output_source": _clean_text(row.get("final_output_source")),
        "final_output_source_field": _clean_text(row.get("final_output_source_field")),
        "reason": "; ".join(reasons),
    }


def rerun_network_csv_preview_payload(
    resolved: ResolvedPaths,
    request: Mapping[str, Any],
    *,
    service: Any | None = None,
) -> dict[str, Any]:
    local_preview = rerun_csv_preview_payload(resolved, request, service=service)
    csv_path = _clean_text(local_preview.get("csv_path") or request.get("csv_path"))
    handoff_root = network_rerun_handoff_root_evidence(resolved)
    rows = [
        _network_preview_row(csv_path, resolved, row, handoff_root)
        for row in local_preview.get("rows") or []
        if isinstance(row, Mapping)
    ]
    claimable_rows = sum(1 for row in rows if row.get("claimable") is True)
    start_ready_rows = sum(1 for row in rows if row.get("start_ready") is True)
    blocked_rows = sum(1 for row in rows if row.get("blocked") is True)
    skipped_rows = sum(1 for row in rows if row.get("skipped") is True)
    duplicate_rows = sum(1 for row in rows if row.get("duplicate") is True)
    source_mapping_ready_rows = sum(1 for row in rows if (row.get("source_mapping") or {}).get("ready") is True)
    source_mapping_path_map_required_rows = sum(
        1
        for row in rows
        if (row.get("source_mapping") or {}).get("requires_worker_path_map") is True
    )
    destination_policy_risk_rows = sum(
        1
        for row in rows
        if (row.get("destination_policy") or {}).get("status") in {"review", "blocked"}
    )
    output_handoff_ready_rows = sum(1 for row in rows if (row.get("output_handoff") or {}).get("ready") is True)
    status = "blocked" if local_preview.get("status") == "blocked" else "ready" if start_ready_rows else "review"
    warnings = [str(item) for item in local_preview.get("warnings") or []]
    if claimable_rows and output_handoff_ready_rows < claimable_rows:
        warnings.append("Network CSV rerun output handoff is not ready for every claimable row.")
    if handoff_root.get("coordinator_local_only") is True:
        warnings.append("NetworkRerunHandoffRoot is local-drive only; remote workers require a UNC/shared root.")
    start_blockers: list[str] = []
    if local_preview.get("status") == "blocked":
        start_blockers.append("local_preview_blocked")
    if claimable_rows <= 0:
        start_blockers.append("network_preview_has_no_claimable_rows")
    if start_ready_rows < claimable_rows:
        start_blockers.append("network_rerun_handoff_not_ready")
    return {
        "ok": bool(local_preview.get("ok")) and claimable_rows > 0,
        "command": RERUN_NETWORK_PREVIEW_COMMAND,
        "schema_version": RERUN_NETWORK_CSV_PREVIEW_SCHEMA_VERSION,
        "row_schema_version": RERUN_NETWORK_CSV_PREVIEW_ROW_SCHEMA_VERSION,
        "local_preview_schema_version": local_preview.get("schema_version"),
        "effect": "none",
        "status": status,
        "severity": "error" if status == "blocked" else "warning" if status == "review" else "ok",
        "message": "Network CSV rerun preview is read-only; it models future row claims without starting workers.",
        "csv_path": csv_path,
        "fieldnames": list(local_preview.get("fieldnames") or []),
        "lifecycle": local_preview.get("lifecycle") or {},
        "scope": local_preview.get("scope") or {},
        "local_preview_status": local_preview.get("status"),
        "local_preview_message": local_preview.get("message"),
        "local_counts": local_preview.get("counts") or {},
        "counts": {
            "preview_rows": len(rows),
            "claimable_rows": claimable_rows,
            "start_ready_rows": start_ready_rows,
            "blocked_rows": blocked_rows,
            "skipped_rows": skipped_rows,
            "duplicate_rows": duplicate_rows,
            "source_mapping_ready_rows": source_mapping_ready_rows,
            "source_mapping_path_map_required_rows": source_mapping_path_map_required_rows,
            "output_handoff_ready_rows": output_handoff_ready_rows,
            "destination_policy_risk_rows": destination_policy_risk_rows,
        },
        "rows": rows,
        "output_handoff": handoff_root,
        "warnings": warnings,
        "errors": [str(item) for item in local_preview.get("errors") or []],
        "can_start_network_batch": status != "blocked" and start_ready_rows > 0 and not start_blockers,
        "start_blockers": start_blockers,
        "state_files_would_write": [],
        "touches_media": False,
        "writes_queue": False,
        "writes_network_state": False,
        "writes_file_overrides": False,
        "launches_work": False,
    }


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
        "nonexistent_source_rows": sum(1 for row in rows if _row_has_reason(row, "source file not found")),
        "missing_file_rows": sum(1 for row in rows if _row_has_reason(row, "source file not found")),
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
    missing_file = sum(1 for row in rows if _row_has_reason(row, "source file not found"))
    if missing_file:
        warnings.append(f"{missing_file} row(s) reference source files that were not found.")
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


__all__ = [
    "RERUN_CSV_PREVIEW_SCHEMA_VERSION",
    "RERUN_NETWORK_CSV_PREVIEW_SCHEMA_VERSION",
    "RERUN_PREVIEW_COMMAND",
    "RERUN_NETWORK_PREVIEW_COMMAND",
    "materialize_scoped_rerun_csv",
    "read_rerun_csv_rows",
    "recent_rerun_csv_candidates",
    "request_needs_scoped_csv",
    "rerun_import_csv_root",
    "scoped_rerun_csv_root",
    "rerun_original_hold_root",
    "rerun_csv_preview_payload",
    "rerun_network_csv_preview_payload",
    "rerun_preview_scope_from_request",
    "scoped_rerun_rows",
]
