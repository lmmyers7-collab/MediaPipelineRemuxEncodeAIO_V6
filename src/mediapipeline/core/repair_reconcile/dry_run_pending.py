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

def _set_pending_manifest_field(
    proposed: dict[str, Any],
    changed: dict[str, dict[str, Any]],
    field: str,
    value: Any,
) -> None:
    current_value = proposed.get(field) if field in proposed else "<missing>"
    if current_value == value:
        return
    proposed[field] = value
    changed[field] = {"current": current_value, "proposed": value}


def _pending_manifest_sidecar_paths(sidecar_files: list[Any]) -> list[Path]:
    paths: list[Path] = []
    for sidecar in sidecar_files:
        if not isinstance(sidecar, Mapping):
            continue
        raw = str(sidecar.get("local_file") or sidecar.get("parked_file") or "").strip()
        if raw:
            paths.append(Path(raw))
    return paths


def _pending_manifest_repair_hash(manifest_path: str, proposed: Mapping[str, Any]) -> str:
    basis = {
        "manifest_path": manifest_path,
        "local_file": str(proposed.get("local_file") or proposed.get("parked_file") or "").strip(),
        "server_out": str(proposed.get("server_out") or "").strip(),
        "source_identity_v2": str(proposed.get("source_identity_v2") or "").strip(),
        "source_path": str(proposed.get("source_path") or "").strip(),
        "output_size": proposed.get("output_size"),
    }
    encoded = json.dumps(basis, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8", errors="replace")).hexdigest()[:24]


def _pending_manifest_array_alias(proposed: Mapping[str, Any], field: str) -> list[Any]:
    aliases = {
        "sidecar_files": ("sidecars",),
    }
    for alias in aliases.get(field, ()):
        value = proposed.get(alias)
        if isinstance(value, list):
            return list(value)
    return []


def _repair_legacy_csv_rerun_manifest(
    *,
    proposed: dict[str, Any],
    changed: dict[str, dict[str, Any]],
    reasons: list[str],
    manifest_path: str,
) -> None:
    route = str(proposed.get("route") or "").strip().casefold()
    source = proposed.get("source")
    source_kind = str(source.get("rerun_batch_id") or source.get("rerun_audit_issue_codes") or "").strip() if isinstance(source, Mapping) else ""
    if route != "csv_rerun" and not source_kind:
        return

    if not str(proposed.get("pipeline_version") or "").strip():
        _set_pending_manifest_field(proposed, changed, "pipeline_version", CSV_RERUN_REPAIR_PIPELINE_VERSION)
        reasons.append("missing_pipeline_version_from_legacy_csv_rerun")

    if not str(proposed.get("publish_transaction_id") or "").strip():
        repair_hash = _pending_manifest_repair_hash(manifest_path, proposed)
        _set_pending_manifest_field(proposed, changed, "publish_transaction_id", f"repair-csv-rerun-{repair_hash}")
        reasons.append("missing_publish_transaction_id_from_legacy_csv_rerun")

    if not str(proposed.get("parked_at") or "").strip():
        created_at = str(proposed.get("created_at") or "").strip()
        if created_at:
            _set_pending_manifest_field(proposed, changed, "parked_at", created_at)
            reasons.append("missing_parked_at_copied_from_created_at")


def _pending_orphan_missing_manifest_evidence(row: Mapping[str, Any]) -> list[str]:
    missing: list[str] = []
    if not str(row.get("manifest_path") or "").strip():
        missing.append("manifest_path")
    if str(row.get("schema_version") or "").strip() != PENDING_PUSH_MANIFEST_SCHEMA_VERSION:
        missing.append("schema_version")
    for field in PENDING_PUSH_MANIFEST_REQUIRED_TEXT_FIELDS:
        if not str(row.get(field) or "").strip():
            missing.append(field)
    if "output_size" not in row or row.get("output_size") in (None, ""):
        missing.append("output_size")
    for field in PENDING_PUSH_MANIFEST_REQUIRED_ARRAY_FIELDS:
        if not isinstance(row.get(field), list):
            missing.append(field)
    return missing


def _path_identity(value: object) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    return str(Path(text)).casefold()


def _server_destination_key(value: object) -> str:
    return _path_identity(value).rstrip("\\/")


def _is_csv_rerun_manifest(proposed: Mapping[str, Any]) -> bool:
    route = str(proposed.get("route") or "").strip().casefold()
    reason_code = str(proposed.get("route_reason_code") or "").strip().casefold()
    source = proposed.get("source")
    source_kind = str(source.get("rerun_batch_id") or source.get("rerun_audit_issue_codes") or "").strip() if isinstance(source, Mapping) else ""
    return route == "csv_rerun" or reason_code == "rerun_csv_pending_publish" or bool(source_kind)


def _pending_manifest_server_destination_keys(rows: list[dict[str, Any]], *, exclude_row_key: str) -> set[str]:
    excluded = exclude_row_key.casefold()
    keys: set[str] = set()
    for row in rows:
        if _row_key(row).casefold() == excluded:
            continue
        for field in ("server_out", "output_path"):
            key = _server_destination_key(row.get(field))
            if key:
                keys.add(key)
                break
    return keys


def _non_overlapping_server_destination(path: Path, occupied_keys: set[str], suffix: str) -> Path:
    if _server_destination_key(path) not in occupied_keys:
        return path
    candidate = path.with_name(f"{path.stem}.{suffix}{path.suffix}")
    counter = 1
    while _server_destination_key(candidate) in occupied_keys:
        candidate = path.with_name(f"{path.stem}.{suffix}.{counter}{path.suffix}")
        counter += 1
    return candidate


def _duplicate_rerun_server_destination(
    *,
    current_server_out: str,
    local_file: str,
    occupied_server_out_keys: set[str],
    manifest_path: str,
) -> tuple[str, str]:
    current_path = Path(current_server_out)
    local_path = Path(local_file)
    if not current_path.name or not local_path.name:
        return "", "Duplicate target repair requires both current server_out and local_file filenames."
    if current_path.suffix.casefold() != local_path.suffix.casefold():
        return "", "Duplicate target repair requires the parked payload extension to match server_out."
    if current_path.name.casefold() == local_path.name.casefold():
        return "", "Selected duplicate row has no rerun-suffixed parked payload name to derive a distinct destination."
    if not local_path.stem.casefold().startswith(current_path.stem.casefold()):
        return "", "Selected duplicate row payload name does not preserve the original destination stem."
    repair_hash = _pending_manifest_repair_hash(manifest_path, {"local_file": local_file, "server_out": current_server_out})
    candidate = _non_overlapping_server_destination(
        current_path.with_name(local_path.name),
        occupied_server_out_keys,
        f"repair-{repair_hash}",
    )
    return str(candidate), ""


def _rerun_sidecars_for_server_destination(
    sidecar_files: Any,
    *,
    current_server_out: str,
    repaired_server_out: str,
) -> list[Any] | None:
    if not isinstance(sidecar_files, list):
        return None
    current_media = Path(current_server_out)
    repaired_media = Path(repaired_server_out)
    current_stem = current_media.stem
    repaired_stem = repaired_media.stem
    if not current_stem or not repaired_stem:
        return None
    changed = False
    repaired_sidecars: list[Any] = []
    for sidecar in sidecar_files:
        if not isinstance(sidecar, Mapping):
            repaired_sidecars.append(sidecar)
            continue
        copied = dict(sidecar)
        sidecar_out = str(copied.get("server_out") or "").strip()
        if sidecar_out:
            sidecar_path = Path(sidecar_out)
            sidecar_stem = sidecar_path.stem
            if sidecar_stem.casefold().startswith(current_stem.casefold()):
                repaired_name = f"{repaired_stem}{sidecar_stem[len(current_stem):]}{sidecar_path.suffix}"
                repaired_out = str(sidecar_path.with_name(repaired_name))
                if repaired_out != sidecar_out:
                    copied["server_out"] = repaired_out
                    changed = True
        repaired_sidecars.append(copied)
    return repaired_sidecars if changed else None


def _pending_orphan_expected_manifest_path(payload_path: Path) -> Path:
    return payload_path.with_name(f"{payload_path.name}.manifest.json")


def _pending_orphan_backend_proposal(row: Mapping[str, Any]) -> tuple[dict[str, Any] | None, str]:
    for key in ("backend_manifest_proposal", "orphan_manifest_proposal", "proposed_manifest"):
        value = row.get(key)
        if isinstance(value, Mapping):
            return dict(value), key
    return None, ""


def _pending_orphan_payload_candidate_row(
    *,
    row: Mapping[str, Any],
    key: str,
    diagnostic_status: str,
) -> dict[str, Any] | None:
    proposed, proposal_source = _pending_orphan_backend_proposal(row)
    if proposed is None:
        return None

    local_file = str(row.get("local_file") or "").strip()
    if not local_file:
        return {
            "row_key": key,
            "status": "blocked",
            "action": "pending_orphan_payload_reconcile",
            "local_file": "",
            "diagnostic_status": diagnostic_status,
            "proposed_manifest_available": True,
            "proposal_source": proposal_source,
            "missing_required_manifest_fields": _pending_orphan_missing_manifest_evidence(proposed),
            "error": "Backend orphan manifest proposal cannot be matched because the orphan row has no local_file payload.",
            "safe_next_action": "Refresh Pending Publish evidence before confirmed apply.",
        }

    payload_path = Path(local_file)
    expected_manifest_path = _pending_orphan_expected_manifest_path(payload_path)
    manifest_path_text = str(row.get("manifest_path") or expected_manifest_path).strip()
    if _path_identity(manifest_path_text) != _path_identity(expected_manifest_path):
        return {
            "row_key": key,
            "status": "blocked",
            "action": "pending_orphan_payload_reconcile",
            "manifest_path": manifest_path_text,
            "local_file": local_file,
            "diagnostic_status": diagnostic_status,
            "proposed_manifest_available": True,
            "proposal_source": proposal_source,
            "error": "Backend orphan manifest proposal targets a manifest path that is not the payload-adjacent pending manifest path.",
            "safe_next_action": "Refresh backend pending-publish evidence; do not apply mismatched orphan manifest proposals.",
        }
    if expected_manifest_path.exists():
        return {
            "row_key": key,
            "status": "blocked",
            "action": "pending_orphan_payload_reconcile",
            "manifest_path": str(expected_manifest_path),
            "local_file": local_file,
            "diagnostic_status": diagnostic_status,
            "proposed_manifest_available": True,
            "proposal_source": proposal_source,
            "error": "Backend orphan manifest proposal would overwrite an existing pending manifest.",
            "safe_next_action": "Refresh Pending Publish; use pending manifest repair for existing manifests.",
        }

    try:
        validated = PendingPushManifest.from_mapping(proposed)
    except ContractError as exc:
        return {
            "row_key": key,
            "status": "blocked",
            "action": "pending_orphan_payload_reconcile",
            "manifest_path": str(expected_manifest_path),
            "local_file": local_file,
            "diagnostic_status": diagnostic_status,
            "proposed_manifest_available": True,
            "proposal_source": proposal_source,
            "missing_required_manifest_fields": _pending_orphan_missing_manifest_evidence(proposed),
            "error": f"Backend orphan manifest proposal fails pending manifest contract: {exc}",
            "safe_next_action": "Repair backend manifest evidence before confirmed apply.",
        }

    if _path_identity(validated.local_file) != _path_identity(local_file):
        return {
            "row_key": key,
            "status": "blocked",
            "action": "pending_orphan_payload_reconcile",
            "manifest_path": str(expected_manifest_path),
            "local_file": local_file,
            "diagnostic_status": diagnostic_status,
            "proposed_manifest_available": True,
            "proposal_source": proposal_source,
            "error": "Backend orphan manifest proposal local_file does not match the selected orphan payload.",
            "safe_next_action": "Refresh backend pending-publish evidence; do not reconcile mismatched payload proposals.",
        }
    if not payload_path.exists() or not payload_path.is_file():
        return {
            "row_key": key,
            "status": "blocked",
            "action": "pending_orphan_payload_reconcile",
            "manifest_path": str(expected_manifest_path),
            "local_file": local_file,
            "diagnostic_status": diagnostic_status,
            "proposed_manifest_available": True,
            "proposal_source": proposal_source,
            "error": "Backend orphan manifest proposal points at a missing pending payload.",
            "safe_next_action": "Restore the pending payload before confirmed orphan manifest reconcile.",
        }
    try:
        payload_size = payload_path.stat().st_size
    except OSError as exc:
        return {
            "row_key": key,
            "status": "blocked",
            "action": "pending_orphan_payload_reconcile",
            "manifest_path": str(expected_manifest_path),
            "local_file": local_file,
            "diagnostic_status": diagnostic_status,
            "proposed_manifest_available": True,
            "proposal_source": proposal_source,
            "error": f"Pending payload size could not be verified: {exc}",
            "safe_next_action": "Refresh Pending Publish after payload access is stable.",
        }
    if int(validated.output_size) != int(payload_size):
        return {
            "row_key": key,
            "status": "blocked",
            "action": "pending_orphan_payload_reconcile",
            "manifest_path": str(expected_manifest_path),
            "local_file": local_file,
            "diagnostic_status": diagnostic_status,
            "proposed_manifest_available": True,
            "proposal_source": proposal_source,
            "error": "Backend orphan manifest proposal output_size does not match the selected pending payload.",
            "safe_next_action": "Refresh backend manifest evidence before confirmed apply.",
        }

    missing_sidecars = [str(path) for path in _pending_manifest_sidecar_paths(validated.sidecar_files) if not path.exists()]
    if missing_sidecars:
        return {
            "row_key": key,
            "status": "blocked",
            "action": "pending_orphan_payload_reconcile",
            "manifest_path": str(expected_manifest_path),
            "local_file": local_file,
            "diagnostic_status": diagnostic_status,
            "proposed_manifest_available": True,
            "proposal_source": proposal_source,
            "missing_sidecar_paths": missing_sidecars,
            "error": "Backend orphan manifest proposal references missing pending sidecar payloads.",
            "safe_next_action": "Restore missing sidecar payloads before confirmed orphan manifest reconcile.",
        }

    return {
        "row_key": key,
        "status": "candidate",
        "action": "pending_orphan_payload_reconcile",
        "manifest_path": str(expected_manifest_path),
        "diagnostic_status": diagnostic_status,
        "local_file": validated.local_file,
        "source_path": validated.source_path,
        "output_path": validated.server_out,
        "proposed_manifest_available": True,
        "proposal_source": proposal_source,
        "proposed": {
            "local_file": validated.local_file,
            "source_path": validated.source_path,
            "output_path": validated.server_out,
            "manifest_state": validated.manifest_state,
            "schema_version": PENDING_PUSH_MANIFEST_SCHEMA_VERSION,
        },
        "proposed_manifest": proposed,
        "safe_next_action": "Review the backend-derived orphan manifest proposal, then submit the matching dry-run fingerprint to confirmed apply.",
    }


def _pending_manifest_repair_candidate_row(
    *,
    row: Mapping[str, Any],
    key: str,
    manifest_path: str,
    diagnostic_status: str,
    occupied_server_out_keys: set[str] | None = None,
) -> dict[str, Any]:
    manifest, read_error = _read_json_object(manifest_path)
    if manifest is None:
        return {
            "row_key": key,
            "status": "blocked",
            "action": "pending_manifest_repair",
            "manifest_path": manifest_path,
            "diagnostic_status": diagnostic_status,
            "error": read_error,
            "safe_next_action": "Fix pending manifest readability before any backend manifest repair.",
        }

    proposed = dict(manifest)
    changed: dict[str, dict[str, Any]] = {}
    reasons: list[str] = []
    for field in PENDING_PUSH_MANIFEST_REQUIRED_ARRAY_FIELDS:
        if field not in proposed or proposed.get(field) is None:
            _set_pending_manifest_field(proposed, changed, field, _pending_manifest_array_alias(proposed, field))
            reasons.append(f"missing_{field}")

    _repair_legacy_csv_rerun_manifest(
        proposed=proposed,
        changed=changed,
        reasons=reasons,
        manifest_path=manifest_path,
    )

    if diagnostic_status == "duplicate_target":
        if not _is_csv_rerun_manifest(proposed):
            return {
                "row_key": key,
                "status": "blocked",
                "action": "pending_manifest_repair",
                "manifest_path": manifest_path,
                "diagnostic_status": diagnostic_status,
                "error": "Duplicate target repair is only backend-derived for CSV rerun pending manifests.",
                "safe_next_action": "Compare duplicate manifests manually and keep payloads parked until target ownership is unambiguous.",
            }
        repaired_server_out, repair_error = _duplicate_rerun_server_destination(
            current_server_out=str(proposed.get("server_out") or "").strip(),
            local_file=str(proposed.get("local_file") or proposed.get("parked_file") or "").strip(),
            occupied_server_out_keys=occupied_server_out_keys or set(),
            manifest_path=manifest_path,
        )
        if repair_error:
            return {
                "row_key": key,
                "status": "blocked",
                "action": "pending_manifest_repair",
                "manifest_path": manifest_path,
                "diagnostic_status": diagnostic_status,
                "error": repair_error,
                "safe_next_action": "Select the rerun-suffixed duplicate row or keep the file parked for manual duplicate review.",
            }
        current_server_out = str(proposed.get("server_out") or "").strip()
        _set_pending_manifest_field(proposed, changed, "server_out", repaired_server_out)
        reasons.append("duplicate_server_out_resolved_from_rerun_payload_name")
        repaired_sidecars = _rerun_sidecars_for_server_destination(
            proposed.get("sidecar_files"),
            current_server_out=current_server_out,
            repaired_server_out=repaired_server_out,
        )
        if repaired_sidecars is not None:
            _set_pending_manifest_field(proposed, changed, "sidecar_files", repaired_sidecars)
            reasons.append("duplicate_sidecar_server_outs_retargeted")

    local_file = str(proposed.get("local_file") or "").strip()
    parked_file = str(proposed.get("parked_file") or "").strip()
    if not local_file and parked_file:
        parked_path = Path(parked_file)
        if parked_path.exists() and parked_path.is_file():
            _set_pending_manifest_field(proposed, changed, "local_file", parked_file)
            reasons.append("missing_local_file_copied_from_parked_file")

    output_size_missing = "output_size" not in proposed or proposed.get("output_size") in (None, "")
    if output_size_missing:
        local_text = str(proposed.get("local_file") or "").strip()
        if local_text:
            local_path = Path(local_text)
            try:
                if local_path.exists() and local_path.is_file():
                    _set_pending_manifest_field(proposed, changed, "output_size", local_path.stat().st_size)
                    reasons.append("missing_output_size_inferred_from_payload")
            except OSError:
                pass

    if not changed:
        try:
            PendingPushManifest.from_mapping(manifest)
        except ContractError as exc:
            return {
                "row_key": key,
                "status": "blocked",
                "action": "pending_manifest_repair",
                "manifest_path": manifest_path,
                "diagnostic_status": diagnostic_status,
                "error": f"Current pending manifest contract invalid and no safe backend normalization is available: {exc}",
                "safe_next_action": "Repair pending manifest contract fields manually before confirmed apply.",
            }
        return {
            "row_key": key,
            "status": "unchanged",
            "action": "pending_manifest_repair",
            "manifest_path": manifest_path,
            "diagnostic_status": diagnostic_status,
            "safe_next_action": "No backend-derived manifest-field repair candidate detected for this pending row.",
        }

    try:
        validated = PendingPushManifest.from_mapping(proposed)
    except ContractError as exc:
        return {
            "row_key": key,
            "status": "blocked",
            "action": "pending_manifest_repair",
            "manifest_path": manifest_path,
            "diagnostic_status": diagnostic_status,
            "changed_fields": changed,
            "missing_or_unsafe_fields": sorted(changed),
            "error": f"Backend proposed manifest still fails pending manifest contract: {exc}",
            "safe_next_action": "Repair the remaining manifest contract fields manually before confirmed apply.",
        }

    payload_path = Path(validated.local_file)
    if not payload_path.exists() or not payload_path.is_file():
        return {
            "row_key": key,
            "status": "blocked",
            "action": "pending_manifest_repair",
            "manifest_path": manifest_path,
            "diagnostic_status": diagnostic_status,
            "changed_fields": changed,
            "missing_or_unsafe_fields": sorted(changed),
            "error": "Backend proposed manifest points at a missing pending payload.",
            "safe_next_action": "Restore the pending payload before confirmed manifest repair.",
        }
    try:
        payload_size = payload_path.stat().st_size
    except OSError as exc:
        return {
            "row_key": key,
            "status": "blocked",
            "action": "pending_manifest_repair",
            "manifest_path": manifest_path,
            "diagnostic_status": diagnostic_status,
            "changed_fields": changed,
            "missing_or_unsafe_fields": sorted(changed),
            "error": f"Pending payload size could not be verified: {exc}",
            "safe_next_action": "Refresh Pending Publish after payload access is stable.",
        }
    if int(validated.output_size) != int(payload_size):
        return {
            "row_key": key,
            "status": "blocked",
            "action": "pending_manifest_repair",
            "manifest_path": manifest_path,
            "diagnostic_status": diagnostic_status,
            "changed_fields": changed,
            "missing_or_unsafe_fields": sorted(changed),
            "error": "Backend proposed manifest output_size does not match the pending payload.",
            "safe_next_action": "Refresh backend manifest evidence before confirmed apply.",
        }

    missing_sidecars = [str(path) for path in _pending_manifest_sidecar_paths(validated.sidecar_files) if not path.exists()]
    if missing_sidecars:
        return {
            "row_key": key,
            "status": "blocked",
            "action": "pending_manifest_repair",
            "manifest_path": manifest_path,
            "diagnostic_status": diagnostic_status,
            "changed_fields": changed,
            "missing_or_unsafe_fields": sorted(changed),
            "missing_sidecar_paths": missing_sidecars,
            "error": "Backend proposed manifest references missing pending sidecar payloads.",
            "safe_next_action": "Restore missing sidecar payloads before confirmed manifest repair.",
        }

    return {
        "row_key": key,
        "status": "candidate",
        "action": "pending_manifest_repair",
        "manifest_path": manifest_path,
        "diagnostic_status": diagnostic_status,
        "local_file": validated.local_file,
        "source_path": validated.source_path,
        "output_path": validated.server_out,
        "reasons": reasons,
        "changed_fields": changed,
        "proposed": {
            "local_file": validated.local_file,
            "source_path": validated.source_path,
            "output_path": validated.server_out,
            "manifest_state": validated.manifest_state,
            "schema_version": PENDING_PUSH_MANIFEST_SCHEMA_VERSION,
        },
        "proposed_manifest": proposed,
        "safe_next_action": "Review the backend-derived manifest diff, then submit the matching dry-run fingerprint to confirmed apply.",
    }


def pending_manifest_repair_dry_run(
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
    preconditions = [*base_preconditions, backend_path_authority_precondition("pending_publish"), *selection_preconditions]
    pending_error = str(preview.get("error") or "").strip()
    preconditions.append(
        _precondition(
            "pending_publish_scan_readable",
            "blocked" if pending_error else "ok",
            pending_error or f"{len(rows)} pending publish row(s) loaded from existing scan.",
            "Resolve pending publish scan errors before mutation design." if pending_error else "Use current pending-publish scan evidence only.",
        )
    )
    payload = _base_payload(
        candidate_command=PENDING_PUBLISH_REPAIR_MANIFEST_COMMAND,
        scope=scope,
        selected_row_keys=selected_keys,
        preconditions=preconditions,
        request=request,
    )
    diff_rows: list[dict[str, Any]] = []
    would_write: list[dict[str, str]] = []
    for row in selected_rows:
        key = _row_key(row)
        status = str(row.get("diagnostic_status") or "").strip().casefold()
        manifest_path = str(row.get("manifest_path") or "").strip()
        if status == "unreadable_manifest":
            diff_rows.append(
                {
                    "row_key": key,
                    "status": "blocked",
                    "action": "pending_manifest_repair",
                    "manifest_path": manifest_path,
                    "diagnostic_status": status,
                    "error": str(row.get("error") or ""),
                    "safe_next_action": "Review the backend manifest evidence manually; this dry-run does not accept patches.",
                }
            )
            preconditions.append(
                _precondition(
                    f"pending_manifest_repairable:{key}",
                    "blocked",
                    status or "pending manifest status is not repairable",
                    "Do not build a mutation from unreadable, invalid, or duplicate-target pending manifests.",
                )
            )
            continue
        if not manifest_path:
            diff_rows.append(
                {
                    "row_key": key,
                    "status": "unchanged",
                    "action": "pending_manifest_repair",
                    "diagnostic_status": status,
                    "safe_next_action": "No manifest path exists for this row; use orphan-payload dry-run instead.",
                }
            )
            continue
        if status == "ready":
            diff_rows.append(
                {
                    "row_key": key,
                    "status": "unchanged",
                    "action": "pending_manifest_repair",
                    "manifest_path": manifest_path,
                    "diagnostic_status": status,
                    "safe_next_action": "No pending manifest repair candidate detected.",
                }
            )
            continue
        candidate = _pending_manifest_repair_candidate_row(
            row=row,
            key=key,
            manifest_path=manifest_path,
            diagnostic_status=status,
            occupied_server_out_keys=_pending_manifest_server_destination_keys(rows, exclude_row_key=key),
        )
        diff_rows.append(candidate)
        if candidate.get("status") == "candidate":
            preconditions.append(
                _precondition(
                    f"pending_manifest_repairable:{key}",
                    "ok",
                    "Backend-derived proposed manifest validates pending_push_manifest.v1 and preserves payload/source/output paths.",
                    "Confirmed apply may write only this manifest after matching fingerprint and strict confirmation.",
                )
            )
            would_write.append({"path": manifest_path, "reason": "pending manifest repair will rewrite backend-validated manifest fields"})
        elif candidate.get("status") == "blocked":
            preconditions.append(
                _precondition(
                    f"pending_manifest_repairable:{key}",
                    "blocked",
                    str(candidate.get("error") or status or "pending manifest is not repairable"),
                    "Do not apply pending manifest repair until backend evidence can build a complete proposed manifest.",
                )
            )
    return _set_summary(
        payload,
        rows=diff_rows,
        summary_lines=[
            f"Pending manifest dry-run reviewed {len(selected_rows)} pending-publish row(s).",
            "Existing pending scan, recovery classification, file inventory, and drain summary evidence were reused.",
            "No pending manifest, payload, sidecar, output, source, or scratch file was written or moved.",
        ],
        would_write_paths=would_write,
    )


def pending_orphan_payload_reconcile_dry_run(
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
    preconditions = [*base_preconditions, backend_path_authority_precondition("pending_publish"), *selection_preconditions]
    pending_error = str(preview.get("error") or "").strip()
    preconditions.append(
        _precondition(
            "pending_publish_scan_readable",
            "blocked" if pending_error else "ok",
            pending_error or f"{len(rows)} pending publish row(s) loaded from existing scan.",
            "Resolve pending publish scan errors before mutation design." if pending_error else "Use current pending-publish scan evidence only.",
        )
    )
    payload = _base_payload(
        candidate_command=PENDING_PUBLISH_RECONCILE_ORPHAN_PAYLOADS_COMMAND,
        scope=scope,
        selected_row_keys=selected_keys,
        preconditions=preconditions,
        request=request,
    )
    diff_rows: list[dict[str, Any]] = []
    would_write: list[dict[str, str]] = []
    for row in selected_rows:
        key = _row_key(row)
        status = str(row.get("diagnostic_status") or "").strip().casefold()
        if status == "duplicate_target":
            diff_rows.append(
                {
                    "row_key": key,
                    "status": "blocked",
                    "action": "pending_orphan_payload_reconcile",
                    "local_file": str(row.get("local_file") or ""),
                    "diagnostic_status": status,
                    "safe_next_action": "Resolve duplicate pending targets before any orphan-payload mutation design.",
                }
            )
            preconditions.append(
                _precondition(
                    f"pending_payload_ambiguity:{key}",
                    "blocked",
                    "duplicate pending target collision",
                    "Do not move or delete payloads while target ownership is ambiguous.",
                )
            )
            continue
        if status != "orphan_payload" and str(row.get("state") or "").casefold() != "orphan_payload":
            diff_rows.append(
                {
                    "row_key": key,
                    "status": "unchanged",
                    "action": "pending_orphan_payload_reconcile",
                    "local_file": str(row.get("local_file") or ""),
                    "diagnostic_status": status,
                    "safe_next_action": "No orphan payload reconcile candidate detected.",
                }
            )
            continue
        candidate = _pending_orphan_payload_candidate_row(row=row, key=key, diagnostic_status=status)
        if candidate is not None:
            diff_rows.append(candidate)
            if str(candidate.get("status") or "").casefold() == "candidate":
                would_write.append(
                    {
                        "path": str(candidate.get("manifest_path") or ""),
                        "reason": "orphan payload reconcile will create backend-validated pending manifest",
                    }
                )
            else:
                preconditions.append(
                    _precondition(
                        f"pending_payload_manifest_evidence:{key}",
                        "blocked",
                        str(candidate.get("error") or "backend orphan manifest proposal is incomplete"),
                        "Repair backend manifest evidence before confirmed apply; do not infer source/destination in the frontend.",
                    )
                )
            continue
        missing_manifest_fields = _pending_orphan_missing_manifest_evidence(row)
        diff_rows.append(
            {
                "row_key": key,
                "status": "blocked",
                "action": "pending_orphan_payload_reconcile",
                "local_file": str(row.get("local_file") or ""),
                "output_size": row.get("output_size") or 0,
                "diagnostic_status": status,
                "missing_required_manifest_fields": missing_manifest_fields,
                "required_backend_evidence": (
                    "A manifest-only orphan reconcile requires a complete backend-derived "
                    f"{PENDING_PUSH_MANIFEST_SCHEMA_VERSION} proposal; WebView/request payloads must not supply fields."
                ),
                "proposed_manifest_available": False,
                "safe_next_action": (
                    "Restore the original pending manifest or rerun with backend manifest evidence; this route will not "
                    "infer destination/source from filename and will not move, delete, drain, or publish payloads."
                ),
            }
        )
        preconditions.append(
            _precondition(
                f"pending_payload_manifest_evidence:{key}",
                "blocked",
                "orphan payload lacks complete backend-derived pending_push_manifest.v1 evidence",
                "Restore the manifest or provide backend-owned manifest evidence before any confirmed apply; do not infer source/destination in the frontend.",
            )
        )
    return _set_summary(
        payload,
        rows=diff_rows,
        summary_lines=[
            f"Pending orphan-payload dry-run reviewed {len(selected_rows)} pending-publish row(s).",
            "Existing pending scan, file inventory, recovery classification, and drain summary evidence were reused.",
            "No backend-derived orphan manifest candidates were safe to apply unless a complete pending_push_manifest.v1 proposal is present.",
            "No pending payload, manifest, sidecar, output, source, or scratch file was moved, deleted, drained, or written.",
        ],
        would_write_paths=would_write,
        would_move_paths=[],
        would_delete_paths=[],
    )


__all__ = [
    "COMPLETED_RECONCILE_MANIFEST_COMMAND",
    "COMPLETED_REPAIR_SIDECAR_METADATA_COMMAND",
    "PENDING_PUBLISH_REPAIR_MANIFEST_COMMAND",
    "PENDING_PUBLISH_RECONCILE_ORPHAN_PAYLOADS_COMMAND",
    "REPAIR_RECONCILE_DRY_RUN_SCHEMA_VERSION",
    "STARTUP_RECONCILE_STATE_COMMAND",
    "STARTUP_RECONCILIATION_DRY_RUN_SCHEMA_VERSION",
    "active_work_precondition",
    "bounded_repair_reconcile_limit",
    "completed_manifest_reconcile_dry_run",
    "completed_sidecar_metadata_repair_dry_run",
    "dry_run_command_name",
    "normalize_repair_reconcile_scope",
    "pending_manifest_repair_dry_run",
    "pending_orphan_payload_reconcile_dry_run",
    "repair_reconcile_dry_run_fingerprint",
    "startup_reconciliation_dry_run",
]
