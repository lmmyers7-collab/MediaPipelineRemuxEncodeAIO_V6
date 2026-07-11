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
from mediapipeline.core.repair_reconcile.dry_run_support import *  # noqa: F403

def completed_manifest_reconcile_dry_run(
    *,
    preview: Mapping[str, Any],
    resolved: Any,
    request: Mapping[str, Any],
    base_preconditions: list[dict[str, str]],
) -> dict[str, Any]:
    scope = normalize_repair_reconcile_scope(request.get("scope"), request.get("row_key"))
    limit = bounded_repair_reconcile_limit(request.get("limit"))
    row_key = requested_row_key(request)
    rows = [dict(row) for row in preview.get("rows") or [] if isinstance(row, Mapping)]
    selected_rows, selection_preconditions = _select_rows(rows, scope=scope, row_key=row_key, limit=limit)
    selected_keys = [_row_key(row) for row in selected_rows if _row_key(row)]
    preconditions = [*base_preconditions, backend_path_authority_precondition("completed"), *selection_preconditions]
    manifest_path = str(getattr(resolved, "completed_manifest_path", "") or preview.get("source") or "")
    manifest_error = str(preview.get("manifest_error") or "").strip()
    parse_health_value = preview.get("parse_health")
    parse_health: dict[str, Any] = dict(parse_health_value) if isinstance(parse_health_value, Mapping) else {}
    skipped_manifest_rows = max(0, int(parse_health.get("skipped_count") or 0))
    if manifest_error:
        preconditions.append(
            _precondition(
                "completed_manifest_readable",
                "blocked",
                manifest_error,
                "Repair the completed manifest read error before designing a mutation.",
            )
        )
    else:
        preconditions.append(
            _precondition(
                "completed_manifest_readable",
                "ok" if manifest_path else "review",
                manifest_path or "completed manifest path is not reported",
                "Use backend-resolved completed manifest evidence only.",
            )
        )
    if skipped_manifest_rows:
        recent_errors = [
            str(row.get("line_identifier") or "unknown")
            for row in parse_health.get("recent_errors") or []
            if isinstance(row, Mapping)
        ]
        preconditions.append(
            _precondition(
                "completed_manifest_parse_health",
                "blocked",
                f"{skipped_manifest_rows} malformed completed manifest row(s) were omitted; recent identifiers: {', '.join(recent_errors) or 'not reported'}.",
                "Repair or restore the append-only manifest before designing a reconcile mutation.",
            )
        )
    else:
        preconditions.append(
            _precondition(
                "completed_manifest_parse_health",
                "ok",
                "No malformed rows were reported in the loaded completed-manifest scope.",
                "Continue to treat row caps and parse-health scope as explicit evidence limits.",
            )
        )
    payload = _base_payload(
        candidate_command=COMPLETED_RECONCILE_MANIFEST_COMMAND,
        scope=scope,
        selected_row_keys=selected_keys,
        preconditions=preconditions,
        request=request,
    )
    diff_rows: list[dict[str, Any]] = []
    would_write: list[dict[str, str]] = []
    for row in selected_rows:
        issues = [str(issue) for issue in row.get("consistency_issues") or [] if str(issue).strip()]
        relevant = [issue for issue in issues if issue in {"manifest_missing_output_path", "output_sidecar_mismatch"}]
        output_path = str(row.get("output_path") or "").strip()
        output_exists = row.get("output_exists")
        if "missing_output" in issues or output_exists is False:
            diff_rows.append(
                {
                    "row_key": _row_key(row),
                    "status": "blocked",
                    "action": "completed_manifest_reconcile",
                    "reasons": sorted(set(issues or ["missing_output"])),
                    "safe_next_action": "Resolve missing completed output before any manifest repair design.",
                }
            )
            preconditions.append(
                _precondition(
                    f"completed_row_output_exists:{_row_key(row)}",
                    "blocked",
                    output_path or "output path not reported",
                    "Do not rewrite completed manifest evidence while the output is missing.",
                )
            )
            continue
        if not relevant:
            diff_rows.append(
                {
                    "row_key": _row_key(row),
                    "status": "unchanged",
                    "action": "completed_manifest_reconcile",
                    "reasons": issues,
                    "safe_next_action": "No completed manifest reconcile candidate detected in this loaded row.",
                }
            )
            continue
        diff_rows.append(
            {
                "row_key": _row_key(row),
                "status": "candidate",
                "action": "completed_manifest_reconcile",
                "reasons": relevant,
                "current": {
                    "manifest_output_path": str(row.get("manifest_output_path") or ""),
                    "manifest_output_file": str(row.get("manifest_output_file") or ""),
                    "sidecar_path": str(row.get("sidecar_path") or ""),
                },
                "proposed": {
                    "output_path": output_path,
                    "output_file": str(row.get("output_file") or Path(output_path).name if output_path else ""),
                    "expected_sidecar_path": str(row.get("expected_sidecar_path") or ""),
                },
                "safe_next_action": "Review the dry-run diff, then submit the fingerprint to the matching confirmed apply route.",
            }
        )
    if manifest_path and any(row.get("status") == "candidate" for row in diff_rows):
        would_write.append({"path": manifest_path, "reason": "future completed manifest reconcile mutation would rewrite affected row fields"})
    return _set_summary(
        payload,
        rows=diff_rows,
        summary_lines=[
            f"Completed manifest dry-run reviewed {len(selected_rows)} loaded completed row(s).",
            "No completed manifest, sidecar, output, source, or scratch file was written.",
        ],
        would_write_paths=would_write,
    )


