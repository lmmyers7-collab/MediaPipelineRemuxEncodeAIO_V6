from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
import json
import ntpath
from pathlib import Path
import re
from typing import Any, Mapping
from uuid import uuid4

from mediapipeline.core.kernel.contracts import accepted_run_rows_fingerprint
from mediapipeline.core.queue.file_io import atomic_write_text


PRIORITY_QUEUE_EXPORT_SCHEMA_VERSION = "priority_queue_export.v1"
_EXPORT_ID_PATTERN = re.compile(r"^priority-export-[A-Za-z0-9._-]{1,96}$")
_PUBLIC_STATUS_KEYS = frozenset({
    "schema_version",
    "status",
    "ready",
    "reason_code",
    "message",
    "queue_scope",
    "export_id",
    "created_at",
    "count",
    "queue_plan_fingerprint_schema",
    "queue_plan_fingerprint",
    "queue_input_fingerprint_schema",
    "queue_input_fingerprint",
    "accepted_run_rows_fingerprint_schema",
    "accepted_run_rows_fingerprint",
})


def _path_key(value: object) -> str:
    text = str(value or "").strip()
    return ntpath.normcase(ntpath.normpath(text)) if text else ""


def _row_is_effective_high(row: Mapping[str, Any]) -> bool:
    level = str(
        row.get("manifest_priority_level")
        or row.get("effective_priority_level")
        or row.get("effective_priority")
        or "normal"
    ).strip().casefold()
    manifest_explicit = bool(row.get("manifest_priority_explicit", False))
    marker_priority = bool(row.get("is_priority", False))
    high = level == "high" or (marker_priority and level == "normal" and not manifest_explicit)
    blocked = bool(str(row.get("blocked_reason_code") or row.get("blocked_reason") or "").strip())
    held = level == "hold" or str(row.get("phase") or "").strip().casefold() == "hold"
    status = str(row.get("status") or "ready").strip().casefold()
    pending_excluded = bool(row.get("pending_publish_excluded", False))
    return high and not blocked and not held and status in {"ready", "priority ready"} and not pending_excluded


def _blocked(reason_code: str, message: str) -> dict[str, Any]:
    return {
        "schema_version": PRIORITY_QUEUE_EXPORT_SCHEMA_VERSION,
        "status": "blocked",
        "ready": False,
        "reason_code": reason_code,
        "message": message,
        "count": 0,
        "queue_scope": "priority_export",
    }


def _valid_iso_timestamp(value: object) -> bool:
    text = str(value or "").strip()
    if not text:
        return False
    try:
        datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return False
    return True


def _validate_ready_artifact(
    payload: object,
    *,
    requested_export_id: str | None = None,
) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return _blocked("priority_export_malformed", "Priority queue export is malformed.")
    export_id = str(payload.get("export_id") or "").strip()
    accepted = payload.get("accepted_rows")
    count = payload.get("count")
    required_fingerprints = (
        "queue_plan_fingerprint",
        "queue_input_fingerprint",
        "accepted_run_rows_fingerprint",
    )
    valid = (
        payload.get("schema_version") == PRIORITY_QUEUE_EXPORT_SCHEMA_VERSION
        and payload.get("status") == "ready"
        and payload.get("ready") is True
        and payload.get("queue_scope") == "priority_export"
        and _EXPORT_ID_PATTERN.fullmatch(export_id) is not None
        and (requested_export_id is None or export_id == requested_export_id)
        and _valid_iso_timestamp(payload.get("created_at"))
        and isinstance(count, int)
        and not isinstance(count, bool)
        and count > 0
        and isinstance(accepted, list)
        and len(accepted) == count
        and all(isinstance(row, dict) for row in accepted)
        and payload.get("queue_plan_fingerprint_schema") == "queue_plan_fingerprint.v1"
        and payload.get("queue_input_fingerprint_schema") == "queue_input_fingerprint.v1"
        and payload.get("accepted_run_rows_fingerprint_schema") == "accepted_run_rows_fingerprint.v1"
        and all(bool(str(payload.get(key) or "").strip()) for key in required_fingerprints)
    )
    if not valid:
        return _blocked("priority_export_malformed", "Priority queue export failed strict artifact validation.")
    expected_membership = str(payload.get("accepted_run_rows_fingerprint") or "")
    if accepted_run_rows_fingerprint(accepted) != expected_membership:
        return _blocked(
            "priority_export_membership_mismatch",
            "Priority export accepted membership fingerprint does not match.",
        )
    return dict(payload)


