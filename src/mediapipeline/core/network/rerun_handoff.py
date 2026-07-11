"""Network CSV rerun handoff path planning and validation."""

from __future__ import annotations

import copy
import ntpath
import os
import uuid
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from mediapipeline.core.config.library_profiles import library_profiles_from_config
from mediapipeline.core.kernel.config_keys import (
    KEY_LOCAL_BASE,
    KEY_NETWORK_RERUN_HANDOFF_ROOT,
    KEY_OUTSOURCE,
    KEY_SOURCE_MOVIES,
    KEY_SOURCE_TV,
)
from mediapipeline.core.paths.contracts import ResolvedPaths


NETWORK_RERUN_HANDOFF_SCHEMA_VERSION = "desktop_rerun_network_handoff.v1"
NETWORK_RERUN_HANDOFF_PROBE_SCHEMA_VERSION = "desktop_rerun_network_handoff_probe.v1"


def _text(value: Any) -> str:
    return str(value or "").strip()


def _expanded_path_text(value: Any) -> str:
    text = _text(value)
    if not text:
        return ""
    try:
        expanded = str(Path(text).expanduser())
    except (OSError, RuntimeError, ValueError):
        expanded = text
    try:
        return os.path.abspath(os.path.normpath(expanded))
    except (OSError, ValueError):
        return os.path.normpath(expanded)


def _path_key(value: Any) -> str:
    text = _expanded_path_text(value).replace("/", "\\").rstrip("\\")
    if not text:
        return ""
    return text.casefold()


def _path_is_absolute(value: Any) -> bool:
    text = _text(value)
    if not text:
        return False
    try:
        if Path(text).expanduser().is_absolute():
            return True
    except (OSError, RuntimeError, ValueError):
        pass
    return ntpath.isabs(text.replace("/", "\\"))


def _path_is_unc(value: Any) -> bool:
    text = _text(value).replace("/", "\\")
    return text.startswith("\\\\") and len([part for part in text.split("\\") if part]) >= 2


def _path_within_or_equal(path: Any, root: Any) -> bool:
    path_key = _path_key(path)
    root_key = _path_key(root)
    return bool(path_key and root_key and (path_key == root_key or path_key.startswith(root_key + "\\")))


def _candidate_path(label: str, value: Any) -> dict[str, str] | None:
    text = _text(value)
    if not text:
        return None
    return {"label": label, "path": _expanded_path_text(text)}


def _library_profile_paths(config: Mapping[str, Any]) -> list[dict[str, str]]:
    try:
        profiles = library_profiles_from_config(dict(config or {}))
    except Exception:
        profiles = []
    rows: list[dict[str, str]] = []
    for index, profile in enumerate(profiles, start=1):
        if not isinstance(profile, Mapping) or profile.get("enabled", True) is False:
            continue
        label = _text(profile.get("id") or profile.get("name") or f"profile_{index}")
        source = _candidate_path(f"LibraryProfiles[{label}].source_path", profile.get("effective_source_root") or profile.get("source_path"))
        output = _candidate_path(f"LibraryProfiles[{label}].output_path", profile.get("effective_output_root") or profile.get("output_path"))
        if source is not None:
            rows.append(source)
        if output is not None:
            rows.append(output)
    return rows


def network_rerun_handoff_forbidden_roots(
    config: Mapping[str, Any] | None,
    *,
    resolved: ResolvedPaths | None = None,
) -> list[dict[str, str]]:
    """Return roots that a network rerun handoff root must not overlap."""

    config = dict(config or {})
    roots: list[dict[str, str]] = []
    for key in (KEY_SOURCE_MOVIES, KEY_SOURCE_TV, KEY_OUTSOURCE, KEY_LOCAL_BASE):
        candidate = _candidate_path(key, config.get(key))
        if candidate is not None:
            roots.append(candidate)

    roots.extend(_library_profile_paths(config))

    if resolved is not None:
        for label, value in (
            (KEY_SOURCE_MOVIES, getattr(resolved, "source_movies", None)),
            (KEY_SOURCE_TV, getattr(resolved, "source_tv", None)),
            (KEY_LOCAL_BASE, getattr(resolved, "local_base", None)),
            ("PendingServerPush", getattr(resolved, "pending_push_path", None)),
        ):
            candidate = _candidate_path(label, value)
            if candidate is not None:
                roots.append(candidate)
        if getattr(resolved, "pending_push_path", None) is None and getattr(resolved, "state_root", None) is not None:
            roots.append({"label": "PendingServerPush", "path": str(resolved.state_root / "PendingServerPush")})
        elif getattr(resolved, "pending_push_path", None) is None and getattr(resolved, "local_base", None) is not None:
            roots.append({"label": "PendingServerPush", "path": str(resolved.local_base / "PendingServerPush")})
    elif _text(config.get(KEY_LOCAL_BASE)):
        roots.append({"label": "PendingServerPush", "path": str(Path(_expanded_path_text(config[KEY_LOCAL_BASE])) / "State" / "PendingServerPush")})

    unique: list[dict[str, str]] = []
    seen: set[str] = set()
    for root in roots:
        key = _path_key(root.get("path"))
        if not key or key in seen:
            continue
        seen.add(key)
        unique.append(root)
    return unique


