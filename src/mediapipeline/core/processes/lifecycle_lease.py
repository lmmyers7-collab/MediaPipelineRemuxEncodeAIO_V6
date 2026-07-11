"""Durable, fail-closed lifecycle lease for backend-owned work."""

from __future__ import annotations

import json
import os
import tempfile
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable


LIFECYCLE_LEASE_SCHEMA_VERSION = "desktop_lifecycle_lease.v1"
LIFECYCLE_INDETERMINATE_SCHEMA_VERSION = "desktop_lifecycle_indeterminate.v1"


class LifecycleLeaseError(RuntimeError):
    """A durable lifecycle lease could not be acquired or verified."""


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


def _pid_liveness(pid: int) -> bool | None:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return None
    except OSError:
        return None
    return True


class LifecycleLease:
    """One backend-held lease.  The lock file is the cross-process guard."""

    def __init__(self, store: "LifecycleLeaseStore", payload: dict[str, Any]) -> None:
        self._store = store
        self.payload = payload
        self.released = False

    @property
    def lease_id(self) -> str:
        return str(self.payload["lease_id"])

    def activate(self, child_pid: int) -> None:
        if self.released:
            raise LifecycleLeaseError("Cannot activate a released lifecycle lease.")
        self.payload["child_pid"] = int(child_pid)
        self.heartbeat()

    def heartbeat(self) -> None:
        if self.released:
            return
        self.payload["heartbeat_utc"] = _utc_now()
        self._store._write_current(self.payload)

    def set_recovery_descriptor(self, *, route: str, request: dict[str, Any]) -> None:
        """Persist the narrowly scoped input needed for one safe auto-resume."""
        if self.released:
            raise LifecycleLeaseError("Cannot update a released lifecycle lease.")
        self.payload["recovery"] = {
            "route": str(route),
            "request": {str(key): value for key, value in request.items() if str(key) != "_command_id"},
            "attempt_count": int((self.payload.get("recovery") or {}).get("attempt_count") or 0),
        }
        self.heartbeat()

    def release(self, *, outcome: str = "completed") -> None:
        if self.released:
            return
        self._store.release(self, outcome=outcome)
        self.released = True


