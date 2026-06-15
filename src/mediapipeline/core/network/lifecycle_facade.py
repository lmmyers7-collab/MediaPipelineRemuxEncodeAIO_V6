"""Backend-owned coordinator/worker lifecycle command facade."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import uuid
from typing import Any, Callable, Mapping

from mediapipeline.core.network.url_policy import (
    redact_network_secret_text,
    redact_url,
    validate_coordinator_url,
)
from mediapipeline.core.processes.pipeline_policy import (
    configured_network_role,
    coordinator_also_encode_locally_enabled,
    normalize_network_role,
    network_role_is_valid,
    pipeline_start_network_mode_label,
)
from mediapipeline.core.kernel.dto_commands import CommandResult
from mediapipeline.core.kernel.models_core import ResolvedPaths


NETWORK_LIFECYCLE_DRY_RUN_SCHEMA_VERSION = "desktop_network_lifecycle_dry_run.v1"
NETWORK_LIFECYCLE_RESULT_SCHEMA_VERSION = "desktop_network_lifecycle_result.v1"
NETWORK_LIFECYCLE_EFFECT_NONE = "none"


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _runtime_state_dir(resolved: ResolvedPaths, service: object) -> Path:
    app_state_path = getattr(resolved, "app_state_path", None) or getattr(service, "app_state_path", None)
    if app_state_path:
        return Path(app_state_path).parent
    if resolved.state_root is not None:
        return Path(resolved.state_root) / "App"
    return Path(resolved.app_root)


def _precondition(key: str, status: str, evidence: str, action: str) -> dict[str, Any]:
    return {
        "key": key,
        "status": status,
        "evidence": evidence,
        "action": action,
    }


def _safe_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _redacted_token_state(value: Any, *, allow_generate: bool = False) -> str:
    text = str(value or "").strip()
    if text:
        return "present_redacted"
    return "will_generate_on_start" if allow_generate else "missing"


def _redact_url(value: Any) -> str:
    return redact_url(value)


def _worker_coordinator_url_issue(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return "missing"
    try:
        validate_coordinator_url(text)
    except ValueError as exc:
        return redact_network_secret_text(exc)
    return ""


def _bounded_evidence(value: Any, *, limit: int = 240) -> str:
    text = redact_network_secret_text(value).strip()
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 3)] + "..."


def _lifecycle_command(role: str, action: str) -> str:
    return f"network.{role}.{action}"


def _state_file_posture(resolved: ResolvedPaths, service: object) -> list[dict[str, Any]]:
    state_dir = _runtime_state_dir(resolved, service)
    rows: list[dict[str, Any]] = []
    for key, name in (
        ("coordinator_inflight", "coordinator_inflight.json"),
        ("worker_state", "worker_state.json"),
        ("cluster_log", "cluster.log"),
    ):
        path = state_dir / name
        row: dict[str, Any] = {
            "key": key,
            "path": str(path),
            "exists": False,
            "status": "missing",
            "size_bytes": 0,
            "read_only": True,
        }
        try:
            stat = path.stat()
        except FileNotFoundError:
            rows.append(row)
            continue
        except OSError as exc:
            row["status"] = "unreadable"
            row["error"] = _bounded_evidence(exc)
            rows.append(row)
            continue
        row.update(
            {
                "exists": True,
                "status": "present",
                "size_bytes": int(stat.st_size),
                "modified_utc": datetime.fromtimestamp(stat.st_mtime, timezone.utc)
                .replace(microsecond=0)
                .isoformat()
                .replace("+00:00", "Z"),
            }
        )
        rows.append(row)
    return rows


class NetworkLifecycleFacadeMixin:
    """Network lifecycle command boundary for the local API."""

    service: object
    app_version: str

    def _network_lifecycle_state_for(self, role: str) -> dict[str, Any]:
        state = getattr(self, "_network_lifecycle_state", None)
        if not isinstance(state, dict):
            return {"role": role, "status": "stopped"}
        return dict(state.get(role) or {"role": role, "status": "stopped"})

    def _network_lifecycle_provider_available(self, role: str, action: str) -> bool:
        return callable(self._network_lifecycle_provider_method(role, action))

    def _network_lifecycle_provider_method(self, role: str, action: str) -> Any:
        name = f"{action}_network_{role}"
        service_provider = getattr(self.service, name, None)
        if callable(service_provider):
            return service_provider
        return getattr(self, name, None)

    def _network_lifecycle_state_update(
        self,
        *,
        role: str,
        status: str,
        command_id: str,
        action: str,
    ) -> dict[str, Any]:
        lock = getattr(self, "_network_lifecycle_lock", None)
        if lock is None:
            return {"role": role, "status": status}
        with lock:
            state = getattr(self, "_network_lifecycle_state", None)
            if not isinstance(state, dict):
                state = {}
                setattr(self, "_network_lifecycle_state", state)
            previous = dict(state.get(role) or {"role": role, "status": "stopped"})
            updated = self._network_lifecycle_state_candidate(
                previous,
                role=role,
                status=status,
                command_id=command_id,
                action=action,
            )
            self._network_lifecycle_state_commit(role, updated)
            return updated

    def _network_lifecycle_state_candidate(
        self,
        previous: Mapping[str, Any],
        *,
        role: str,
        status: str,
        command_id: str,
        action: str,
    ) -> dict[str, Any]:
        now = _utc_now()
        updated = {
            **dict(previous),
            "role": role,
            "status": status,
            "last_command_id": command_id,
            "last_action": action,
            "updated_utc": now,
            "state_scope": "session_memory_only",
        }
        if action == "start" and status == "running":
            updated["started_utc"] = now
        if action == "stop" and status == "stopped":
            updated["stopped_utc"] = now
        return updated

    def _network_lifecycle_state_commit(self, role: str, state_after: Mapping[str, Any]) -> None:
        state = getattr(self, "_network_lifecycle_state", None)
        if not isinstance(state, dict):
            state = {}
            setattr(self, "_network_lifecycle_state", state)
        state[role] = dict(state_after)

    def _network_lifecycle_preconditions(
        self,
        *,
        resolved: ResolvedPaths,
        role: str,
        action: str,
        state: dict[str, Any],
    ) -> list[dict[str, Any]]:
        config = dict(resolved.config_data or {})
        configured_role = configured_network_role(config)
        configured_role_valid = network_role_is_valid(configured_role)
        running = str(state.get("status") or "stopped") == "running"
        provider_available = self._network_lifecycle_provider_available(role, action)
        preconditions = [
            _precondition(
                f"NetworkRole_is_{role}",
                "pass" if configured_role == role and configured_role_valid else "blocked",
                f"configured NetworkRole={configured_role}; valid={'yes' if configured_role_valid else 'no'}; requested={role}",
                f"Save NetworkRole={role} before using {role} lifecycle controls.",
            ),
            _precondition(
                "lifecycle_provider_available",
                "pass" if provider_available else "blocked",
                f"{action}_network_{role} callable={provider_available}",
                (
                    "Restart the app/API to load backend lifecycle providers, then retry. "
                    "If this is a source checkout, verify NetworkLifecycleProviderMixin is mixed into the facade."
                ),
            ),
        ]
        if action == "start":
            preconditions.append(
                _precondition(
                    "duplicate_start_guard",
                    "blocked" if running else "pass",
                    f"current_lifecycle_status={state.get('status') or 'stopped'}",
                    "Stop the existing network lifecycle before starting it again.",
                )
            )
        else:
            preconditions.append(
                _precondition(
                    "duplicate_stop_guard",
                    "pass",
                    f"current_lifecycle_status={state.get('status') or 'stopped'}",
                    "Stop is idempotent; if already stopped, this command leaves lifecycle state stopped.",
                )
            )
        block_message = ""
        if action == "start":
            try:
                block_message = self._active_work_block_message(resolved, f"Network {role} start")
            except Exception as exc:
                block_message = f"Active-work guard could not be verified: {_bounded_evidence(exc)}"
            preconditions.append(
                _precondition(
                    "backend_close_readiness_safe",
                    "blocked" if block_message else "pass",
                    block_message or "No active work block is currently reported.",
                    "Stop or finish active standalone pipeline/audit/rerun work before starting network lifecycle.",
                )
            )
        if role == "coordinator":
            port = _safe_int(config.get("CoordinatorPort", 7830), 7830)
            bind_address = str(config.get("CoordinatorBindAddress") or "0.0.0.0").strip()
            heartbeat_mins = _safe_int(config.get("CoordinatorHeartbeatTimeoutMins", 5), 5)
            preconditions.extend(
                [
                    _precondition(
                        "bind_address_and_port_valid",
                        "pass" if bind_address and 1 <= port <= 65535 else "blocked",
                        f"bind_address={bind_address or '(empty)'}; port={port}",
                        "Set a non-empty CoordinatorBindAddress and a CoordinatorPort in 1..65535.",
                    ),
                    _precondition(
                        "heartbeat_timeout_valid",
                        "pass" if heartbeat_mins > 0 else "blocked",
                        f"CoordinatorHeartbeatTimeoutMins={heartbeat_mins}",
                        "Set CoordinatorHeartbeatTimeoutMins to a positive value.",
                    ),
                    _precondition(
                        "coordinator_auth_token_posture",
                        "review",
                        f"CoordinatorAuthToken={_redacted_token_state(config.get('CoordinatorAuthToken'), allow_generate=True)}",
                        "Leave blank only when the backend lifecycle provider can generate and persist a shared token.",
                    ),
                ]
            )
        if role == "worker":
            coordinator_url_issue = _worker_coordinator_url_issue(config.get("WorkerCoordinatorUrl"))
            coordinator_url = _redact_url(config.get("WorkerCoordinatorUrl"))
            worker_name = str(config.get("WorkerName") or "").strip()
            path_map = str(config.get("WorkerSourcePathMap") or "").strip()
            pending_done = False
            pending_done_unknown = False
            pending_done_error = ""
            try:
                network_workers = self.get_network_workers(resolved).to_mapping()
                pending_done = bool((network_workers.get("worker_state") or {}).get("pending_done_report"))
            except Exception as exc:
                pending_done_unknown = True
                pending_done_error = _bounded_evidence(exc)
                pending_done = False
            preconditions.extend(
                [
                    _precondition(
                        "coordinator_url_present",
                        "pass" if not coordinator_url_issue else "blocked",
                        f"WorkerCoordinatorUrl={coordinator_url or '(empty)'}; validation={coordinator_url_issue or 'ok'}",
                        "Set WorkerCoordinatorUrl to the coordinator machine URL, for example http://coordinator-host:7830.",
                    ),
                    _precondition(
                        "worker_identity_present",
                        "pass" if worker_name else "review",
                        f"WorkerName={worker_name or '(hostname fallback)'}",
                        "Set WorkerName when you need stable worker-specific visibility on the coordinator.",
                    ),
                    _precondition(
                        "worker_auth_token_present",
                        "pass" if str(config.get("WorkerAuthToken") or "").strip() else "blocked",
                        f"WorkerAuthToken={_redacted_token_state(config.get('WorkerAuthToken'))}",
                        "Set WorkerAuthToken to match the coordinator token.",
                    ),
                    _precondition(
                        "source_path_map_configured",
                        "pass" if path_map else "review",
                        f"WorkerSourcePathMap entries={'present' if path_map else 'none'}",
                        "Configure WorkerSourcePathMap when coordinator paths differ from this worker's reachable paths.",
                    ),
                    _precondition(
                        "pending_done_reports_delivered",
                        "blocked" if pending_done_unknown or (pending_done and action == "start") else "pass",
                        (
                            f"pending_done_report={'unknown' if pending_done_unknown else 'yes' if pending_done else 'no'}"
                            + (f"; read_error={pending_done_error}" if pending_done_error else "")
                        ),
                        "Deliver or review the pending done report before claiming new work.",
                    ),
                ]
            )
        return preconditions

    def _network_lifecycle_dry_run_data(
        self,
        *,
        resolved: ResolvedPaths,
        role: str,
        action: str,
        request: dict[str, Any],
    ) -> dict[str, Any]:
        config = dict(resolved.config_data or {})
        state = self._network_lifecycle_state_for(role)
        preconditions = self._network_lifecycle_preconditions(
            resolved=resolved,
            role=role,
            action=action,
            state=state,
        )
        blocked = [row for row in preconditions if row.get("status") == "blocked"]
        would_start = []
        would_stop = []
        if action == "start":
            would_start = [f"{role}_dispatcher"]
            if role == "coordinator":
                would_start.extend(["coordinator_http_server", "coordinator_stale_reaper"])
            if role == "worker":
                would_start.append("worker_polling_loop")
        else:
            would_stop = [f"{role}_dispatcher"]
            if role == "coordinator":
                would_stop.extend(["coordinator_http_server", "coordinator_stale_reaper"])
            if role == "worker":
                would_stop.append("worker_polling_loop")
        return {
            "schema_version": NETWORK_LIFECYCLE_DRY_RUN_SCHEMA_VERSION,
            "candidate_command": _lifecycle_command(role, action),
            "dry_run_only": True,
            "effect": NETWORK_LIFECYCLE_EFFECT_NONE,
            "role": role,
            "network_mode_label": pipeline_start_network_mode_label(
                configured_network_role(config),
                coordinator_also_encode_locally=coordinator_also_encode_locally_enabled(config),
            ),
            "requested_action": action,
            "lifecycle_state": state,
            "lifecycle_state_source": "session_memory_only",
            "precondition_results": preconditions,
            "would_start_processes": would_start,
            "would_stop_processes": would_stop,
            "dry_run_writes": [],
            "suppress_command_journal": True,
            "confirmed_route_would_write": [
                "command_journal_entry",
                "session_network_lifecycle_state",
            ],
            "state_file_posture": _state_file_posture(resolved, self.service),
            "would_not_touch": {
                "source_media": "no read/write/delete/rename/move",
                "scratch_media": "no create/delete/cleanup",
                "output_media": "no create/delete/overwrite/publish",
                "queue_manifests": "no enqueue/dequeue/reorder",
                "pending_publish": "no drain/repair/move/delete",
                "completed_manifest": "no acceptance ledger writes",
            },
            "active_work": {
                "reported_worker_count": 0,
                "pending_done_reports": any(
                    row.get("key") == "pending_done_reports_delivered" and row.get("status") == "blocked"
                    for row in preconditions
                ),
                "state_read_failed": any(
                    row.get("key") == "pending_done_reports_delivered" and "unknown" in str(row.get("evidence") or "")
                    for row in preconditions
                ),
            },
            "provider_available": self._network_lifecycle_provider_available(role, action),
            "redacted_config_evidence": {
                "CoordinatorBindAddress": str(config.get("CoordinatorBindAddress") or "0.0.0.0"),
                "CoordinatorPort": _safe_int(config.get("CoordinatorPort", 7830), 7830),
                "CoordinatorAlsoEncodeLocally": coordinator_also_encode_locally_enabled(config),
                "CoordinatorAuthToken": _redacted_token_state(config.get("CoordinatorAuthToken"), allow_generate=True),
                "WorkerCoordinatorUrl": _redact_url(config.get("WorkerCoordinatorUrl")),
                "WorkerName": str(config.get("WorkerName") or ""),
                "WorkerAuthToken": _redacted_token_state(config.get("WorkerAuthToken")),
                "WorkerSourcePathMap": "present" if str(config.get("WorkerSourcePathMap") or "").strip() else "none",
                "WorkerConfigOverrides": "disabled_by_backend_policy",
            },
            "safe_to_apply": not blocked,
            "operator_confirmation_scope": f"Confirm {role} {action} through backend Network/Workers lifecycle controls only.",
            "request_summary": {
                "confirm_start": request.get("confirm_start") is True,
                "confirm_stop": request.get("confirm_stop") is True,
                "reason_present": bool(str(request.get("reason") or "").strip()),
            },
        }

    def request_network_lifecycle(
        self,
        resolved: ResolvedPaths,
        *,
        role: str,
        action: str,
        dry_run: bool,
        request: dict[str, Any],
        journal_recorder: Callable[[dict[str, Any], dict[str, Any] | None], None] | None = None,
    ) -> CommandResult:
        normalized_role = normalize_network_role(role)
        normalized_action = str(action or "").strip().casefold()
        command = _lifecycle_command(normalized_role, normalized_action)
        if normalized_role not in {"coordinator", "worker"} or normalized_action not in {"start", "stop"}:
            return CommandResult(
                command=command,
                ok=False,
                severity="error",
                message="Unsupported network lifecycle command.",
                errors=["role must be coordinator or worker; action must be start or stop"],
                refresh_hint="network",
            )
        lock = getattr(self, "_network_lifecycle_lock", None)
        if lock is None:
            lock_context = _NullLock()
        else:
            lock_context = lock
        with lock_context:
            data = self._network_lifecycle_dry_run_data(
                resolved=resolved,
                role=normalized_role,
                action=normalized_action,
                request=request,
            )
            if dry_run:
                return CommandResult(
                    command=command,
                    ok=True,
                    severity="info" if data.get("safe_to_apply") else "warning",
                    message=(
                        f"{normalized_role} {normalized_action} dry-run complete; "
                        f"safe_to_apply={'yes' if data.get('safe_to_apply') else 'no'}."
                    ),
                    warnings=[] if data.get("safe_to_apply") else ["One or more lifecycle preconditions are blocked."],
                    refresh_hint="network",
                    data=data,
                )
            confirmation_key = "confirm_start" if normalized_action == "start" else "confirm_stop"
            if request.get(confirmation_key) is not True:
                result_data = {
                    **data,
                    "schema_version": NETWORK_LIFECYCLE_RESULT_SCHEMA_VERSION,
                    "dry_run_only": False,
                    "state_before": data.get("lifecycle_state") or {},
                    "state_after": data.get("lifecycle_state") or {},
                    "cleanup_result": "not_started_confirmation_missing",
                }
                return CommandResult(
                    command=command,
                    ok=False,
                    severity="error",
                    message=f"Network {normalized_role} {normalized_action} requires {confirmation_key}=true.",
                    errors=[f"{confirmation_key}=true is required."],
                    refresh_hint="network",
                    data=result_data,
                )
            blocked = [row for row in data.get("precondition_results", []) if row.get("status") == "blocked"]
            if blocked:
                result_data = {
                    **data,
                    "schema_version": NETWORK_LIFECYCLE_RESULT_SCHEMA_VERSION,
                    "dry_run_only": False,
                    "state_before": data.get("lifecycle_state") or {},
                    "state_after": data.get("lifecycle_state") or {},
                    "cleanup_result": "not_started_preconditions_blocked",
                }
                return CommandResult(
                    command=command,
                    ok=False,
                    severity="error",
                    message=f"Network {normalized_role} {normalized_action} blocked by backend preconditions.",
                    errors=[str(row.get("key") or "precondition_blocked") for row in blocked],
                    refresh_hint="network",
                    data=result_data,
                )
            provider = self._network_lifecycle_provider_method(normalized_role, normalized_action)
            if not callable(provider):
                result_data = {
                    **data,
                    "schema_version": NETWORK_LIFECYCLE_RESULT_SCHEMA_VERSION,
                    "dry_run_only": False,
                    "state_before": data.get("lifecycle_state") or {},
                    "state_after": data.get("lifecycle_state") or {},
                    "cleanup_result": "provider_unavailable",
                }
                return CommandResult(
                    command=command,
                    ok=False,
                    severity="error",
                    message=(
                        f"Network {normalized_role} {normalized_action} provider is not available; "
                        "no dispatcher was started or stopped."
                    ),
                    errors=[f"{normalized_action}_network_{normalized_role} provider unavailable"],
                    refresh_hint="network",
                    data=result_data,
                )
            if journal_recorder is None:
                result_data = {
                    **data,
                    "schema_version": NETWORK_LIFECYCLE_RESULT_SCHEMA_VERSION,
                    "dry_run_only": False,
                    "state_before": data.get("lifecycle_state") or {},
                    "state_after": data.get("lifecycle_state") or {},
                    "cleanup_result": "not_started_command_journal_unavailable",
                }
                return CommandResult(
                    command=command,
                    ok=False,
                    severity="error",
                    message="Network lifecycle provider was not called because strict command journal evidence is unavailable.",
                    errors=["strict command journal recorder unavailable"],
                    refresh_hint="network",
                    data=result_data,
                )
            command_id = uuid.uuid4().hex
            state_before = self._network_lifecycle_state_for(normalized_role)
            try:
                provider(resolved=resolved, request=request, command_id=command_id)
            except Exception as exc:
                safe_exc = _bounded_evidence(exc)
                result_data = {
                    **data,
                    "schema_version": NETWORK_LIFECYCLE_RESULT_SCHEMA_VERSION,
                    "dry_run_only": False,
                    "command_id": command_id,
                    "state_before": state_before,
                    "state_after": self._network_lifecycle_state_for(normalized_role),
                    "cleanup_result": "provider_exception",
                }
                return CommandResult(
                    command=command,
                    ok=False,
                    severity="error",
                    message=f"Network {normalized_role} {normalized_action} failed: {safe_exc}",
                    errors=[safe_exc],
                    refresh_hint="network",
                    data=result_data,
                )
            state_after = self._network_lifecycle_state_candidate(
                state_before,
                role=normalized_role,
                status="running" if normalized_action == "start" else "stopped",
                command_id=command_id,
                action=normalized_action,
            )
            result_data = {
                **data,
                "schema_version": NETWORK_LIFECYCLE_RESULT_SCHEMA_VERSION,
                "dry_run_only": False,
                "command_id": command_id,
                "state_before": state_before,
                "state_after": state_after,
                "cleanup_result": "ok",
            }
            result = CommandResult(
                command=command,
                ok=True,
                severity="info",
                message=f"Network {normalized_role} {normalized_action} completed.",
                refresh_hint="network",
                data=result_data,
            )
            try:
                journal_recorder(result.to_mapping(), request)
            except Exception as exc:
                cleanup_result = "command_journal_failed_state_not_committed"
                cleanup_errors: list[str] = []
                if normalized_action == "start":
                    cleanup_provider = self._network_lifecycle_provider_method(normalized_role, "stop")
                    if callable(cleanup_provider):
                        try:
                            cleanup_provider(
                                resolved=resolved,
                                request={
                                    "reason": "cleanup after network lifecycle command journal failure",
                                    "journal_failure_cleanup": True,
                                },
                                command_id=command_id,
                            )
                            cleanup_result = "command_journal_failed_provider_cleanup_ok"
                        except Exception as cleanup_exc:
                            cleanup_result = "command_journal_failed_provider_cleanup_failed"
                            cleanup_errors.append(f"provider cleanup failed: {_bounded_evidence(cleanup_exc)}")
                    else:
                        cleanup_result = "command_journal_failed_provider_cleanup_unavailable"
                elif normalized_action == "stop":
                    # The stop provider already tore the dispatcher down, so
                    # leaving the session state as "running" would be a phantom
                    # that blocks a later start via duplicate_start_guard. Commit
                    # the stopped state to keep session state truthful; the
                    # journal write still failed and is reported below.
                    self._network_lifecycle_state_commit(normalized_role, state_after)
                    cleanup_result = "command_journal_failed_stop_state_committed"
                failure_data = {
                    **result_data,
                    "state_after": self._network_lifecycle_state_for(normalized_role),
                    "cleanup_result": cleanup_result,
                }
                return CommandResult(
                    command=command,
                    ok=False,
                    severity="error",
                    message=f"Network {normalized_role} {normalized_action} failed after provider returned: command journal write failed.",
                    errors=[f"command journal write failed: {_bounded_evidence(exc)}", *cleanup_errors],
                    refresh_hint="network",
                    data=failure_data,
                )
            self._network_lifecycle_state_commit(normalized_role, state_after)
            result.data["strict_command_journal_recorded"] = True
            return result


class _NullLock:
    def __enter__(self) -> "_NullLock":
        return self

    def __exit__(self, *args: Any) -> None:
        return None


__all__ = [
    "NETWORK_LIFECYCLE_DRY_RUN_SCHEMA_VERSION",
    "NETWORK_LIFECYCLE_RESULT_SCHEMA_VERSION",
    "NetworkLifecycleFacadeMixin",
]
