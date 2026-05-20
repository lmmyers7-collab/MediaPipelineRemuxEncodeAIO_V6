from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

from ..config_keys import KEY_OUTSOURCE
from ..service_path_layout import path_within_root
from ..service_rename_plan_policy import normalize_rename_template_preset, rename_template_catalog
from .dto import CommandResult, json_safe

RENAME_APPLY_COMMAND = "rename.apply"
RENAME_REFRESH_HINT = "rename"
CONFIRM_RENAME_APPLY_MESSAGE = "Rename apply requires explicit confirmation."
CONFIRM_RENAME_APPLY_WARNING = "confirm_apply must be true."
NO_RENAME_SELECTION_MESSAGE = "Select one or more rename rows before applying."
NO_RENAME_SELECTION_WARNING = "No selected_sources were provided."
MISSING_RENAME_SELECTION_MESSAGE = "One or more selected rename rows are no longer in the current plan."
RENAME_APPLY_SERVICE_UNAVAILABLE_MESSAGE = "Rename apply service is not available."
RENAME_APPLY_BUSY_MESSAGE = "Rename apply blocked because another rename apply command is already in progress."
OUTSIDE_CONFIGURED_ROOTS_MESSAGE = "Rename apply includes path(s) outside configured media roots."
OUTSIDE_CONFIGURED_ROOTS_WARNING = (
    "Path is outside configured SourceMovies, SourceTV, or Outsource roots; standalone rename requires explicit outside-root confirmation."
)


def dict_bool(value: object) -> dict[str, bool]:
    if not isinstance(value, dict):
        return {}
    return {str(key): bool(item) for key, item in value.items()}


def dict_str(value: object) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    return {str(key): str(item) for key, item in value.items()}


def dict_terms(value: object, parser: Callable[[str], list[str]] | None = None) -> dict[str, list[str]]:
    if not isinstance(value, dict):
        return {}
    result: dict[str, list[str]] = {}
    for key, item in value.items():
        if isinstance(item, list):
            terms = [str(term).strip() for term in item if str(term or "").strip()]
        else:
            raw_terms = str(item or "")
            if callable(parser):
                terms = [str(term).strip() for term in parser(raw_terms) if str(term or "").strip()]
            else:
                terms = [term.strip() for term in raw_terms.replace(";", ",").replace("\n", ",").split(",") if term.strip()]
        seen: set[str] = set()
        deduped: list[str] = []
        for term in terms:
            term_key = term.casefold()
            if term_key in seen:
                continue
            seen.add(term_key)
            deduped.append(term)
        result[str(key)] = deduped
    return result


def rename_preview_counts(rows: Iterable[Mapping[str, Any]]) -> dict[str, int]:
    row_list = list(rows)
    return {
        "total": len(row_list),
        "ready": sum(1 for row in row_list if row.get("status") == "ready"),
        "match": sum(1 for row in row_list if row.get("status") == "match"),
        "warning": sum(1 for row in row_list if row.get("status") == "warning"),
        "blocked": sum(1 for row in row_list if row.get("status") == "blocked"),
    }


def rename_preview_count_by(
    rows: Iterable[Mapping[str, Any]],
    key: str,
    *,
    default: str = "unknown",
) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        value = str(row.get(key) or default).strip() or default
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def rename_preview_confidence_counts(rows: Iterable[Mapping[str, Any]]) -> dict[str, int]:
    return rename_preview_count_by(rows, "confidence")


def rename_preview_source_counts(rows: Iterable[Mapping[str, Any]]) -> dict[str, int]:
    return rename_preview_count_by(rows, "preview_source")


def rename_preview_change_kind_counts(rows: Iterable[Mapping[str, Any]]) -> dict[str, int]:
    return rename_preview_count_by(rows, "change_kind")


def rename_preview_warnings(rows: Iterable[Mapping[str, Any]]) -> list[str]:
    return sorted({str(warning) for row in rows for warning in row.get("warnings") or []})


