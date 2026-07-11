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

__all__ = (
    "RERUN_CSV_PREVIEW_SCHEMA_VERSION",
    "RERUN_NETWORK_CSV_PREVIEW_SCHEMA_VERSION",
    "RERUN_NETWORK_CSV_PREVIEW_ROW_SCHEMA_VERSION",
    "RERUN_SCOPED_CSV_SCHEMA_VERSION",
    "RERUN_PREVIEW_COMMAND",
    "RERUN_NETWORK_PREVIEW_COMMAND",
    "RERUN_CSV_DEFAULT_PREVIEW_LIMIT",
    "RERUN_CSV_MAX_PREVIEW_LIMIT",
    "RERUN_CSV_MAX_FIRST_N",
    "RERUN_CSV_SOURCE_PATH_HEADERS",
    "RerunCsvRow",
    "RerunPreviewScope",
    "_clean_text",
    "_row_value",
    "_normalize_choice",
    "_bool_from_csv",
    "_bool_from_request",
    "_bounded_int",
    "_filter_values",
    "_split_option_tokens",
    "rerun_preview_scope_from_request",
    "_filter_matches",
    "read_rerun_csv_rows",
    "_read_rerun_csv_rows",
    "_csv_structure_errors",
    "_fieldnames_include_source_path",
    "_valid_extension_set",
    "_is_absolute_source_path",
    "_source_file_exists",
    "_source_extension",
    "_classify_rows",
    "_safe_lifecycle_modes",
    "_row_in_scope",
    "scoped_rerun_rows",
    "_row_status",
    "_source_stat_fields",
    "_preview_row",
    "_recent_csv_entry",
    "rerun_import_csv_root",
    "scoped_rerun_csv_root",
    "rerun_original_hold_root",
    "recent_rerun_csv_candidates",
    "_status_for_preview",
)
