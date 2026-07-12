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
from mediapipeline.core.processes.rerun_preview_orchestration import *  # noqa: F403

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

__all__ = (
    "_network_preview_row_key",
    "_network_reason_parts",
    "_network_source_mapping",
    "_network_output_handoff",
    "_network_destination_policy",
    "_network_preview_row",
    "rerun_network_csv_preview_payload",
)