class LifecycleLeaseStore:
    """Local-file lifecycle authority. Ambiguous existing leases always block."""

    def __init__(self, state_root: Path, *, pid_alive: Callable[[int], bool | None] = _pid_liveness) -> None:
        self.root = Path(state_root) / "Lifecycle"
        self.lock_path = self.root / "active.lock"
        self.record_path = self.root / "active-lease.json"
        self.recovery_path = self.root / "recovery-pending.json"
        self.indeterminate_path = self.root / "indeterminate-command-evidence.json"
        self._pid_alive = pid_alive

    def _read_current(self) -> dict[str, Any] | None:
        try:
            payload = json.loads(self.record_path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return None
        except (OSError, json.JSONDecodeError) as exc:
            raise LifecycleLeaseError(f"Lifecycle lease record could not be verified: {exc}") from exc
        if not isinstance(payload, dict) or payload.get("schema_version") != LIFECYCLE_LEASE_SCHEMA_VERSION:
            raise LifecycleLeaseError("Lifecycle lease record has an invalid schema.")
        return payload

    def _write_current(self, payload: dict[str, Any]) -> None:
        _atomic_write_json(self.record_path, payload)

    def _read_recovery(self) -> dict[str, Any] | None:
        try:
            payload = json.loads(self.recovery_path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return None
        except (OSError, json.JSONDecodeError) as exc:
            raise LifecycleLeaseError(f"Lifecycle recovery record could not be verified: {exc}") from exc
        if not isinstance(payload, dict) or payload.get("schema_version") != LIFECYCLE_LEASE_SCHEMA_VERSION:
            raise LifecycleLeaseError("Lifecycle recovery record has an invalid schema.")
        return payload

    @staticmethod
    def _recovery_command_id(recovery: dict[str, Any]) -> str:
        return f"{str(recovery.get('command_id') or '')}-recovery"

    def _existing_lease_block_message(self) -> str:
        current = self._read_current()
        if current is None:
            return "Lifecycle lock exists without a durable lease record; state is unknown."
        pid = int(current.get("child_pid") or current.get("owner_pid") or 0)
        alive = self._pid_alive(pid)
        if alive is False:
            return f"Lifecycle lease {current.get('lease_id', 'unknown')} is conclusively stale; backend recovery reconciliation is required before new work."
        detail = "still active" if alive is True else "could not be verified"
        return f"Lifecycle lease {current.get('lease_id', 'unknown')} {detail}; new work is blocked."

    def acquire(self, *, scope: str, command_id: str, resource_claims: list[str] | None = None) -> LifecycleLease:
        self.root.mkdir(parents=True, exist_ok=True)
        if self.indeterminate_path.exists():
            raise LifecycleLeaseError("A critical command outcome could not be durably journaled; backend reconciliation is required before new work.")
        recovery = self._read_recovery()
        if recovery is not None and str(command_id) != self._recovery_command_id(recovery):
            raise LifecycleLeaseError("Lifecycle recovery is pending; backend reconciliation is required before new work.")
        try:
            fd = os.open(self.lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError as exc:
            raise LifecycleLeaseError(self._existing_lease_block_message()) from exc
        else:
            os.close(fd)
        payload = {
            "schema_version": LIFECYCLE_LEASE_SCHEMA_VERSION,
            "lease_id": uuid.uuid4().hex,
            "scope": str(scope),
            "command_id": str(command_id),
            "owner_pid": os.getpid(),
            "child_pid": 0,
            "resource_claims": [str(item) for item in resource_claims or [] if str(item)],
            "created_utc": _utc_now(),
            "heartbeat_utc": _utc_now(),
            "recovery_attempt_count": 0,
            "status": "reserved",
        }
        if recovery is not None:
            payload["recovery_attempt"] = {
                "recovery_of_lease_id": str(recovery.get("lease_id") or ""),
                "recovery_of_command_id": str(recovery.get("command_id") or ""),
            }
        try:
            self._write_current(payload)
        except Exception:
            self.lock_path.unlink(missing_ok=True)
            raise
        return LifecycleLease(self, payload)

    def release(self, lease: LifecycleLease, *, outcome: str) -> None:
        current = self._read_current()
        if current is None or str(current.get("lease_id")) != lease.lease_id:
            raise LifecycleLeaseError("Lifecycle lease ownership could not be verified during release.")
        current["status"] = str(outcome)
        current["released_utc"] = _utc_now()
        _atomic_write_json(self.root / f"{lease.lease_id}.terminal.json", current)
        self.record_path.unlink(missing_ok=True)
        self.lock_path.unlink(missing_ok=True)
        if isinstance(current.get("recovery_attempt"), dict):
            if outcome == "completed":
                self.recovery_path.unlink(missing_ok=True)
            else:
                self.mark_indeterminate(
                    command_id=str(current.get("command_id") or ""),
                    route="lifecycle-recovery",
                    reason=f"Automatic lifecycle recovery ended with terminal outcome '{outcome}'.",
                )

    def status(self) -> dict[str, Any]:
        if self.indeterminate_path.exists():
            return {"status": "indeterminate", "reason": "A critical command outcome could not be durably journaled."}
        try:
            recovery = self._read_recovery()
        except LifecycleLeaseError as exc:
            return {"status": "unknown", "reason": str(exc)}
        if recovery is not None:
            return {
                "status": "recovering",
                "lease": recovery,
                "reason": "An automatic lifecycle recovery attempt is pending completion or reconciliation.",
            }
        if not self.lock_path.exists():
            return {"status": "idle"}
        try:
            current = self._read_current()
        except LifecycleLeaseError as exc:
            return {"status": "unknown", "reason": str(exc)}
        if current is None:
            return {"status": "unknown", "reason": "Lifecycle lock exists without a lease record."}
        pid = int(current.get("child_pid") or current.get("owner_pid") or 0)
        alive = self._pid_alive(pid)
        if alive is True:
            return {"status": "active", "lease": current}
        if alive is False:
            return {"status": "stale", "lease": current, "reason": "Lease owner is conclusively absent; recovery reconciliation is required."}
        return {"status": "unknown", "lease": current, "reason": "Lifecycle lease owner could not be verified."}

    def begin_one_recovery_attempt(self) -> dict[str, Any]:
        """Consume one conclusively stale lease before its replacement starts."""
        current = self._read_current()
        if current is None:
            raise LifecycleLeaseError("No lifecycle lease is available for recovery.")
        pid = int(current.get("child_pid") or current.get("owner_pid") or 0)
        if self._pid_alive(pid) is not False:
            raise LifecycleLeaseError("Lifecycle lease owner is not conclusively absent.")
        recovery_value = current.get("recovery")
        recovery: dict[str, Any] = dict(recovery_value) if isinstance(recovery_value, dict) else {}
        if int(recovery.get("attempt_count") or 0) >= 1:
            raise LifecycleLeaseError("The interrupted command has already used its automatic recovery attempt.")
        if not recovery.get("route") or not isinstance(recovery.get("request"), dict):
            raise LifecycleLeaseError("The interrupted command has no durable recovery descriptor.")
        recovery["attempt_count"] = 1
        current["recovery"] = recovery
        current["status"] = "recovery_started"
        current["recovery_started_utc"] = _utc_now()
        _atomic_write_json(self.recovery_path, current)
        self.record_path.unlink(missing_ok=True)
        self.lock_path.unlink(missing_ok=True)
        return {
            "scope": current.get("scope"),
            "command_id": current.get("command_id"),
            "recovery_command_id": self._recovery_command_id(current),
            **recovery,
        }

    def mark_indeterminate(self, *, command_id: str, route: str, reason: str) -> None:
        _atomic_write_json(
            self.indeterminate_path,
            {
                "schema_version": LIFECYCLE_INDETERMINATE_SCHEMA_VERSION,
                "command_id": str(command_id),
                "route": str(route),
                "reason": str(reason),
                "recorded_utc": _utc_now(),
                "operator_action_required": "Run backend reconciliation before retrying or closing.",
            },
        )


__all__ = ["LIFECYCLE_LEASE_SCHEMA_VERSION", "LifecycleLease", "LifecycleLeaseError", "LifecycleLeaseStore"]