class PriorityQueueExportStore:
    def __init__(self, state_root: Path):
        self.state_root = Path(state_root)
        self.export_root = self.state_root / "QueueExports" / "Priority"
        self.latest_path = self.export_root / "latest.json"

    def path_for_export(self, export_id: str) -> Path:
        normalized = str(export_id or "").strip()
        if not _EXPORT_ID_PATTERN.fullmatch(normalized):
            raise ValueError("Priority export id is invalid.")
        return self.export_root / f"{normalized}.json"

    def new_export_id(self) -> str:
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        return f"priority-export-{stamp}-{uuid4().hex[:10]}"

    def create_from_snapshot(
        self,
        snapshot: Mapping[str, Any],
        *,
        export_id: str | None = None,
        created_at: str | None = None,
    ) -> dict[str, Any]:
        rows = snapshot.get("rows") if isinstance(snapshot, Mapping) else None
        accepted = snapshot.get("accepted_run_rows") if isinstance(snapshot, Mapping) else None
        if not isinstance(rows, list) or not isinstance(accepted, list):
            return _blocked("priority_export_snapshot_malformed", "Queue snapshot rows are malformed.")

        if snapshot.get("priority_only_scope") is True:
            selected = [deepcopy(dict(row)) for row in accepted if isinstance(row, Mapping)]
        else:
            high_paths = {
                _path_key(row.get("source_path"))
                for row in rows
                if isinstance(row, Mapping) and _row_is_effective_high(row)
            }
            selected = [
                deepcopy(dict(row))
                for row in accepted
                if isinstance(row, Mapping) and _path_key(row.get("source_path")) in high_paths
            ]
        if not selected:
            return _blocked("priority_export_empty", "No runnable effective-High queue rows are available to export.")

        total = len(selected)
        for index, row in enumerate(selected, start=1):
            row["run_queue_index"] = index
            row["run_queue_total"] = total
        accepted_fingerprint = accepted_run_rows_fingerprint(selected)
        resolved_export_id = str(export_id or self.new_export_id()).strip()
        artifact_path = self.path_for_export(resolved_export_id)
        artifact = {
            "schema_version": PRIORITY_QUEUE_EXPORT_SCHEMA_VERSION,
            "status": "ready",
            "ready": True,
            "reason_code": "",
            "message": f"Priority export contains {total} runnable effective-High row(s).",
            "queue_scope": "priority_export",
            "export_id": resolved_export_id,
            "created_at": str(created_at or datetime.now(UTC).isoformat()),
            "count": total,
            "queue_plan_fingerprint_schema": str(snapshot.get("queue_plan_fingerprint_schema") or ""),
            "queue_plan_fingerprint": str(snapshot.get("queue_plan_fingerprint") or ""),
            "queue_input_fingerprint_schema": str(snapshot.get("queue_input_fingerprint_schema") or ""),
            "queue_input_fingerprint": str(snapshot.get("queue_input_fingerprint") or ""),
            "accepted_run_rows_fingerprint_schema": "accepted_run_rows_fingerprint.v1",
            "accepted_run_rows_fingerprint": accepted_fingerprint,
            "accepted_rows": selected,
        }
        serialized = json.dumps(artifact, indent=2, sort_keys=True) + "\n"
        atomic_write_text(artifact_path, serialized)
        atomic_write_text(self.latest_path, serialized)
        return artifact

    def latest_status(self) -> dict[str, Any]:
        if not self.latest_path.is_file():
            return {
                "schema_version": PRIORITY_QUEUE_EXPORT_SCHEMA_VERSION,
                "status": "missing",
                "ready": False,
                "reason_code": "priority_export_missing",
                "message": "No priority queue export has been created.",
                "count": 0,
                "queue_scope": "priority_export",
            }
        try:
            payload = json.loads(self.latest_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            return _blocked("priority_export_malformed", "Latest priority queue export is unreadable.")
        return _validate_ready_artifact(payload)

    def validate_for_launch(
        self,
        *,
        export_id: str,
        current_snapshot: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        try:
            artifact_path = self.path_for_export(export_id)
        except ValueError:
            return _blocked("priority_export_missing", "Priority queue export id is invalid.")
        if not artifact_path.is_file():
            return _blocked("priority_export_missing", "Requested priority queue export does not exist.")
        try:
            payload = json.loads(artifact_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            return _blocked("priority_export_malformed", "Requested priority queue export is unreadable.")
        validated = _validate_ready_artifact(payload, requested_export_id=str(export_id or "").strip())
        if validated.get("status") != "ready":
            return validated
        payload = validated
        if current_snapshot is not None:
            input_fingerprint = str(current_snapshot.get("queue_input_fingerprint") or "")
            plan_fingerprint = str(current_snapshot.get("queue_plan_fingerprint") or "")
            if not input_fingerprint or input_fingerprint != str(payload.get("queue_input_fingerprint") or ""):
                return _blocked("priority_export_input_stale", "Queue inputs changed after this priority export was created.")
            if not plan_fingerprint or plan_fingerprint != str(payload.get("queue_plan_fingerprint") or ""):
                return _blocked("priority_export_plan_mismatch", "Priority queue membership changed after export.")

        result = dict(payload)
        result["status"] = "ready"
        result["ready"] = True
        return result


def priority_export_public_status(payload: Mapping[str, Any]) -> dict[str, Any]:
    public = {key: payload[key] for key in _PUBLIC_STATUS_KEYS if key in payload}
    public["accepted_membership_backend_owned"] = bool(payload.get("accepted_rows"))
    return public


__all__ = [
    "PRIORITY_QUEUE_EXPORT_SCHEMA_VERSION",
    "PriorityQueueExportStore",
    "priority_export_public_status",
]