def completed_sidecar_metadata_repair_dry_run(
    *,
    preview: Mapping[str, Any],
    request: Mapping[str, Any],
    base_preconditions: list[dict[str, str]],
) -> dict[str, Any]:
    scope = normalize_repair_reconcile_scope(request.get("scope"), request.get("row_key"))
    limit = bounded_repair_reconcile_limit(request.get("limit"))
    row_key = requested_row_key(request)
    rows = [dict(row) for row in preview.get("rows") or [] if isinstance(row, Mapping)]
    selected_rows, selection_preconditions = _select_rows(rows, scope=scope, row_key=row_key, limit=limit)
    selected_keys = [_row_key(row) for row in selected_rows if _row_key(row)]
    preconditions = [*base_preconditions, backend_path_authority_precondition("completed"), *selection_preconditions]
    payload = _base_payload(
        candidate_command=COMPLETED_REPAIR_SIDECAR_METADATA_COMMAND,
        scope=scope,
        selected_row_keys=selected_keys,
        preconditions=preconditions,
        request=request,
    )
    diff_rows: list[dict[str, Any]] = []
    would_write: list[dict[str, str]] = []
    for row in selected_rows:
        key = _row_key(row)
        sidecar_path = str(row.get("sidecar_path") or "").strip()
        exists, evidence = _path_exists_text(sidecar_path)
        if exists is not True:
            diff_rows.append(
                {
                    "row_key": key,
                    "status": "blocked",
                    "action": "completed_sidecar_metadata_repair",
                    "sidecar_path": sidecar_path,
                    "reasons": ["missing_sidecar"],
                    "safe_next_action": "Restore or regenerate the backend-selected sidecar before metadata repair.",
                }
            )
            preconditions.append(
                _precondition(
                    f"completed_sidecar_readable:{key}",
                    "blocked",
                    evidence,
                    "Missing sidecars are review evidence only in this dry-run.",
                )
            )
            continue
        sidecar, error = _read_json_object(sidecar_path)
        if sidecar is None:
            diff_rows.append(
                {
                    "row_key": key,
                    "status": "blocked",
                    "action": "completed_sidecar_metadata_repair",
                    "sidecar_path": sidecar_path,
                    "reasons": ["unreadable_sidecar"],
                    "error": error,
                    "safe_next_action": "Fix sidecar JSON readability before metadata repair.",
                }
            )
            preconditions.append(
                _precondition(
                    f"completed_sidecar_readable:{key}",
                    "blocked",
                    error,
                    "Sidecar metadata repair cannot be previewed from unreadable JSON.",
                )
            )
            continue
        preconditions.append(
            _precondition(
                f"completed_sidecar_readable:{key}",
                "ok",
                sidecar_path,
                "Sidecar JSON was read for diff evidence only.",
            )
        )
        proposed = {
            "source_path": str(row.get("source_path") or ""),
            "output_path": str(row.get("output_path") or ""),
            "output_file": str(row.get("output_file") or ""),
        }
        current = {field: str(sidecar.get(field) or "") for field in proposed}
        changed = {field: {"current": current[field], "proposed": proposed[field]} for field in proposed if current[field] != proposed[field]}
        if not changed:
            diff_rows.append(
                {
                    "row_key": key,
                    "status": "unchanged",
                    "action": "completed_sidecar_metadata_repair",
                    "sidecar_path": sidecar_path,
                    "changed_fields": {},
                    "safe_next_action": "No sidecar metadata repair candidate detected in this loaded row.",
                }
            )
            continue
        diff_rows.append(
            {
                "row_key": key,
                "status": "candidate",
                "action": "completed_sidecar_metadata_repair",
                "sidecar_path": sidecar_path,
                "changed_fields": changed,
                "safe_next_action": "Review the dry-run diff; no sidecar write route exists.",
            }
        )
        would_write.append({"path": sidecar_path, "reason": "future sidecar metadata repair mutation would rewrite JSON metadata fields"})
    return _set_summary(
        payload,
        rows=diff_rows,
        summary_lines=[
            f"Completed sidecar dry-run reviewed {len(selected_rows)} loaded completed row(s).",
            "No sidecar JSON, completed manifest, output, source, or scratch file was written.",
        ],
        would_write_paths=would_write,
    )


