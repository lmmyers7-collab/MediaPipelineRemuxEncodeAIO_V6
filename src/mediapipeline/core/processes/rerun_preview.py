"""CSV rerun preview, scoping, and scoped CSV materialization helpers."""

from __future__ import annotations

import csv
import hashlib
import io
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from mediapipeline.core.kernel.models import ResolvedPaths
from mediapipeline.core.processes.file_io import atomic_write_text
from mediapipeline.core.processes.rerun_policy import rerun_modes_are_supported


RERUN_CSV_PREVIEW_SCHEMA_VERSION = "desktop_rerun_csv_preview.v1"
RERUN_SCOPED_CSV_SCHEMA_VERSION = "desktop_rerun_scoped_csv.v1"
RERUN_PREVIEW_COMMAND = "rerun.preview"
RERUN_CSV_DEFAULT_PREVIEW_LIMIT = 50
RERUN_CSV_MAX_PREVIEW_LIMIT = 200
RERUN_CSV_MAX_FIRST_N = 5000


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
    duplicate_source: bool = False


@dataclass(frozen=True)
class RerunPreviewScope:
    enabled_only: bool
    skip_blocked: bool
    skip_warning_rows: bool
    first_n: int
    issue_filter: str
    bucket_filter: str
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
        issue_filter=_clean_text(raw_scope.get("issue_filter")),
        bucket_filter=_clean_text(raw_scope.get("bucket_filter")),
        preview_limit=_bounded_int(
            raw_scope.get("preview_limit"),
            default=RERUN_CSV_DEFAULT_PREVIEW_LIMIT,
            minimum=1,
            maximum=RERUN_CSV_MAX_PREVIEW_LIMIT,
        ),
    )


def _filter_matches(text: str, filter_text: str) -> bool:
    if not filter_text:
        return True
    haystack = text.casefold()
    tokens = [item.strip().casefold() for item in filter_text.replace(";", ",").split(",") if item.strip()]
    return any(token in haystack for token in tokens)


def read_rerun_csv_rows(csv_path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with csv_path.open("r", encoding="utf-8-sig", errors="replace", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = [str(name) for name in (reader.fieldnames or []) if name is not None]
        rows = [
            {str(key): str(value or "") for key, value in row.items() if key is not None}
            for row in reader
        ]
    return fieldnames, rows


def _classify_rows(
    rows: Iterable[Mapping[str, Any]],
    *,
    default_stage_mode: str,
    default_original_mode: str,
    default_return_mode: str,
) -> list[RerunCsvRow]:
    source_counts: dict[str, int] = {}
    raw_rows = list(rows)
    for row in raw_rows:
        source_path = _row_value(row, "source_path", "Path", "SourcePath")
        if source_path:
            key = source_path.casefold()
            source_counts[key] = source_counts.get(key, 0) + 1

    classified: list[RerunCsvRow] = []
    for index, row in enumerate(raw_rows):
        source_path = _row_value(row, "source_path", "Path", "SourcePath")
        enabled = _bool_from_csv(_row_value(row, "enabled", "rerun_enabled", "Enabled", default="true"), True)
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
        if not enabled:
            warnings.append("disabled row")
        if not source_path:
            blockers.append("missing source_path")
        if source_path and source_counts.get(source_path.casefold(), 0) > 1:
            warnings.append("duplicate source_path")
        if not rerun_modes_are_supported(stage_mode, original_mode, return_mode):
            blockers.append("blocked source-mutating or in-place mode")
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
                duplicate_source=bool(source_path and source_counts.get(source_path.casefold(), 0) > 1),
            )
        )
    return classified


def _row_in_scope(row: RerunCsvRow, scope: RerunPreviewScope) -> bool:
    if scope.enabled_only and not row.enabled:
        return False
    if scope.skip_blocked and row.blocked_reasons:
        return False
    if scope.skip_warning_rows and row.warning_reasons:
        return False
    if not _filter_matches(row.issue_text, scope.issue_filter):
        return False
    if not _filter_matches(row.bucket_text, scope.bucket_filter):
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