def selected_rename_sources(request: Mapping[str, Any]) -> list[str]:
    return [str(path).strip() for path in request.get("selected_sources") or [] if str(path or "").strip()]


def rename_selection_key(path: object) -> str:
    return str(Path(str(path))).casefold()


def select_rename_plan_rows(
    plan: Iterable[Mapping[str, Any]],
    selected_sources: Iterable[str],
) -> tuple[list[Mapping[str, Any]], list[str]]:
    selected_keys = {rename_selection_key(path) for path in selected_sources}
    selected_plan = [row for row in plan if rename_selection_key(row.get("source", "")) in selected_keys]
    selected_plan_keys = {rename_selection_key(row.get("source", "")) for row in selected_plan}
    missing = sorted(selected_keys.difference(selected_plan_keys))
    return selected_plan, missing


def missing_rename_selection_warnings(missing: Iterable[str]) -> list[str]:
    return [f"Missing selected source: {path}" for path in missing]


def rename_blocker_error_lines(rows: Iterable[Mapping[str, Any]]) -> list[str]:
    return [
        f"{Path(str(row.get('source') or '')).name}: {'; '.join(str(item) for item in row.get('errors') or [])}"
        for row in rows
    ]


def rename_apply_confirmation_required_result() -> CommandResult:
    return CommandResult(
        command=RENAME_APPLY_COMMAND,
        ok=False,
        message=CONFIRM_RENAME_APPLY_MESSAGE,
        severity="warning",
        warnings=[CONFIRM_RENAME_APPLY_WARNING],
        refresh_hint=RENAME_REFRESH_HINT,
    )


def rename_apply_no_selection_result() -> CommandResult:
    return CommandResult(
        command=RENAME_APPLY_COMMAND,
        ok=False,
        message=NO_RENAME_SELECTION_MESSAGE,
        severity="warning",
        warnings=[NO_RENAME_SELECTION_WARNING],
        refresh_hint=RENAME_REFRESH_HINT,
    )


def rename_apply_service_unavailable_result() -> CommandResult:
    return CommandResult(
        command=RENAME_APPLY_COMMAND,
        ok=False,
        message=RENAME_APPLY_SERVICE_UNAVAILABLE_MESSAGE,
        severity="error",
        errors=[RENAME_APPLY_SERVICE_UNAVAILABLE_MESSAGE],
        refresh_hint=RENAME_REFRESH_HINT,
    )


def rename_apply_busy_result(message: str = RENAME_APPLY_BUSY_MESSAGE) -> CommandResult:
    return CommandResult(
        command=RENAME_APPLY_COMMAND,
        ok=False,
        message=message,
        severity="warning",
        warnings=[message],
        refresh_hint=RENAME_REFRESH_HINT,
    )


def rename_plan_build_exception_result(exc: Exception) -> CommandResult:
    return CommandResult(
        command=RENAME_APPLY_COMMAND,
        ok=False,
        message=f"Rename plan could not be built: {exc}",
        severity="error",
        errors=[str(exc)],
        refresh_hint=RENAME_REFRESH_HINT,
    )


def rename_apply_missing_selection_result(missing: Iterable[str]) -> CommandResult:
    return CommandResult(
        command=RENAME_APPLY_COMMAND,
        ok=False,
        message=MISSING_RENAME_SELECTION_MESSAGE,
        severity="warning",
        warnings=missing_rename_selection_warnings(missing),
        refresh_hint=RENAME_REFRESH_HINT,
    )


def rename_apply_blockers_result(blockers: Iterable[Mapping[str, Any]]) -> CommandResult:
    blocker_list = list(blockers)
    return CommandResult(
        command=RENAME_APPLY_COMMAND,
        ok=False,
        message=f"Rename selection has {len(blocker_list)} blocked row(s).",
        severity="error",
        errors=rename_blocker_error_lines(blocker_list),
        refresh_hint=RENAME_REFRESH_HINT,
    )