def _handoff_overlap_errors(root_path: str, forbidden_roots: list[dict[str, str]]) -> list[str]:
    errors: list[str] = []
    for forbidden in forbidden_roots:
        label = _text(forbidden.get("label"))
        path = _text(forbidden.get("path"))
        if not path:
            continue
        if _path_within_or_equal(root_path, path) or _path_within_or_equal(path, root_path):
            errors.append(f"NetworkRerunHandoffRoot must not overlap {label}: {path}")
    return errors


def network_rerun_handoff_config_errors(config: Mapping[str, Any] | None) -> list[str]:
    """Static config validation for a configured handoff root.

    Missing ``NetworkRerunHandoffRoot`` is allowed at general settings-save time
    because only network CSV rerun uses it. Runtime preview/start routes block
    missing roots when the operator chooses that mode.
    """

    config = dict(config or {})
    root = _text(config.get(KEY_NETWORK_RERUN_HANDOFF_ROOT))
    if not root:
        return []
    errors: list[str] = []
    if not _path_is_absolute(root):
        errors.append("NetworkRerunHandoffRoot must be an absolute path.")
        return errors
    errors.extend(_handoff_overlap_errors(_expanded_path_text(root), network_rerun_handoff_forbidden_roots(config)))
    return errors


def network_rerun_handoff_root_evidence(
    resolved: ResolvedPaths,
    *,
    require_shared: bool = False,
) -> dict[str, Any]:
    config = dict(getattr(resolved, "config_data", {}) or {})
    raw_root = _text(config.get(KEY_NETWORK_RERUN_HANDOFF_ROOT))
    evidence: dict[str, Any] = {
        "schema_version": NETWORK_RERUN_HANDOFF_SCHEMA_VERSION,
        "setting_key": KEY_NETWORK_RERUN_HANDOFF_ROOT,
        "configured": bool(raw_root),
        "status": "not_configured",
        "ready": False,
        "root_path": "",
        "path_kind": "missing",
        "remote_worker_compatible": False,
        "coordinator_local_only": False,
        "cleanup_owner": "coordinator",
        "blockers": [],
        "warnings": [],
        "forbidden_roots_checked": network_rerun_handoff_forbidden_roots(config, resolved=resolved),
        "coordinator_probe": {
            "schema_version": NETWORK_RERUN_HANDOFF_PROBE_SCHEMA_VERSION,
            "status": "not_run_no_write_evidence",
            "required_before_state_exposure": True,
            "operations_required": ["create", "list", "read", "delete"],
        },
    }
    if not raw_root:
        evidence["blockers"] = ["network_rerun_handoff_root_missing"]
        evidence["reason"] = "NetworkRerunHandoffRoot is not configured."
        return evidence

    root_path = _expanded_path_text(raw_root)
    is_unc = _path_is_unc(raw_root)
    evidence.update(
        {
            "status": "blocked",
            "root_path": root_path,
            "path_kind": "unc" if is_unc else "local_drive",
            "remote_worker_compatible": is_unc,
            "coordinator_local_only": not is_unc,
        }
    )
    blockers: list[str] = []
    warnings: list[str] = []
    if not _path_is_absolute(raw_root):
        blockers.append("network_rerun_handoff_root_not_absolute")
    if require_shared and not is_unc:
        blockers.append("network_rerun_handoff_root_not_unc_for_remote_workers")
    if not blockers:
        root = Path(root_path)
        if not root.exists():
            blockers.append("network_rerun_handoff_root_missing_on_disk")
        elif not root.is_dir():
            blockers.append("network_rerun_handoff_root_not_directory")
    blockers.extend(_handoff_overlap_errors(root_path, list(evidence["forbidden_roots_checked"])))
    if not is_unc:
        warnings.append("NetworkRerunHandoffRoot is a coordinator-local path; remote worker claims require a UNC/shared root.")

    evidence["blockers"] = blockers
    evidence["warnings"] = warnings
    if blockers:
        evidence["reason"] = "; ".join(blockers)
        return evidence

    evidence["status"] = "ready"
    evidence["ready"] = True
    evidence["reason"] = "NetworkRerunHandoffRoot exists, is outside protected roots, and is ready for confirmed-start coordinator probe."
    return evidence


