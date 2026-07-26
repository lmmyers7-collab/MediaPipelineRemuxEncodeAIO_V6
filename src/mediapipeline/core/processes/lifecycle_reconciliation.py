"""Fail-closed reconciliation for terminal lifecycle recovery evidence."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

from mediapipeline.core.processes.lifecycle_lease import (
    LIFECYCLE_INDETERMINATE_SCHEMA_VERSION,
    LIFECYCLE_LEASE_SCHEMA_VERSION,
    LIFECYCLE_RECONCILIATION_PENDING_FILENAME,
    _pid_liveness,
)


LIFECYCLE_RECONCILIATION_PREVIEW_SCHEMA_VERSION = "desktop_lifecycle_reconciliation_preview.v1"
LIFECYCLE_RECONCILIATION_RESULT_SCHEMA_VERSION = "desktop_lifecycle_reconciliation_result.v1"
LIFECYCLE_RECONCILIATION_TRANSACTION_SCHEMA_VERSION = "desktop_lifecycle_reconciliation_transaction.v1"

PidAlive = Callable[[int], bool | None]


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path: Path | None = None
    try:
        fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent, text=True)
        tmp_path = Path(tmp_name)
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, path)
        tmp_path = None
    finally:
        if tmp_path is not None:
            try:
                tmp_path.unlink(missing_ok=True)
            except OSError:
                pass


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _valid_nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


class LifecycleReconciliationService:
    """Classify and archive one provably terminal failed recovery chain."""

    def __init__(self, state_root: Path, *, pid_alive: PidAlive = _pid_liveness) -> None:
        self.state_root = Path(state_root)
        self.lifecycle_root = self.state_root / "Lifecycle"
        self.archive_root = self.state_root / "LifecycleArchive"
        self.pending_intent_path = self.state_root / LIFECYCLE_RECONCILIATION_PENDING_FILENAME
        self._pid_alive = pid_alive

    def _snapshot(self) -> tuple[list[dict[str, Any]], dict[str, bytes], list[str]]:
        entries: list[dict[str, Any]] = []
        raw_files: dict[str, bytes] = {}
        blockers: list[str] = []
        if not self.lifecycle_root.exists():
            return entries, raw_files, ["Lifecycle evidence directory is missing."]
        if not self.lifecycle_root.is_dir() or self.lifecycle_root.is_symlink():
            return entries, raw_files, ["Lifecycle evidence path is not a regular directory."]
        try:
            paths = sorted(self.lifecycle_root.rglob("*"), key=lambda item: item.as_posix().casefold())
        except OSError as exc:
            return entries, raw_files, [f"Lifecycle evidence could not be enumerated: {exc}"]
        for path in paths:
            relative = path.relative_to(self.lifecycle_root).as_posix()
            if path.is_symlink():
                try:
                    target = os.readlink(path)
                except OSError as exc:
                    target = f"<unreadable: {exc}>"
                entries.append({"path": relative, "kind": "symlink", "target": target})
                blockers.append(f"Lifecycle evidence contains unsupported symbolic link: {relative}.")
                continue
            if path.is_dir():
                entries.append({"path": relative, "kind": "directory"})
                blockers.append(f"Lifecycle evidence contains unsupported nested directory: {relative}.")
                continue
            if not path.is_file():
                entries.append({"path": relative, "kind": "unknown"})
                blockers.append(f"Lifecycle evidence contains an unsupported path type: {relative}.")
                continue
            try:
                raw = path.read_bytes()
            except OSError as exc:
                entries.append({"path": relative, "kind": "file", "error": str(exc)})
                blockers.append(f"Lifecycle evidence could not be read: {relative}: {exc}")
                continue
            raw_files[relative] = raw
            entries.append(
                {
                    "path": relative,
                    "kind": "file",
                    "size": len(raw),
                    "sha256": hashlib.sha256(raw).hexdigest(),
                }
            )
        return entries, raw_files, blockers

    @staticmethod
    def _read_mapping(raw_files: dict[str, bytes], relative: str, blockers: list[str]) -> dict[str, Any] | None:
        raw = raw_files.get(relative)
        if raw is None:
            blockers.append(f"Required lifecycle evidence is missing: {relative}.")
            return None
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            blockers.append(f"Lifecycle evidence is not valid UTF-8 JSON: {relative}: {exc}")
            return None
        if not isinstance(payload, dict):
            blockers.append(f"Lifecycle evidence must be a JSON object: {relative}.")
            return None
        return payload

    @staticmethod
    def _safe_recovery_request(route: str, request: dict[str, Any]) -> bool:
        if route == "/api/audit/start":
            return True
        if route == "/api/pipeline/start":
            return str(request.get("mode") or "").casefold() == "validate"
        if route == "/api/rerun/start":
            return request.get("dry_run") is True or request.get("plan_only") is True
        return False

    @staticmethod
    def _known_terminal_recovery_reason(reason: Any) -> bool:
        if not _valid_nonempty_string(reason):
            return False
        normalized = str(reason).strip().casefold()
        return (
            normalized == "automatic recovery did not produce a successful terminal result."
            or "backend lifecycle state is recovering" in normalized
        )

    def _record_pid_verdict(
        self,
        payload: dict[str, Any],
        *,
        evidence: str,
        field: str,
        verdicts: list[dict[str, Any]],
        blockers: list[str],
    ) -> None:
        value = payload.get(field)
        if type(value) is not int or value < 0:
            blockers.append(f"{evidence} has an invalid {field} PID.")
            verdicts.append({"evidence": evidence, "field": field, "pid": value, "alive": None})
            return
        try:
            alive = self._pid_alive(value)
        except Exception:
            alive = None
        verdicts.append({"evidence": evidence, "field": field, "pid": value, "alive": alive})
        if alive is not False:
            detail = "alive" if alive is True else "not conclusively dead"
            blockers.append(f"{evidence} {field} PID {value} is {detail}.")

    def _preview(self, *, ignore_pending_intent: bool = False) -> dict[str, Any]:
        entries, raw_files, blockers = self._snapshot()
        if self.pending_intent_path.exists() and not ignore_pending_intent:
            blockers.append(
                "A prior lifecycle evidence reconciliation transaction is incomplete; manual transaction recovery is required."
            )
        marker_name = "indeterminate-command-evidence.json"
        recovery_name = "recovery-pending.json"
        marker = self._read_mapping(raw_files, marker_name, blockers)
        recovery = self._read_mapping(raw_files, recovery_name, blockers)
        verdicts: list[dict[str, Any]] = []
        correlated_terminal_name = ""

        if "active.lock" in raw_files or "active-lease.json" in raw_files:
            blockers.append("Active lifecycle reservation evidence is present; reconciliation cannot archive active work.")

        if marker is not None:
            if marker.get("schema_version") != LIFECYCLE_INDETERMINATE_SCHEMA_VERSION:
                blockers.append("Indeterminate lifecycle evidence has an invalid schema.")
            if not _valid_nonempty_string(marker.get("command_id")):
                blockers.append("Indeterminate lifecycle evidence is missing command_id.")
            if not _valid_nonempty_string(marker.get("route")):
                blockers.append("Indeterminate lifecycle evidence is missing route.")
            if not self._known_terminal_recovery_reason(marker.get("reason")):
                blockers.append("Indeterminate lifecycle evidence does not describe the known terminal recovery failure.")

        recovery_descriptor: dict[str, Any] | None = None
        if recovery is not None:
            if recovery.get("schema_version") != LIFECYCLE_LEASE_SCHEMA_VERSION:
                blockers.append("Pending recovery evidence has an invalid schema.")
            if not _valid_nonempty_string(recovery.get("lease_id")):
                blockers.append("Pending recovery evidence is missing lease_id.")
            if not _valid_nonempty_string(recovery.get("command_id")):
                blockers.append("Pending recovery evidence is missing command_id.")
            if recovery.get("status") != "recovery_started":
                blockers.append("Pending recovery evidence is not in recovery_started status.")
            descriptor_value = recovery.get("recovery")
            if not isinstance(descriptor_value, dict):
                blockers.append("Pending recovery evidence is missing its recovery descriptor.")
            else:
                recovery_descriptor = descriptor_value
                route = descriptor_value.get("route")
                request = descriptor_value.get("request")
                if not _valid_nonempty_string(route):
                    blockers.append("Pending recovery descriptor is missing route.")
                if not isinstance(request, dict):
                    blockers.append("Pending recovery descriptor request must be a JSON object.")
                elif isinstance(route, str) and not self._safe_recovery_request(route, request):
                    blockers.append("Pending recovery descriptor is outside the proven safe replay boundary.")
                if type(descriptor_value.get("attempt_count")) is not int or descriptor_value.get("attempt_count") != 1:
                    blockers.append("Pending recovery evidence must record exactly one recovery attempt.")
            self._record_pid_verdict(
                recovery,
                evidence=recovery_name,
                field="owner_pid",
                verdicts=verdicts,
                blockers=blockers,
            )
            self._record_pid_verdict(
                recovery,
                evidence=recovery_name,
                field="child_pid",
                verdicts=verdicts,
                blockers=blockers,
            )

        if marker is not None and recovery is not None and recovery_descriptor is not None:
            if marker.get("command_id") != recovery.get("command_id"):
                blockers.append("Indeterminate and pending recovery command IDs do not match.")
            if marker.get("route") != recovery_descriptor.get("route"):
                blockers.append("Indeterminate and pending recovery routes do not match.")

        terminal_mappings: list[tuple[str, dict[str, Any]]] = []
        for relative in sorted(name for name in raw_files if name.endswith(".terminal.json")):
            payload = self._read_mapping(raw_files, relative, blockers)
            if payload is not None:
                terminal_mappings.append((relative, payload))

        original_command_id = str(recovery.get("command_id") or "") if recovery is not None else ""
        expected_recovery_command_id = f"{original_command_id}-recovery" if original_command_id else ""
        matching_terminals = [
            (relative, payload)
            for relative, payload in terminal_mappings
            if payload.get("command_id") == expected_recovery_command_id
        ]
        if len(matching_terminals) != 1:
            blockers.append("Exactly one terminal recovery record must match the pending recovery command.")
        else:
            correlated_terminal_name, terminal = matching_terminals[0]
            if terminal.get("schema_version") != LIFECYCLE_LEASE_SCHEMA_VERSION:
                blockers.append("Terminal recovery evidence has an invalid schema.")
            if terminal.get("status") != "launch_failed":
                blockers.append("Terminal recovery evidence must have launch_failed status.")
            if type(terminal.get("child_pid")) is not int or terminal.get("child_pid") != 0:
                blockers.append("Terminal recovery evidence must record child_pid 0.")
            terminal_lease_id = terminal.get("lease_id")
            if not _valid_nonempty_string(terminal_lease_id):
                blockers.append("Terminal recovery evidence is missing lease_id.")
            elif Path(correlated_terminal_name).name != f"{terminal_lease_id}.terminal.json":
                blockers.append("Terminal recovery filename does not match its lease_id.")
            attempt = terminal.get("recovery_attempt")
            if not isinstance(attempt, dict):
                blockers.append("Terminal recovery evidence is missing recovery_attempt correlation.")
            elif recovery is not None:
                if attempt.get("recovery_of_lease_id") != recovery.get("lease_id"):
                    blockers.append("Terminal recovery evidence does not reference the pending lease ID.")
                if attempt.get("recovery_of_command_id") != recovery.get("command_id"):
                    blockers.append("Terminal recovery evidence does not reference the pending command ID.")
            terminal_descriptor = terminal.get("recovery")
            if not isinstance(terminal_descriptor, dict):
                blockers.append("Terminal recovery evidence is missing its recovery descriptor.")
            elif recovery_descriptor is not None:
                if terminal_descriptor.get("route") != recovery_descriptor.get("route"):
                    blockers.append("Terminal and pending recovery routes do not match.")
                try:
                    requests_match = _canonical_json(terminal_descriptor.get("request")) == _canonical_json(
                        recovery_descriptor.get("request")
                    )
                except (TypeError, ValueError):
                    requests_match = False
                if not requests_match:
                    blockers.append("Terminal and pending recovery requests do not match.")
            self._record_pid_verdict(
                terminal,
                evidence=correlated_terminal_name,
                field="owner_pid",
                verdicts=verdicts,
                blockers=blockers,
            )
            self._record_pid_verdict(
                terminal,
                evidence=correlated_terminal_name,
                field="child_pid",
                verdicts=verdicts,
                blockers=blockers,
            )

        fingerprint_payload = {
            "lifecycle_root": str(self.lifecycle_root.resolve(strict=False)),
            "entries": entries,
            "pid_verdicts": verdicts,
        }
        fingerprint = hashlib.sha256(_canonical_json(fingerprint_payload).encode("utf-8")).hexdigest()
        unique_blockers = list(dict.fromkeys(blockers))
        return {
            "schema_version": LIFECYCLE_RECONCILIATION_PREVIEW_SCHEMA_VERSION,
            "dry_run": True,
            "safe_to_apply": not unique_blockers,
            "dry_run_fingerprint": fingerprint,
            "blockers": unique_blockers,
            "lifecycle_root": str(self.lifecycle_root),
            "evidence_paths": [str(self.lifecycle_root / entry["path"]) for entry in entries if entry.get("kind") == "file"],
            "correlated_terminal_path": str(self.lifecycle_root / correlated_terminal_name) if correlated_terminal_name else "",
            "pid_verdicts": verdicts,
        }

    def preview(self) -> dict[str, Any]:
        return self._preview()

    @staticmethod
    def _failed_result(*, fingerprint: str, errors: list[str]) -> dict[str, Any]:
        return {
            "schema_version": LIFECYCLE_RECONCILIATION_RESULT_SCHEMA_VERSION,
            "ok": False,
            "applied": False,
            "dry_run_fingerprint": fingerprint,
            "archive_path": "",
            "archived_paths": [],
            "errors": errors,
        }

    def apply(self, *, dry_run_fingerprint: str, confirm_apply: object, reason: str) -> dict[str, Any]:
        request_errors: list[str] = []
        if type(confirm_apply) is not bool or confirm_apply is not True:
            request_errors.append("confirm_apply must be the JSON boolean true.")
        if not _valid_nonempty_string(dry_run_fingerprint):
            request_errors.append("dry_run_fingerprint is required.")
        if not _valid_nonempty_string(reason):
            request_errors.append("A non-empty reconciliation reason is required.")
        if request_errors:
            return self._failed_result(fingerprint=str(dry_run_fingerprint or ""), errors=request_errors)

        current = self.preview()
        current_fingerprint = str(current["dry_run_fingerprint"])
        if str(dry_run_fingerprint) != current_fingerprint:
            return self._failed_result(
                fingerprint=current_fingerprint,
                errors=["Lifecycle evidence changed after preview; run the dry-run again."],
            )
        if not bool(current["safe_to_apply"]):
            return self._failed_result(
                fingerprint=current_fingerprint,
                errors=[str(item) for item in current["blockers"]],
            )

        transaction_id = f"{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex}"
        transaction_root = self.archive_root / transaction_id
        archived_lifecycle_root = transaction_root / "Lifecycle"
        intent_path = transaction_root / "reconciliation-intent.json"
        intent = {
            "schema_version": LIFECYCLE_RECONCILIATION_TRANSACTION_SCHEMA_VERSION,
            "transaction_id": transaction_id,
            "status": "prepared",
            "created_utc": _utc_now(),
            "reason": reason.strip(),
            "dry_run_fingerprint": current_fingerprint,
            "source_path": str(self.lifecycle_root),
            "archive_path": str(archived_lifecycle_root),
        }
        try:
            transaction_root.mkdir(parents=True, exist_ok=False)
            _atomic_write_json(intent_path, intent)
            revalidated = self.preview()
            if (
                not bool(revalidated["safe_to_apply"])
                or str(revalidated["dry_run_fingerprint"]) != current_fingerprint
            ):
                raise RuntimeError("Lifecycle evidence changed while the archive transaction was being prepared.")
            _atomic_write_json(self.pending_intent_path, intent)
            guarded = self._preview(ignore_pending_intent=True)
            if (
                not bool(guarded["safe_to_apply"])
                or str(guarded["dry_run_fingerprint"]) != current_fingerprint
            ):
                raise RuntimeError(
                    "Lifecycle evidence changed after the reconciliation guard was published; the archive was not applied."
                )
            os.replace(self.lifecycle_root, archived_lifecycle_root)
            archived_paths = sorted(
                str(path)
                for path in archived_lifecycle_root.rglob("*")
                if path.is_file() and not path.is_symlink()
            )
            manifest = {
                **intent,
                "status": "completed",
                "completed_utc": _utc_now(),
                "archived_paths": archived_paths,
            }
            _atomic_write_json(transaction_root / "reconciliation-manifest.json", manifest)
            _atomic_write_json(intent_path, manifest)
            self.pending_intent_path.unlink()
        except Exception as exc:
            rollback_error = ""
            if archived_lifecycle_root.exists() and not self.lifecycle_root.exists():
                try:
                    os.replace(archived_lifecycle_root, self.lifecycle_root)
                except OSError as rollback_exc:
                    rollback_error = f" Rollback also failed: {rollback_exc}"
            if not rollback_error and self.lifecycle_root.exists():
                try:
                    self.pending_intent_path.unlink(missing_ok=True)
                except OSError as cleanup_exc:
                    rollback_error = f" Reconciliation guard cleanup also failed: {cleanup_exc}"
            try:
                _atomic_write_json(
                    intent_path,
                    {
                        **intent,
                        "status": "rolled_back" if not rollback_error else "rollback_failed",
                        "failed_utc": _utc_now(),
                        "error": f"{exc}{rollback_error}",
                    },
                )
            except OSError:
                pass
            return self._failed_result(
                fingerprint=current_fingerprint,
                errors=[f"Lifecycle evidence archive failed: {exc}{rollback_error}"],
            )

        return {
            "schema_version": LIFECYCLE_RECONCILIATION_RESULT_SCHEMA_VERSION,
            "ok": True,
            "applied": True,
            "dry_run_fingerprint": current_fingerprint,
            "archive_path": str(archived_lifecycle_root),
            "archived_paths": archived_paths,
            "errors": [],
        }


__all__ = [
    "LIFECYCLE_RECONCILIATION_PREVIEW_SCHEMA_VERSION",
    "LIFECYCLE_RECONCILIATION_RESULT_SCHEMA_VERSION",
    "LifecycleReconciliationService",
]