def rename_apply_outside_configured_roots_result(rows: Iterable[Mapping[str, Any]]) -> CommandResult:
    row_list = list(rows)
    warnings = [OUTSIDE_CONFIGURED_ROOTS_MESSAGE]
    warnings.extend(
        f"Outside configured roots: {Path(str(row.get('source') or '')).name} ({row.get('source') or ''})"
        for row in row_list[:8]
    )
    if len(row_list) > 8:
        warnings.append(f"...and {len(row_list) - 8} more outside-root row(s).")
    warnings.append("Set allow_outside_configured_roots only after operator review of the exact source and destination paths.")
    return CommandResult(
        command=RENAME_APPLY_COMMAND,
        ok=False,
        message=OUTSIDE_CONFIGURED_ROOTS_MESSAGE,
        severity="warning",
        warnings=warnings,
        refresh_hint=RENAME_REFRESH_HINT,
    )


def rename_apply_exception_result(exc: Exception) -> CommandResult:
    return CommandResult(
        command=RENAME_APPLY_COMMAND,
        ok=False,
        message=f"Rename apply failed: {exc}",
        severity="error",
        errors=[str(exc)],
        refresh_hint=RENAME_REFRESH_HINT,
    )


def rename_apply_progress_payload(summary: Mapping[str, Any], *, renamed: int) -> dict[str, Any]:
    selected = int(summary.get("selected") or 0)
    unchanged = int(summary.get("unchanged") or 0)
    sidecars = int(summary.get("sidecars") or 0)
    media_operations = int(summary.get("media_operations") or 0)
    sidecar_operations = int(summary.get("sidecar_operations") or 0)
    percent = 100.0 if selected <= 0 else max(0.0, min(100.0, round((renamed / selected) * 100.0, 1)))
    detail = (
        f"{renamed} renamed / {selected} planned"
        f"; unchanged {unchanged}; media ops {media_operations}; sidecar ops {sidecar_operations}; sidecars {sidecars}"
    )
    updated_at = datetime.now().isoformat(timespec="seconds")
    bar = {
        "id": "rename_apply",
        "label": "Rename apply",
        "mode": "determinate",
        "percent": percent,
        "status": "complete",
        "detail": detail,
        "source": "rename.apply",
        "updated_at": updated_at,
        "stale": False,
    }
    return {
        "schema_version": "desktop_rename_apply_progress.v1",
        "status": "complete",
        "selected": selected,
        "renamed": renamed,
        "unchanged": unchanged,
        "sidecars": sidecars,
        "media_operations": media_operations,
        "sidecar_operations": sidecar_operations,
        "updated_at": updated_at,
        "progress_bars": [bar],
    }


def rename_apply_success_result(summary: Mapping[str, Any], *, renamed: int) -> CommandResult:
    rows = [json_safe(dict(row)) for row in summary.get("rows") or [] if isinstance(row, dict)]
    progress = rename_apply_progress_payload(summary, renamed=renamed)
    return CommandResult(
        command=RENAME_APPLY_COMMAND,
        ok=True,
        message=f"Rename applied: {renamed} file(s) renamed.",
        severity="info",
        refresh_hint=RENAME_REFRESH_HINT,
        data={
            "selected": int(summary.get("selected") or len(rows)),
            "renamed": renamed,
            "unchanged": int(summary.get("unchanged") or 0),
            "sidecars": int(summary.get("sidecars") or 0),
            "media_operations": int(summary.get("media_operations") or 0),
            "sidecar_operations": int(summary.get("sidecar_operations") or 0),
            "rows": rows,
            "undo_manifest": str(summary.get("undo_manifest") or ""),
            "applied_count": len(rows),
            "rename_progress": progress,
            "progress_bars": progress["progress_bars"],
        },
    )


def rename_request_paths(request: Mapping[str, Any]) -> list[Path]:
    return [Path(str(path)) for path in request.get("paths") or [] if str(path or "").strip()]