def network_rerun_handoff_for_row(
    root_evidence: Mapping[str, Any],
    *,
    row_key: str,
    planned_output_key: str = "",
    batch_id: str = "",
) -> dict[str, Any]:
    root_path = _text(root_evidence.get("root_path") or root_evidence.get("handoff_root"))
    ready = root_evidence.get("ready") is True and bool(row_key)
    batch_part = batch_id or "{batch_id}"
    planned_path = str(Path(root_path) / batch_part / row_key) if root_path and row_key else ""
    result = {
        "schema_version": NETWORK_RERUN_HANDOFF_SCHEMA_VERSION,
        "status": "ready" if ready else str(root_evidence.get("status") or "blocked"),
        "ready": ready,
        "strategy": "network_rerun_handoff_root",
        "setting_key": KEY_NETWORK_RERUN_HANDOFF_ROOT,
        "root_path": root_path,
        "handoff_root": root_path,
        "path_kind": str(root_evidence.get("path_kind") or ""),
        "remote_worker_compatible": root_evidence.get("remote_worker_compatible") is True,
        "coordinator_local_only": root_evidence.get("coordinator_local_only") is True,
        "cleanup_owner": "coordinator",
        "planned_output_key": planned_output_key,
        "batch_id": batch_id,
        "row_key": row_key,
        "planned_batch_relative_path": f"{batch_part}/{row_key}" if row_key else "",
        "planned_row_handoff_path": planned_path if batch_id else "",
        "planned_row_handoff_path_template": planned_path,
        "blockers": [str(item) for item in root_evidence.get("blockers") or []],
        "warnings": [str(item) for item in root_evidence.get("warnings") or []],
        "coordinator_probe": dict(root_evidence.get("coordinator_probe") or {}),
        "reason": str(root_evidence.get("reason") or ""),
    }
    if not ready and not result["blockers"]:
        result["blockers"] = ["network_rerun_handoff_row_key_missing"]
    return result


def network_rerun_assign_batch_handoff_paths(preview: Mapping[str, Any], batch_id: str) -> dict[str, Any]:
    payload = copy.deepcopy(dict(preview or {}))
    rows: list[dict[str, Any]] = []
    for row in payload.get("rows") or []:
        if not isinstance(row, dict):
            continue
        output_handoff = dict(row.get("output_handoff") or {})
        if output_handoff.get("ready") is True:
            refreshed = network_rerun_handoff_for_row(
                output_handoff,
                row_key=str(row.get("row_key") or ""),
                planned_output_key=str(output_handoff.get("planned_output_key") or ""),
                batch_id=batch_id,
            )
            row["output_handoff"] = refreshed
            row["planned_output_path"] = str(refreshed.get("planned_row_handoff_path") or "")
        rows.append(row)
    payload["rows"] = rows
    root_evidence = dict(payload.get("output_handoff") or {})
    if root_evidence:
        root_evidence["batch_id"] = batch_id
        root_evidence["per_row_path_shape"] = "<NetworkRerunHandoffRoot>/<batch_id>/<row_key>/"
        payload["output_handoff"] = root_evidence
    return payload


def probe_network_rerun_handoff_root(root_evidence: Mapping[str, Any]) -> dict[str, Any]:
    """Create/list/read/delete a temporary probe below the configured handoff root."""

    root_path = _text(root_evidence.get("root_path"))
    result: dict[str, Any] = {
        "schema_version": NETWORK_RERUN_HANDOFF_PROBE_SCHEMA_VERSION,
        "status": "not_run",
        "ok": False,
        "root_path": root_path,
        "operations": [],
        "cleanup_result": "not_started",
    }
    if root_evidence.get("ready") is not True or not root_path:
        result.update(
            {
                "status": "blocked",
                "error": "NetworkRerunHandoffRoot is not ready for coordinator probe.",
                "blockers": [str(item) for item in root_evidence.get("blockers") or []],
            }
        )
        return result

    probe_dir = Path(root_path) / f".network-rerun-probe-{uuid.uuid4().hex}"
    probe_file = probe_dir / "probe.txt"
    try:
        probe_dir.mkdir(parents=False, exist_ok=False)
        result["operations"].append("create")
        probe_file.write_text("network rerun handoff probe\n", encoding="utf-8")
        result["operations"].append("write")
        if probe_file.read_text(encoding="utf-8") != "network rerun handoff probe\n":
            raise RuntimeError("probe read did not match written content")
        result["operations"].append("read")
        _ = list(probe_dir.iterdir())
        _ = list(Path(root_path).iterdir())
        result["operations"].append("list")
        probe_file.unlink()
        probe_dir.rmdir()
        result["operations"].append("delete")
    except Exception as exc:
        result.update({"status": "failed", "error": str(exc), "cleanup_result": "cleanup_attempted"})
        try:
            probe_file.unlink(missing_ok=True)
        except OSError:
            pass
        try:
            probe_dir.rmdir()
        except OSError:
            pass
        return result

    result.update({"status": "pass", "ok": True, "cleanup_result": "probe_removed"})
    return result


__all__ = [
    "NETWORK_RERUN_HANDOFF_PROBE_SCHEMA_VERSION",
    "NETWORK_RERUN_HANDOFF_SCHEMA_VERSION",
    "network_rerun_assign_batch_handoff_paths",
    "network_rerun_handoff_config_errors",
    "network_rerun_handoff_for_row",
    "network_rerun_handoff_forbidden_roots",
    "network_rerun_handoff_root_evidence",
    "probe_network_rerun_handoff_root",
]
