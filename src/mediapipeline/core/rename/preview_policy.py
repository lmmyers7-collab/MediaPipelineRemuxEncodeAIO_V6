"""Rename preview counts and selected-row helpers."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any
from collections.abc import Iterable, Mapping


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


def _rename_path_freshness(path: object) -> dict[str, Any]:
    value = Path(str(path or ""))
    evidence: dict[str, Any] = {"path": str(value)}
    try:
        stat = value.stat()
    except FileNotFoundError:
        evidence.update({"exists": False, "is_file": False, "size": None, "mtime_ns": None})
    except OSError as exc:
        evidence.update({"exists": None, "is_file": None, "size": None, "mtime_ns": None, "error": type(exc).__name__})
    else:
        evidence.update({"exists": True, "is_file": value.is_file(), "size": stat.st_size, "mtime_ns": stat.st_mtime_ns})
    return evidence


def rename_preview_fingerprint(rows: Iterable[Mapping[str, Any]]) -> str:
    """Hash the backend plan plus source/destination freshness evidence."""
    evidence: list[dict[str, Any]] = []
    for row in sorted(rows, key=lambda item: rename_selection_key(item.get("source", ""))):
        sidecar_moves = [dict(move) for move in row.get("sidecar_moves") or [] if isinstance(move, Mapping)]
        paths = [row.get("source"), row.get("destination")]
        for move in sidecar_moves:
            paths.extend((move.get("source"), move.get("destination")))
        evidence.append(
            {
                "source": str(row.get("source") or ""),
                "destination": str(row.get("destination") or ""),
                "mutation_root": str(row.get("mutation_root") or ""),
                "mode": str(row.get("mode") or ""),
                "rename_cleaning_policy_fingerprint": str(row.get("rename_cleaning_policy_fingerprint") or ""),
                "parsed_identity": (
                    dict(row["parsed_identity"])
                    if isinstance(row.get("parsed_identity"), Mapping)
                    else None
                ),
                "destination_identity_key": str(row.get("destination_identity_key") or ""),
                "target_name": str(row.get("target_name") or ""),
                "status": str(row.get("status") or ""),
                "errors": sorted(str(item) for item in row.get("errors") or []),
                "rename_sidecars": row.get("rename_sidecars") is True,
                "force_pipeline_name": row.get("force_pipeline_name") is True,
                "sidecar_moves": sidecar_moves,
                "path_authority": str(row.get("path_authority") or ""),
                "path_authority_status": str(row.get("path_authority_status") or ""),
                "path_authority_source_roots": sorted(str(item) for item in row.get("path_authority_source_roots") or []),
                "path_freshness": [_rename_path_freshness(path) for path in paths if str(path or "").strip()],
            }
        )
    payload = json.dumps(evidence, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


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


__all__ = [
    "rename_preview_counts",
    "rename_preview_count_by",
    "rename_preview_confidence_counts",
    "rename_preview_source_counts",
    "rename_preview_change_kind_counts",
    "rename_preview_warnings",
    "rename_preview_fingerprint",
    "selected_rename_sources",
    "rename_selection_key",
    "select_rename_plan_rows",
    "missing_rename_selection_warnings",
    "rename_blocker_error_lines",
]