def rename_configured_media_roots_from_request(request: Mapping[str, Any]) -> list[Path]:
    roots: list[Path] = []
    raw_roots = request.get("_configured_media_roots")
    if isinstance(raw_roots, list):
        for item in raw_roots:
            text = str(item or "").strip()
            if text:
                roots.append(Path(text))
    return roots


def rename_undo_manifest_root_from_request(request: Mapping[str, Any]) -> Path | None:
    text = str(request.get("_rename_undo_manifest_root") or "").strip()
    return Path(text) if text else None


def rename_undo_manifest_root_from_resolved(resolved: Any) -> Path | None:
    state_root = getattr(resolved, "state_root", None)
    if state_root:
        return Path(state_root) / "RenameUndo"
    local_base = getattr(resolved, "local_base", None)
    if local_base:
        return Path(local_base) / "State" / "RenameUndo"
    return None


def rename_authority_fields_for_source(source: object, configured_roots: Iterable[Path]) -> dict[str, Any]:
    roots = [root for root in configured_roots if str(root or "").strip()]
    if not roots:
        return {
            "path_authority": "unscoped_operator_path",
            "path_authority_status": "review",
            "path_authority_root_count": 0,
            "path_authority_message": "No configured media roots were available to the rename authority check.",
        }
    source_path = Path(str(source or ""))
    if any(path_within_root(source_path, root) for root in roots):
        return {
            "path_authority": "configured_media_root",
            "path_authority_status": "ready",
            "path_authority_root_count": len(roots),
            "path_authority_message": "Source is inside a configured media root.",
        }
    return {
        "path_authority": "outside_configured_roots",
        "path_authority_status": "review",
        "path_authority_root_count": len(roots),
        "path_authority_message": OUTSIDE_CONFIGURED_ROOTS_WARNING,
    }


def annotate_rename_plan_path_authority(
    rows: Iterable[Mapping[str, Any]],
    configured_roots: Iterable[Path],
) -> list[dict[str, Any]]:
    annotated: list[dict[str, Any]] = []
    roots = list(configured_roots)
    for raw_row in rows:
        row = dict(raw_row)
        fields = rename_authority_fields_for_source(row.get("source"), roots)
        row.update(fields)
        if fields["path_authority"] == "outside_configured_roots":
            warnings = [str(item) for item in row.get("warnings") or []]
            if OUTSIDE_CONFIGURED_ROOTS_WARNING not in warnings:
                warnings.append(OUTSIDE_CONFIGURED_ROOTS_WARNING)
            row["warnings"] = warnings
            if str(row.get("status") or "").casefold() in {"ready", "match"}:
                row["status"] = "warning"
            if str(row.get("confidence") or "").casefold() not in {"blocked", "review"}:
                row["confidence"] = "review"
            reasons = [str(item) for item in row.get("confidence_reasons") or []]
            reason = "Outside configured media roots; requires explicit standalone rename confirmation."
            if reason not in reasons:
                reasons.append(reason)
            row["confidence_reasons"] = reasons
        annotated.append(row)
    return annotated


