from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any
from collections.abc import Mapping, Sequence

from mediapipeline.core.kernel.contracts.base import ContractError
from mediapipeline.core.kernel.contracts.pending_publish import (
    PENDING_PUSH_MANIFEST_REQUIRED_ARRAY_FIELDS,
    PENDING_PUSH_MANIFEST_REQUIRED_TEXT_FIELDS,
    PENDING_PUSH_MANIFEST_SCHEMA_VERSION,
    PendingPushManifest,
)
from mediapipeline.core.repair_reconcile.dry_run_contract import *  # noqa: F403

def dry_run_command_name(candidate_command: str) -> str:
    return DRY_RUN_COMMAND_BY_CANDIDATE.get(candidate_command, f"{candidate_command}_dry_run")


def repair_reconcile_dry_run_fingerprint(payload: Mapping[str, Any]) -> str:
    """Stable operator-confirmation fingerprint for a backend dry-run payload."""

    selected = {
        "schema_version": payload.get("schema_version"),
        "candidate_command": payload.get("candidate_command"),
        "scope": payload.get("scope"),
        "selected_row_keys": payload.get("selected_row_keys") or [],
        "precondition_results": payload.get("precondition_results") or [],
        "diff_summary": payload.get("diff_summary") or {},
        "would_write_paths": payload.get("would_write_paths") or [],
        "would_move_paths": payload.get("would_move_paths") or [],
        "would_delete_paths": payload.get("would_delete_paths") or [],
        "safe_to_apply": bool(payload.get("safe_to_apply")),
    }
    encoded = json.dumps(selected, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8", errors="replace")).hexdigest()


def normalize_repair_reconcile_scope(value: object, row_key: object | None = None) -> str:
    scope = str(value or "").strip().casefold()
    if scope in {"all", "selected"}:
        return scope
    if str(row_key or "").strip():
        return "selected"
    return "all"


def bounded_repair_reconcile_limit(value: object, *, default: int = 100, maximum: int = 500) -> int:
    try:
        parsed = int(str(value)) if value not in (None, "") else default
    except (TypeError, ValueError):
        parsed = default
    return max(1, min(maximum, parsed))


def requested_row_key(request: Mapping[str, Any]) -> str:
    return str(request.get("row_key") or "").strip()


def _precondition(key: str, status: str, evidence: str, action: str) -> dict[str, str]:
    return {
        "key": key,
        "status": status,
        "evidence": evidence,
        "action": action,
    }


def active_work_precondition(block_message: str) -> dict[str, str]:
    if block_message:
        return _precondition(
            "pipeline_idle",
            "blocked",
            block_message,
            "Wait for active MediaPipeline work to finish before designing a mutation route.",
        )
    return _precondition(
        "pipeline_idle",
        "ok",
        "No active MediaPipeline work was reported by backend close-readiness guards.",
        "No operator action required for this dry-run.",
    )


def backend_path_authority_precondition(domain: str) -> dict[str, str]:
    return _precondition(
        "backend_path_authority",
        "ok",
        f"{domain} paths are derived from backend preview/scan evidence; request payload paths are not accepted.",
        "Do not add client-submitted path, patch, destination, manifest, or sidecar fields.",
    )


def _required_would_not_touch() -> dict[str, str]:
    return {
        "source_media": "no read/write/delete/rename/move",
        "scratch_media": "no create/delete/cleanup",
        "output_media": "no create/delete/overwrite/publish",
        "pending_payload_bytes": "no move/delete/drain/publish",
        "completed_manifest": "not written by dry-run",
        "pending_manifest": "not written by dry-run",
        "sidecar_json": "not written by dry-run",
        "command_journal": "suppressed for dry-run preview only",
    }


def _startup_would_not_touch() -> dict[str, str]:
    result = _required_would_not_touch()
    result.update(
        {
            "active_jobs": "read-only scan; not reconciled, killed, archived, or rewritten",
            "sqlite_mirror": "read-only metadata/count check; no migration, rebuild, vacuum, or write",
            "pending_drain_summary": "not written by dry-run",
            "failure_markers": "not cleared by dry-run",
        }
    )
    return result


def _base_payload(
    *,
    candidate_command: str,
    scope: str,
    selected_row_keys: list[str],
    preconditions: list[dict[str, str]],
    request: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": REPAIR_RECONCILE_DRY_RUN_SCHEMA_VERSION,
        "candidate_command": candidate_command,
        "dry_run_only": True,
        "effect": REPAIR_RECONCILE_EFFECT_NONE,
        "scope": scope,
        "selected_row_keys": selected_row_keys,
        "precondition_results": preconditions,
        "diff_summary": {
            "schema_version": "desktop_repair_reconcile_diff_summary.v1",
            "candidate_count": 0,
            "blocked_count": 0,
            "review_count": 0,
            "rows": [],
            "summary_lines": [],
        },
        "would_write_paths": [],
        "would_move_paths": [],
        "would_delete_paths": [],
        "would_not_touch": _required_would_not_touch(),
        "safe_to_apply": False,
        "mutation_route_available": True,
        "apply_route_available": True,
        "operator_confirmation_scope": "A confirmed apply route exists but will reject unless safe_to_apply is true and the dry_run_fingerprint matches.",
        "suppress_command_journal": True,
        "rollback_preview": {
            "backup_required_for_future_mutation": True,
            "backup_created_by_dry_run": False,
            "temp_file_created_by_dry_run": False,
            "journal_recorded_by_dry_run": False,
        },
        "request_summary": {
            "scope": scope,
            "row_key_present": bool(requested_row_key(request)),
            "limit": bounded_repair_reconcile_limit(request.get("limit")),
            "reason_present": bool(str(request.get("reason") or "").strip()),
        },
    }



def _row_key(row: Mapping[str, Any]) -> str:
    return str(row.get("row_key") or "").strip()


def _select_rows(
    rows: list[dict[str, Any]],
    *,
    scope: str,
    row_key: str,
    limit: int,
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    preconditions: list[dict[str, str]] = []
    if scope == "selected":
        selected = [row for row in rows if _row_key(row).casefold() == row_key.casefold()]
        if not row_key:
            preconditions.append(
                _precondition(
                    "selected_row_key_present",
                    "blocked",
                    "scope=selected requires row_key.",
                    "Submit row_key for selected dry-runs.",
                )
            )
        elif not selected:
            preconditions.append(
                _precondition(
                    "selected_row_exists",
                    "blocked",
                    f"Selected row_key was not found in the loaded backend evidence: {row_key}",
                    "Refresh the preview and select an existing backend row.",
                )
            )
        else:
            preconditions.append(
                _precondition(
                    "selected_row_exists",
                    "ok",
                    f"Selected backend row exists: {row_key}",
                    "No operator action required for this dry-run.",
                )
            )
        return selected[:1], preconditions
    return rows[:limit], [
        _precondition(
            "scope_rows_loaded",
            "ok",
            f"{min(len(rows), limit)} loaded backend row(s) selected from {len(rows)} available row(s).",
            "Use scope=selected with row_key to narrow a future review.",
        )
    ]


def _path_exists_text(path_text: str) -> tuple[bool | None, str]:
    if not path_text:
        return None, "path not reported"
    try:
        return Path(path_text).exists(), path_text
    except OSError as exc:
        return None, f"{path_text} ({exc})"


def _read_json_object(path_text: str) -> tuple[dict[str, Any] | None, str]:
    if not path_text:
        return None, "path not reported"
    try:
        path = Path(path_text)
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return None, str(exc)
    if not isinstance(payload, dict):
        return None, "JSON root is not an object."
    return payload, ""


def _blocked(preconditions: Sequence[Mapping[str, Any]]) -> bool:
    return any(str(row.get("status") or "").casefold() == "blocked" for row in preconditions)


def _set_summary(
    payload: dict[str, Any],
    *,
    rows: list[dict[str, Any]],
    summary_lines: list[str],
    would_write_paths: list[dict[str, str]] | None = None,
    would_move_paths: list[dict[str, str]] | None = None,
    would_delete_paths: list[dict[str, str]] | None = None,
    require_mutation_candidate: bool = True,
) -> dict[str, Any]:
    would_write = list(would_write_paths or [])
    would_move = list(would_move_paths or [])
    would_delete = list(would_delete_paths or [])
    payload["would_write_paths"] = would_write
    payload["would_move_paths"] = would_move
    payload["would_delete_paths"] = would_delete
    candidate_count = sum(1 for row in rows if str(row.get("status") or "").casefold() == "candidate")
    blocked_count = sum(1 for row in rows if str(row.get("status") or "").casefold() == "blocked")
    review_count = sum(1 for row in rows if str(row.get("status") or "").casefold() == "review")
    payload["diff_summary"] = {
        "schema_version": "desktop_repair_reconcile_diff_summary.v1",
        "candidate_count": candidate_count,
        "blocked_count": blocked_count,
        "review_count": review_count,
        "rows": rows,
        "summary_lines": summary_lines,
    }
    preconditions = payload["precondition_results"]
    no_blockers = not _blocked(preconditions) and blocked_count == 0
    has_selected_candidate = any(str(row.get("status") or "").casefold() == "candidate" for row in rows)
    has_mutation_candidate = bool(
        (has_selected_candidate and (would_write or would_move or would_delete)) or not require_mutation_candidate
    )
    payload["safe_to_apply"] = bool(no_blockers and has_mutation_candidate)
    payload["dry_run_fingerprint"] = repair_reconcile_dry_run_fingerprint(payload)
    if payload["safe_to_apply"]:
        payload["operator_confirmation_scope"] = "Submit the selected row key and dry_run_fingerprint to the matching confirmed apply route."
    return payload



__all__ = [
    "dry_run_command_name",
    "repair_reconcile_dry_run_fingerprint",
    "normalize_repair_reconcile_scope",
    "bounded_repair_reconcile_limit",
    "requested_row_key",
    "_precondition",
    "active_work_precondition",
    "backend_path_authority_precondition",
    "_required_would_not_touch",
    "_startup_would_not_touch",
    "_base_payload",
    "_row_key",
    "_select_rows",
    "_path_exists_text",
    "_read_json_object",
    "_blocked",
    "_set_summary",
]