def _preview_row(row: RerunCsvRow, *, in_scope: bool) -> dict[str, Any]:
    reasons = list(row.blocked_reasons) + list(row.warning_reasons)
    return {
        "row_index": row.row_index,
        "enabled": row.enabled,
        "status": _row_status(row, in_scope),
        "in_scope": in_scope,
        "source_path": row.source_path,
        "issue": row.issue_text,
        "bucket": row.bucket_text,
        "stage_mode": row.stage_mode,
        "original_mode": row.original_mode,
        "return_mode": row.return_mode,
        "lookup_title": _row_value(row.row, "lookup_title", "LookupTitle"),
        "relative_path": _row_value(row.row, "relative_path", "RelativePath"),
        "reason": "; ".join(reasons),
    }


def _recent_csv_entry(path: Path, *, label: str, source: str) -> dict[str, Any] | None:
    try:
        if not path.exists() or not path.is_file():
            return None
        stat = path.stat()
    except OSError:
        return None
    return {
        "label": label,
        "source": source,
        "path": str(path),
        "size_bytes": int(stat.st_size),
        "modified_at": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
    }


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

    latest = getattr(service, "latest_audit_csv", None) if service is not None else None
    if callable(latest):
        try:
            add(Path(latest(resolved, priority_only=False)), label="Latest audit CSV", source="latest_audit")
        except Exception:
            pass
        try:
            add(Path(latest(resolved, priority_only=True)), label="Latest priority audit CSV", source="latest_priority_audit")
        except Exception:
            pass

    for root, pattern, source in (
        (resolved.audit_reports_path, "audit_rerun_export_*.csv", "audit_rerun_export"),
        (_scoped_csv_root(resolved), "rerun_scoped_*.csv", "scoped_rerun"),
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
    stage_mode = _normalize_choice(request.get("stage_mode"), "copy")
    original_mode = _normalize_choice(request.get("original_mode"), "keep")
    return_mode = _normalize_choice(request.get("return_mode"), "park")
    scope = rerun_preview_scope_from_request(request)
    recent = recent_rerun_csv_candidates(resolved, service)

    if not csv_text:
        return _preview_error_payload("CSV path is required.", csv_text, stage_mode, original_mode, return_mode, scope, recent)

    csv_path = Path(csv_text)
    if not csv_path.exists() or not csv_path.is_file():
        return _preview_error_payload(f"CSV not found: {csv_path}", csv_text, stage_mode, original_mode, return_mode, scope, recent)

    try:
        fieldnames, raw_rows = read_rerun_csv_rows(csv_path)
    except Exception as exc:
        return _preview_error_payload(f"CSV could not be read: {exc}", csv_text, stage_mode, original_mode, return_mode, scope, recent)

    rows = _classify_rows(
        raw_rows,
        default_stage_mode=stage_mode,
        default_original_mode=original_mode,
        default_return_mode=return_mode,
    )
    scoped = scoped_rerun_rows(rows, scope)
    scoped_keys = {row.row_index for row in scoped}
    blocked_in_scope = sum(1 for row in scoped if row.blocked_reasons)
    unsafe_defaults = not rerun_modes_are_supported(stage_mode, original_mode, return_mode)
    preview_rows = [_preview_row(row, in_scope=row.row_index in scoped_keys) for row in rows[:scope.preview_limit]]
    warnings = _preview_warnings(rows, scoped, unsafe_defaults, fieldnames)
    status = _status_for_preview(
        csv_error="",
        unsafe_default_modes=unsafe_defaults,
        effective_rows=scoped,
        blocked_in_scope=blocked_in_scope,
    )
    return {
        "ok": status != "blocked",
        "command": RERUN_PREVIEW_COMMAND,
        "schema_version": RERUN_CSV_PREVIEW_SCHEMA_VERSION,
        "status": status,
        "severity": "error" if status == "blocked" else "warning" if status == "review" else "ok",
        "message": _preview_message(status, len(scoped)),
        "csv_path": str(csv_path),
        "fieldnames": fieldnames,
        "safe_modes": rerun_modes_are_supported(stage_mode, original_mode, return_mode),
        "stage_mode": stage_mode,
        "original_mode": original_mode,
        "return_mode": return_mode,
        "scope": _scope_mapping(scope),
        "counts": _preview_counts(rows, scoped, blocked_in_scope),
        "warnings": warnings,
        "errors": [
            item
            for item in warnings
            if status == "blocked" and ("blocked" in item or "No effective" in item or "missing source_path" in item)
        ],
        "rows": preview_rows,
        "preview_limit": scope.preview_limit,
        "recent_csvs": recent,
        "touches_media": False,
        "writes_queue": False,
        "writes_file_overrides": False,
    }


def _preview_error_payload(
    message: str,
    csv_path: str,
    stage_mode: str,
    original_mode: str,
    return_mode: str,
    scope: RerunPreviewScope,
    recent: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "ok": False,
        "command": RERUN_PREVIEW_COMMAND,
        "schema_version": RERUN_CSV_PREVIEW_SCHEMA_VERSION,
        "status": "blocked",
        "severity": "error",
        "message": message,
        "csv_path": csv_path,
        "fieldnames": [],
        "safe_modes": rerun_modes_are_supported(stage_mode, original_mode, return_mode),
        "stage_mode": stage_mode,
        "original_mode": original_mode,
        "return_mode": return_mode,
        "scope": _scope_mapping(scope),
        "counts": _empty_counts(),
        "warnings": [message],
        "errors": [message],
        "rows": [],
        "preview_limit": scope.preview_limit,
        "recent_csvs": recent,
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
        "missing_source_rows": 0,
        "warning_rows": 0,
    }


def _row_has_blocked_mode(row: RerunCsvRow) -> bool:
    return any("blocked source-mutating" in reason for reason in row.blocked_reasons)


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
        "missing_source_rows": sum(1 for row in rows if not row.source_path),
        "warning_rows": sum(1 for row in rows if row.warning_reasons),
    }