def rename_plan_outside_configured_roots(rows: Iterable[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    return [row for row in rows if str(row.get("path_authority") or "") == "outside_configured_roots"]


def rename_request_allows_outside_configured_roots(request: Mapping[str, Any]) -> bool:
    return bool(request.get("allow_outside_configured_roots", False))


def rename_configured_media_roots_from_resolved(resolved: object) -> list[str]:
    roots: list[str] = []
    for attr in ("source_movies", "source_tv"):
        value = getattr(resolved, attr, None)
        if value is not None and str(value).strip():
            roots.append(str(value))
    config_data = getattr(resolved, "config_data", None)
    if isinstance(config_data, Mapping):
        outsource = config_data.get(KEY_OUTSOURCE)
        if outsource is not None and str(outsource).strip():
            roots.append(str(outsource))
    seen: set[str] = set()
    deduped: list[str] = []
    for root in roots:
        key = root.casefold()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(root)
    return deduped


def remove_terms_from_request(
    request: Mapping[str, Any],
    parser: Callable[[str], list[str]] | None = None,
) -> list[str]:
    remove_terms = request.get("remove_terms")
    if isinstance(remove_terms, list):
        return [str(item) for item in remove_terms]
    raw_terms = str(request.get("remove_terms_text") or "")
    if callable(parser) and raw_terms:
        return [str(item) for item in parser(raw_terms)]
    return []


def rename_plan_kwargs_from_request(
    request: Mapping[str, Any],
    *,
    parse_remove_terms: Callable[[str], list[str]] | None = None,
) -> dict[str, Any]:
    return {
        "mode": str(request.get("mode") or "tv"),
        "show_name": str(request.get("show_name") or ""),
        "season_value": request.get("season", request.get("season_value", "S01")),
        "start_episode_value": request.get("start_episode", request.get("start_episode_value", "E01")),
        "movie_title": str(request.get("movie_title") or ""),
        "movie_year": str(request.get("movie_year") or ""),
        "remove_terms": remove_terms_from_request(request, parse_remove_terms),
        "movie_filter_options": dict_bool(request.get("movie_filter_options")),
        "movie_filter_terms": dict_terms(request.get("movie_filter_terms"), parse_remove_terms)
        if bool(request.get("movie_filter_terms_enabled", False))
        else {},
        "final_name_overrides": dict_str(request.get("final_name_overrides")),
        "rename_sidecars": bool(request.get("rename_sidecars", True)),
        "force_pipeline_name": bool(request.get("force_pipeline_name", False)),
        "force_pipeline_name_overrides": dict_bool(request.get("force_pipeline_name_overrides")),
        "powershell_host": str(request.get("powershell_host") or "") or None,
        "use_pipeline_naming_preview": bool(request.get("use_pipeline_naming_preview", False)),
        "template_preset": str(request.get("template_preset") or ""),
    }

__all__ = [
    "RENAME_APPLY_COMMAND",
    "RENAME_REFRESH_HINT",
    "CONFIRM_RENAME_APPLY_MESSAGE",
    "CONFIRM_RENAME_APPLY_WARNING",
    "NO_RENAME_SELECTION_MESSAGE",
    "NO_RENAME_SELECTION_WARNING",
    "MISSING_RENAME_SELECTION_MESSAGE",
    "RENAME_APPLY_SERVICE_UNAVAILABLE_MESSAGE",
    "RENAME_APPLY_BUSY_MESSAGE",
    "OUTSIDE_CONFIGURED_ROOTS_MESSAGE",
    "OUTSIDE_CONFIGURED_ROOTS_WARNING",
    "dict_bool",
    "dict_str",
    "dict_terms",
    "rename_preview_counts",
    "rename_preview_count_by",
    "rename_preview_confidence_counts",
    "rename_preview_source_counts",
    "rename_preview_change_kind_counts",
    "rename_preview_warnings",
    "selected_rename_sources",
    "rename_selection_key",
    "select_rename_plan_rows",
    "missing_rename_selection_warnings",
    "rename_blocker_error_lines",
    "rename_apply_confirmation_required_result",
    "rename_apply_no_selection_result",
    "rename_apply_service_unavailable_result",
    "rename_apply_busy_result",
    "rename_plan_build_exception_result",
    "rename_apply_missing_selection_result",
    "rename_apply_blockers_result",
    "rename_apply_outside_configured_roots_result",
    "rename_apply_exception_result",
    "rename_apply_progress_payload",
    "rename_apply_success_result",
    "rename_request_paths",
    "rename_configured_media_roots_from_request",
    "rename_undo_manifest_root_from_request",
    "rename_undo_manifest_root_from_resolved",
    "rename_authority_fields_for_source",
    "annotate_rename_plan_path_authority",
    "rename_plan_outside_configured_roots",
    "rename_request_allows_outside_configured_roots",
    "rename_configured_media_roots_from_resolved",
    "remove_terms_from_request",
    "rename_plan_kwargs_from_request",
]
