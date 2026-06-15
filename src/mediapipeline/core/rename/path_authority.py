"""Configured-root authority and undo manifest root helpers for rename."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable, Mapping

from mediapipeline.core.paths.layout import path_within_root
from mediapipeline.core.kernel.config_keys import KEY_OUTSOURCE

OUTSIDE_CONFIGURED_ROOTS_MESSAGE = "Rename apply includes path(s) outside configured media roots."
OUTSIDE_CONFIGURED_ROOTS_WARNING = (
    "Path is outside configured SourceMovies, SourceTV, or Outsource roots; standalone rename requires explicit outside-root confirmation."
)
UNSCOPED_OPERATOR_PATHS_MESSAGE = "Rename apply includes path(s) without configured media-root authority."


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


def rename_plan_unscoped_operator_paths(rows: Iterable[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    return [row for row in rows if str(row.get("path_authority") or "") == "unscoped_operator_path"]


def rename_request_allows_outside_configured_roots(request: Mapping[str, Any]) -> bool:
    return request.get("allow_outside_configured_roots") is True


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


__all__ = [
    "OUTSIDE_CONFIGURED_ROOTS_MESSAGE",
    "OUTSIDE_CONFIGURED_ROOTS_WARNING",
    "UNSCOPED_OPERATOR_PATHS_MESSAGE",
    "rename_request_paths",
    "rename_configured_media_roots_from_request",
    "rename_undo_manifest_root_from_request",
    "rename_undo_manifest_root_from_resolved",
    "rename_authority_fields_for_source",
    "annotate_rename_plan_path_authority",
    "rename_plan_outside_configured_roots",
    "rename_plan_unscoped_operator_paths",
    "rename_request_allows_outside_configured_roots",
    "rename_configured_media_roots_from_resolved",
]