def _preview_warnings(rows: list[RerunCsvRow], scoped: list[RerunCsvRow], unsafe_defaults: bool, fieldnames: list[str]) -> list[str]:
    warnings: list[str] = []
    if not fieldnames:
        warnings.append("CSV has no header columns.")
    if unsafe_defaults:
        warnings.append("Selected default modes are blocked; only copy / keep / park can execute.")
    if not scoped:
        warnings.append("No effective scoped rows are available for rerun.")
    blocked = sum(1 for row in rows if _row_has_blocked_mode(row))
    if blocked:
        warnings.append(f"{blocked} row(s) have blocked source-mutating or in-place policy.")
    missing = sum(1 for row in rows if not row.source_path)
    if missing:
        warnings.append(f"{missing} row(s) are missing source_path.")
    duplicate = sum(1 for row in rows if row.duplicate_source)
    if duplicate:
        warnings.append(f"{duplicate} row(s) share a duplicate source_path.")
    disabled = sum(1 for row in rows if not row.enabled)
    if disabled:
        warnings.append(f"{disabled} row(s) are disabled in the CSV.")
    return warnings


def _scope_mapping(scope: RerunPreviewScope) -> dict[str, Any]:
    return {
        "enabled_only": scope.enabled_only,
        "skip_blocked": scope.skip_blocked,
        "skip_warning_rows": scope.skip_warning_rows,
        "first_n": scope.first_n,
        "issue_filter": scope.issue_filter,
        "bucket_filter": scope.bucket_filter,
        "preview_limit": scope.preview_limit,
    }


def _scoped_csv_root(resolved: ResolvedPaths) -> Path | None:
    if resolved.state_root is not None:
        return resolved.state_root / "Rerun" / "ScopedCsv"
    if resolved.local_base is not None:
        return resolved.local_base / "State" / "Rerun" / "ScopedCsv"
    return None


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
        or bool(scope.issue_filter)
        or bool(scope.bucket_filter)
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
    fieldnames, raw_rows = read_rerun_csv_rows(csv_path)
    rows = _classify_rows(
        raw_rows,
        default_stage_mode=str(payload.get("stage_mode") or "copy"),
        default_original_mode=str(payload.get("original_mode") or "keep"),
        default_return_mode=str(payload.get("return_mode") or "park"),
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
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    for row in scoped:
        writer.writerow({key: row.row.get(key, "") for key in fieldnames})
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
    "RERUN_PREVIEW_COMMAND",
    "materialize_scoped_rerun_csv",
    "read_rerun_csv_rows",
    "recent_rerun_csv_candidates",
    "request_needs_scoped_csv",
    "rerun_csv_preview_payload",
    "rerun_preview_scope_from_request",
    "scoped_rerun_rows",
]
