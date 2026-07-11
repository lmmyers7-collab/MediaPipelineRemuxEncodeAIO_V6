"""Network runtime-state facade adapter."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, UTC
import hashlib
import ipaddress
import logging
from pathlib import Path
import re
import socket
from typing import TYPE_CHECKING, Any
from urllib.parse import urlsplit

from mediapipeline.core.config.library_profiles import effective_library_profiles_from_config
from mediapipeline.core.kernel.config_keys import (
    KEY_WORKER_ENCODER_MAP,
    KEY_WORKER_HONOR_COORDINATOR_POLICY,
)
from mediapipeline.core.kernel.dto_commands import CommandResult
from mediapipeline.core.network.join import (
    NETWORK_JOIN_BLOB_RESULT_SCHEMA_VERSION,
    NETWORK_JOIN_IMPORT_RESULT_SCHEMA_VERSION,
    encode_network_join_blob,
    worker_join_patch_from_blob,
)
from mediapipeline.core.network.auth import generate_token
from mediapipeline.core.network.library_roots import library_roots_from_config
from mediapipeline.core.network.path_map import parse_source_path_map
from mediapipeline.core.network.registry import InFlightRegistry
from mediapipeline.core.network.url_policy import redact_network_secret_text, redact_url
from mediapipeline.core.network.url_policy import validate_coordinator_url
from mediapipeline.core.network.worker_state import load_worker_state
from mediapipeline.core.processes.pipeline_policy import configured_network_role
from mediapipeline.core.paths.contracts import ResolvedPaths

if TYPE_CHECKING:
    from mediapipeline.core.kernel.dto_workspaces import NetworkWorkersDto


from mediapipeline.core.network.facade_contract import (
    NETWORK_COORDINATOR_DISCOVERY_SCHEMA_VERSION,
    NETWORK_TEST_CONNECTION_SCHEMA_VERSION,
    NetworkDiscoveryUnavailable,
)
from mediapipeline.core.network.facade_connectivity import *  # noqa: F403
from mediapipeline.core.network.facade_policy import *  # noqa: F403
from mediapipeline.core.network.facade_diagnostics import *  # noqa: F403

class NetworkFacadeMixin:
    """Read-only network runtime-state adapter for local WebView/Tauri shells."""

    service: object
    app_version: str

    def _network_probe_worker_auth_adapter(self, base_url: str, token: str, *, timeout_seconds: int = 4) -> Any:
        probe = getattr(self, "_network_probe_worker_auth", None)
        if not callable(probe):
            raise RuntimeError("Network worker auth probe adapter is unavailable.")
        return probe(base_url, token, timeout_seconds=timeout_seconds)

    def _network_discover_coordinators_adapter(self, *, timeout_seconds: float) -> list[str]:
        discover = getattr(self, "_network_discover_coordinators", None)
        if not callable(discover):
            raise NetworkDiscoveryUnavailable("mDNS coordinator discovery adapter is unavailable.")
        return list(discover(timeout_secs=timeout_seconds) or [])

    def _network_dispatcher_for_role(self, role: str) -> Any:
        runtime = getattr(self, "_network_dispatcher_runtime", None)
        if not isinstance(runtime, dict):
            return None
        entry = runtime.get(role)
        if not isinstance(entry, dict):
            return None
        return entry.get("dispatcher")

    def _load_coordinator_app_state_token(self) -> str:
        loader = getattr(self.service, "load_app_state", None)
        if not callable(loader):
            return ""
        try:
            state = loader()
        except Exception:
            return ""
        if not isinstance(state, dict):
            return ""
        return str(state.get("coordinator_auth_token", "") or "").strip()

    def _save_coordinator_app_state_token(self, token: str) -> tuple[bool, str]:
        saver = getattr(self.service, "save_app_state", None)
        if not callable(saver):
            return False, "save_app_state is unavailable; coordinator token was not persisted."
        try:
            saver({"coordinator_auth_token": token})
        except Exception as exc:
            return False, f"coordinator token app-state save failed: {redact_network_secret_text(exc)}"
        return True, ""

    def _coordinator_join_token(
        self,
        resolved: ResolvedPaths,
        *,
        rotate: bool,
    ) -> tuple[str, str, list[str], dict[str, Any]]:
        warnings: list[str] = []
        write_evidence: dict[str, Any] = {
            "writes_config": False,
            "writes_app_state": False,
            "running_coordinator_updated": False,
        }
        dispatcher = self._network_dispatcher_for_role("coordinator")
        config_token = str((resolved.config_data or {}).get("CoordinatorAuthToken", "") or "").strip()
        getter = getattr(dispatcher, "get_auth_token", None)
        running_token = str(getter() or "").strip() if callable(getter) else ""

        if rotate:
            token = generate_token()
            if config_token:
                save_request = self.settings_patch_request_with_review_confirmation(
                    resolved,
                    {"changes": {"CoordinatorAuthToken": token}},
                )
                save_result = self.save_settings_patch(
                    resolved,
                    {**save_request, "confirm_save": True},
                )
                if not save_result.ok:
                    safe_errors = [
                        redact_network_secret_text(error)
                        for error in list(save_result.errors or [])
                    ]
                    detail = "; ".join(safe_errors) if safe_errors else save_result.message
                    raise RuntimeError(f"CoordinatorAuthToken rotation save failed: {detail}")
                write_evidence["writes_config"] = True

            updater = getattr(dispatcher, "update_auth_token", None)
            if callable(updater):
                try:
                    updater(token)
                except Exception as exc:
                    rollback_errors: list[str] = []
                    if write_evidence["writes_config"] and config_token:
                        rollback_request = self.settings_patch_request_with_review_confirmation(
                            resolved,
                            {"changes": {"CoordinatorAuthToken": config_token}},
                        )
                        rollback_result = self.save_settings_patch(
                            resolved,
                            {**rollback_request, "confirm_save": True},
                        )
                        if not rollback_result.ok:
                            rollback_errors.append("config token rollback failed")
                    if running_token:
                        try:
                            updater(running_token)
                        except Exception:
                            rollback_errors.append("running coordinator token rollback failed")
                    rollback_detail = "; ".join(rollback_errors) if rollback_errors else "previous token restored"
                    raise RuntimeError(
                        f"running coordinator token update failed; {rollback_detail}: {redact_network_secret_text(exc)}"
                    ) from exc
                write_evidence["running_coordinator_updated"] = True
                write_evidence["writes_app_state"] = True
                return token, "rotated_running_coordinator", warnings, write_evidence

            if not config_token:
                saved, message = self._save_coordinator_app_state_token(token)
                if not saved:
                    raise RuntimeError(message)
                write_evidence["writes_app_state"] = True
                return token, "rotated_app_state", warnings, write_evidence

            return token, "rotated_config", warnings, write_evidence

        if callable(getter):
            token = running_token
            if token:
                return token, "running_coordinator", warnings, write_evidence
        if config_token:
            return config_token, "CoordinatorAuthToken", warnings, write_evidence
        app_state_token = self._load_coordinator_app_state_token()
        if app_state_token:
            return app_state_token, "app_state", warnings, write_evidence

        token = generate_token()
        saved, message = self._save_coordinator_app_state_token(token)
        if not saved:
            raise RuntimeError(message)
        write_evidence["writes_app_state"] = True
        return token, "generated_app_state", warnings, write_evidence

    def request_network_coordinator_join_blob(
        self,
        resolved: ResolvedPaths,
        request: dict[str, Any] | None = None,
    ) -> CommandResult:
        request = dict(request or {})
        data_base = {
            "schema_version": NETWORK_JOIN_BLOB_RESULT_SCHEMA_VERSION,
            "effect": "secret-transfer",
            "suppress_command_journal": True,
            "read_only_media": True,
            "would_not_touch": {
                "source_media": "no write/delete/rename/move",
                "scratch_media": "no create/delete/cleanup",
                "output_media": "no create/delete/overwrite/publish",
                "queue_state": "no claim, enqueue, dequeue, reorder, or launch",
                "pending_publish": "no drain/repair/move/delete",
                "lifecycle_state": "no coordinator or worker start/stop",
            },
        }
        if request.get("confirm_create") is not True:
            return CommandResult(
                command="network.coordinator.join_blob",
                ok=False,
                severity="warning",
                message="Network coordinator join blob creation requires confirm_create=true.",
                warnings=["confirm_create must be true because the response contains a worker auth secret."],
                refresh_hint="network",
                data={**data_base, "join_blob": ""},
            )

        role = _network_role(resolved)
        coordinator_url = str(request.get("coordinator_url") or "").strip()
        connectivity = _coordinator_connectivity(resolved, "coordinator")
        if not coordinator_url:
            coordinator_url = str(connectivity.get("worker_coordinator_url") or "").strip()
        rotate = request.get("rotate_token") is True
        if rotate and request.get("confirm_rotate") is not True:
            return CommandResult(
                command="network.coordinator.join_blob",
                ok=False,
                severity="warning",
                message="Network coordinator token rotation requires confirm_rotate=true.",
                warnings=["confirm_rotate must be true when rotate_token is true."],
                refresh_hint="network",
                data={**data_base, "join_blob": "", "coordinator_url": redact_url(coordinator_url)},
            )

        try:
            libraries = library_roots_from_config(resolved.config_data or {})
            created_at_utc = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
            # Validate every non-secret blob field before a requested rotation can
            # mutate config, app state, or a running coordinator token.
            encode_network_join_blob(
                coordinator_url=coordinator_url,
                token="preflight-token-0123456789",
                libraries=libraries,
                created_at_utc=created_at_utc,
            )
            token, token_source, warnings, write_evidence = self._coordinator_join_token(
                resolved,
                rotate=rotate,
            )
            blob, payload = encode_network_join_blob(
                coordinator_url=coordinator_url,
                token=token,
                libraries=libraries,
                created_at_utc=created_at_utc,
            )
        except Exception as exc:
            return CommandResult(
                command="network.coordinator.join_blob",
                ok=False,
                severity="error",
                message="Network coordinator join blob could not be created.",
                errors=[redact_network_secret_text(exc)],
                refresh_hint="network",
                data={
                    **data_base,
                    "join_blob": "",
                    "coordinator_url": redact_url(coordinator_url),
                    "role": role,
                },
            )

        libraries = list(payload.get("libraries", []))
        return CommandResult(
            command="network.coordinator.join_blob",
            ok=True,
            severity="info",
            message="Network coordinator join blob created. Treat it as a secret.",
            warnings=warnings,
            refresh_hint="network",
            data={
                **data_base,
                **write_evidence,
                "join_blob": blob,
                "role": role,
                "coordinator_url": redact_url(coordinator_url),
                "token_fingerprint": _fingerprint_text(token),
                "token_source": token_source,
                "rotated": rotate,
                "library_count": len(libraries),
                "libraries": libraries,
                "candidate_urls": connectivity.get("candidate_urls", []),
                "secret_handling": "join_blob contains the worker auth token; do not paste it into logs or support notes.",
            },
        )

    def request_network_worker_join_cluster(
        self,
        resolved: ResolvedPaths,
        request: dict[str, Any] | None = None,
    ) -> CommandResult:
        request = dict(request or {})
        data_base = {
            "schema_version": NETWORK_JOIN_IMPORT_RESULT_SCHEMA_VERSION,
            "effect": "config-write",
            "suppress_command_journal": True,
            "would_not_touch": {
                "source_media": "no write/delete/rename/move",
                "scratch_media": "no create/delete/cleanup",
                "output_media": "stat/readability checks only during test; no create/delete/overwrite/publish",
                "queue_state": "no claim, enqueue, dequeue, reorder, or launch",
                "pending_publish": "no drain/repair/move/delete",
                "lifecycle_state": "no coordinator or worker start/stop",
                "media_policy": "no FFmpeg, subtitle, audio, remux, encode, publish, or cleanup policy changed",
            },
        }
        if request.get("confirm_import") is not True:
            return CommandResult(
                command="network.worker.join_cluster",
                ok=False,
                severity="warning",
                message="Network worker join import requires confirm_import=true.",
                warnings=["confirm_import must be true because this saves worker network settings."],
                refresh_hint="network",
                data=data_base,
            )

        try:
            payload, desired_changes, plan = worker_join_patch_from_blob(
                request.get("join_blob"),
                resolved.config_data or {},
            )
        except Exception as exc:
            return CommandResult(
                command="network.worker.join_cluster",
                ok=False,
                severity="error",
                message="Network worker join blob could not be imported.",
                errors=[redact_network_secret_text(exc)],
                refresh_hint="network",
                data=data_base,
            )

        current_config = dict(resolved.config_data or {})
        changes_to_save = {
            key: value
            for key, value in desired_changes.items()
            if str(current_config.get(key, "") or "") != str(value or "")
        }
        settings_save: dict[str, Any]
        hot_apply: list[dict[str, Any]] = []
        warnings: list[str] = []
        if changes_to_save:
            save_request = self.settings_patch_request_with_review_confirmation(
                resolved,
                {"changes": changes_to_save},
            )
            save_result = self.save_settings_patch(
                resolved,
                {**save_request, "confirm_save": True},
            )
            warnings.extend(redact_network_secret_text(item) for item in list(save_result.warnings or []))
            if not save_result.ok:
                return CommandResult(
                    command="network.worker.join_cluster",
                    ok=False,
                    severity=save_result.severity or "error",
                    message="Network worker join import was blocked by settings save validation.",
                    errors=[redact_network_secret_text(item) for item in list(save_result.errors or [])],
                    warnings=warnings,
                    refresh_hint="network",
                    data={
                        **data_base,
                        "coordinator_url": redact_url(payload["coordinator_url"]),
                        "token_fingerprint": _fingerprint_text(payload["token"]),
                        "join_plan": plan,
                        "settings_save": {
                            "ok": False,
                            "message": redact_network_secret_text(save_result.message),
                            "changed_keys": sorted(changes_to_save),
                        },
                    },
                )
            hot_apply = list(save_result.data.get("network_worker_hot_apply", []) or [])
            settings_save = {
                "ok": True,
                "status": "saved",
                "message": save_result.message,
                "changed_keys": list(save_result.data.get("changed_keys", sorted(changes_to_save))),
            }
        else:
            settings_save = {
                "ok": True,
                "status": "already_current",
                "message": "Worker network settings already matched the join blob.",
                "changed_keys": [],
            }

        test_config = dict(current_config)
        test_config.update(desired_changes)
        test_resolved = replace(resolved, config_data=test_config)
        test_request: dict[str, Any] = {}
        if "timeout_seconds" in request:
            test_request["timeout_seconds"] = request.get("timeout_seconds")
        test_result = self.request_network_test_connection(test_resolved, test_request)
        warnings.extend(redact_network_secret_text(item) for item in list(test_result.warnings or []))

        ok = bool(test_result.ok)
        message = (
            "Network worker joined the cluster and test-connection passed."
            if ok
            else "Network worker settings were imported, but test-connection found blockers."
        )
        return CommandResult(
            command="network.worker.join_cluster",
            ok=ok,
            severity="info" if ok else test_result.severity,
            message=message,
            errors=[redact_network_secret_text(item) for item in list(test_result.errors or [])],
            warnings=warnings,
            refresh_hint="network",
            data={
                **data_base,
                "coordinator_url": redact_url(payload["coordinator_url"]),
                "token_fingerprint": _fingerprint_text(payload["token"]),
                "library_count": int(payload["library_count"]),
                "join_plan": plan,
                "settings_save": settings_save,
                "network_worker_hot_apply": hot_apply,
                "test_connection": test_result.to_mapping(),
            },
        )

    def request_network_worker_discover_coordinators(
        self,
        resolved: ResolvedPaths,
        request: dict[str, Any] | None = None,
    ) -> CommandResult:
        request = dict(request or {})
        timeout_seconds = _network_discovery_timeout(request)
        data_base = {
            "schema_version": NETWORK_COORDINATOR_DISCOVERY_SCHEMA_VERSION,
            "read_only": True,
            "effect": "none",
            "suppress_command_journal": True,
            "timeout_seconds": timeout_seconds,
            "zeroconf_available": True,
            "coordinators": [],
            "count": 0,
            "would_not_touch": {
                "source_media": "no write/delete/rename/move",
                "scratch_media": "no create/delete/cleanup",
                "output_media": "no create/delete/overwrite/publish",
                "queue_state": "no claim, enqueue, dequeue, reorder, or launch",
                "pending_publish": "no drain/repair/move/delete",
                "lifecycle_state": "no coordinator or worker start/stop",
                "settings": "discovery does not save WorkerCoordinatorUrl; selection only fills the UI",
                "media_policy": "no FFmpeg, subtitle, audio, remux, encode, publish, or cleanup policy changed",
            },
        }
        try:
            discovered_urls = self._network_discover_coordinators_adapter(timeout_seconds=timeout_seconds)
        except NetworkDiscoveryUnavailable as exc:
            warning = _bounded_network_detail(exc)
            return CommandResult(
                command="network.worker.discover_coordinators",
                ok=False,
                severity="warning",
                message="mDNS coordinator discovery is unavailable because zeroconf is not installed.",
                warnings=[warning],
                refresh_hint="network",
                data={
                    **data_base,
                    "zeroconf_available": False,
                    "summary_lines": [
                        "mDNS coordinator discovery unavailable.",
                        warning,
                        "Manual WorkerCoordinatorUrl entry and coordinator join blobs remain available.",
                    ],
                },
            )
        except Exception as exc:
            return CommandResult(
                command="network.worker.discover_coordinators",
                ok=False,
                severity="error",
                message="mDNS coordinator discovery failed.",
                errors=[_bounded_network_detail(exc)],
                refresh_hint="network",
                data={
                    **data_base,
                    "summary_lines": [
                        "mDNS coordinator discovery failed before returning coordinator rows.",
                        "Manual WorkerCoordinatorUrl entry and coordinator join blobs remain available.",
                    ],
                },
            )

        coordinators: list[dict[str, Any]] = []
        warnings: list[str] = []
        seen_urls: set[str] = set()
        for raw_url in discovered_urls:
            row, warning = _coordinator_discovery_row(raw_url)
            if warning:
                warnings.append(warning)
            if row is None:
                continue
            url_key = str(row.get("url") or "").casefold()
            if url_key in seen_urls:
                continue
            seen_urls.add(url_key)
            coordinators.append(row)

        count = len(coordinators)
        summary_lines = [
            f"mDNS coordinator discovery returned {count} selectable coordinator(s).",
            "Effect: none.",
            "No files, queue, scratch, output, pending publish, lifecycle state, settings, or media policy were changed.",
        ]
        if not count:
            summary_lines.append("No coordinators were discovered; verify the coordinator is running on the LAN and that firewall/mDNS traffic is allowed.")
        return CommandResult(
            command="network.worker.discover_coordinators",
            ok=True,
            severity="info" if count else "warning",
            message=(
                "mDNS coordinator discovery completed."
                if count
                else "mDNS coordinator discovery completed with no coordinators found."
            ),
            warnings=warnings,
            refresh_hint="network",
            data={
                **data_base,
                "coordinators": coordinators,
                "count": count,
                "summary_lines": summary_lines,
            },
        )

    def request_network_test_connection(self, resolved: ResolvedPaths, request: dict[str, Any] | None = None) -> CommandResult:
        request = dict(request or {})
        config = dict(resolved.config_data or {})
        timeout_seconds = _network_test_timeout(request)
        l1_tcp = _network_tcp_probe(config.get("WorkerCoordinatorUrl"), timeout_seconds=timeout_seconds)
        l2_auth = _network_auth_ping_probe(
            config.get("WorkerCoordinatorUrl"),
            config.get("WorkerAuthToken"),
            timeout_seconds=timeout_seconds,
            probe_worker_auth_func=self._network_probe_worker_auth_adapter,
        )
        l3_paths = _network_path_access_probe(resolved)
        layers = {
            "l1_tcp": l1_tcp,
            "l2_auth": l2_auth,
            "l3_paths": l3_paths,
        }
        failed_layers = [
            layer
            for layer in layers.values()
            if not layer.get("ok")
        ]
        ok = not failed_layers
        transport_blocked = not l1_tcp.get("ok") or not l2_auth.get("ok")
        severity = "info" if ok else "error" if transport_blocked else "warning"
        message = (
            "Network worker test-connection passed."
            if ok
            else "Network worker test-connection found one or more blocked layers."
        )
        errors = [f"{layer.get('label')}: {layer.get('detail')}" for layer in failed_layers]
        warnings = [
            str(warning)
            for warning in l3_paths.get("warnings", [])
            if str(warning or "").strip()
        ]
        data = {
            "schema_version": NETWORK_TEST_CONNECTION_SCHEMA_VERSION,
            "read_only": True,
            "effect": "none",
            "dry_run_writes": [],
            "suppress_command_journal": True,
            "timeout_seconds": timeout_seconds,
            "overall_status": "pass" if ok else "fail",
            "coordinator_url": redact_url(config.get("WorkerCoordinatorUrl")),
            "layers": layers,
            "summary_lines": [
                f"L1 TCP reachability: {l1_tcp.get('status')}",
                f"L2 signed auth ping: {l2_auth.get('status')}",
                f"L3 worker path access: {l3_paths.get('status')}",
                "No files, queue, scratch, output, pending publish, lifecycle state, or media policy were changed.",
            ],
            "would_not_touch": {
                "source_media": "no write/delete/rename/move",
                "scratch_media": "no create/delete/cleanup",
                "output_media": "stat/readability checks only; no create/delete/overwrite/publish",
                "queue_state": "no claim, enqueue, dequeue, reorder, or launch",
                "pending_publish": "no drain/repair/move/delete",
                "lifecycle_state": "no coordinator or worker start/stop",
                "secrets": "auth token used only for signed ping; token value is not returned",
            },
        }
        return CommandResult(
            command="network.worker.test_connection",
            ok=ok,
            message=message,
            severity=severity,
            errors=errors,
            warnings=warnings,
            refresh_hint="network",
            data=data,
        )

    def get_network_workers(self, resolved: ResolvedPaths) -> NetworkWorkersDto:
        role = _network_role(resolved)
        mode = _visible_network_mode(resolved)
        state_dir = _runtime_state_dir(resolved, self.service)
        inflight_path = state_dir / "coordinator_inflight.json"
        worker_state_path = state_dir / "worker_state.json"
        cluster_log_path = state_dir / "cluster.log"
        warnings: list[str] = []
        rows: list[dict[str, Any]] = []
        coordinator_state_error = ""
        session_completed = 0
        session_failed = 0
        active_count = 0
        idle_count = 0

        if inflight_path.exists():
            registry = InFlightRegistry()
            if registry.load(inflight_path):
                active_entries = registry.snapshot()
                idle_entries = registry.idle_workers_snapshot()
                rows.extend(_worker_row(entry, source="coordinator_inflight") for entry in active_entries)
                rows.extend(_worker_row(entry, source="coordinator_inflight_stats") for entry in idle_entries)
                active_count = len(active_entries)
                idle_count = len(idle_entries)
                session_completed = int(registry.session_completed)
                session_failed = int(registry.session_failed)
                if active_entries:
                    warnings.append("Coordinator worker rows come from persisted in-flight state; heartbeat progress may lag the live dispatcher.")
            else:
                coordinator_state_error = "Coordinator in-flight state could not be read; inspect or regenerate coordinator_inflight.json before trusting worker rows."
                warnings.append(coordinator_state_error)
        elif role == "coordinator":
            warnings.append("No coordinator in-flight state file exists yet.")

        worker_state = _safe_worker_state(worker_state_path, warnings)
        if worker_state.get("pending_done_report"):
            warnings.append("Worker state contains a pending done report; the coordinator may not have accepted the last completion yet.")
        if role == "coordinator" and not rows:
            warnings.append("Coordinator worker board is empty from persisted state; confirm workers are polling the displayed Worker Coordinator URL.")

        state_files = [
            _state_file_row(
                "coordinator_inflight",
                "Coordinator in-flight registry",
                inflight_path,
                "Tracks active and idle worker rows persisted by the coordinator dispatcher.",
            ),
            _state_file_row(
                "worker_state",
                "Local worker state",
                worker_state_path,
                "Tracks the current local worker claim and any pending done report.",
            ),
            _state_file_row(
                "cluster_log",
                "Cluster log",
                cluster_log_path,
                "Records coordinator/worker network lifecycle and claim events.",
            ),
        ]
        if coordinator_state_error:
            for item in state_files:
                if item.get("key") == "coordinator_inflight":
                    item["status"] = "unreadable"
                    item["error"] = coordinator_state_error
                    break
        if worker_state.get("read_failed"):
            for item in state_files:
                if item.get("key") == "worker_state":
                    item["status"] = "unreadable"
                    item["error"] = str(worker_state.get("read_error") or "worker_state.json could not be read")
                    break
        unreadable = [item for item in state_files if item.get("status") == "unreadable"]
        for item in unreadable:
            warnings.append(f"{item.get('label') or item.get('key')} could not be inspected: {item.get('error')}")
        coordinator_connectivity = _coordinator_connectivity(resolved, role)
        warnings.extend(str(warning) for warning in coordinator_connectivity.get("warnings", []) if str(warning).strip())
        running_vs_saved = _worker_running_vs_saved(self, resolved)
        if running_vs_saved.get("status") == "drift":
            labels = ", ".join(str(label) for label in running_vs_saved.get("drift_field_labels", []) if str(label))
            warnings.append(
                "Worker running settings differ from saved config"
                + (f": {labels}" if labels else ".")
            )
        token_posture = _token_posture(resolved)
        heartbeat_timeout_seconds = _heartbeat_timeout_seconds(resolved)
        lifecycle_state = _lifecycle_state(self)
        if _worker_state_stale_against_lifecycle(
            mode=mode,
            lifecycle_state=lifecycle_state,
            worker_state=worker_state,
        ):
            warnings.append(
                "Worker state contains an active claim while lifecycle memory is stopped; treat worker_state.json as stale claim evidence before trusting runtime status."
            )
        diagnostic_layers = _network_diagnostic_layers(
            resolved=resolved,
            role=role,
            rows=rows,
            worker_state=worker_state,
            state_files=state_files,
            coordinator_connectivity=coordinator_connectivity,
            token_posture=token_posture,
            heartbeat_timeout_seconds=heartbeat_timeout_seconds,
        )
        worker_progress = _network_worker_progress(
            role=role,
            rows=rows,
            worker_state=worker_state,
            warnings=warnings,
            heartbeat_timeout_seconds=heartbeat_timeout_seconds,
        )
        runtime_status_label, runtime_status_severity = _runtime_status_from_lifecycle(
            mode=mode,
            lifecycle_state=lifecycle_state,
            worker_state=worker_state,
            state_files=state_files,
            warnings=warnings,
        )
        if running_vs_saved.get("status") == "drift" and runtime_status_severity == "match":
            runtime_status_severity = "warning"
            if runtime_status_label == "Running":
                runtime_status_label = "Running with drift"
        operator_summary_lines = _operator_summary_lines(
            resolved=resolved,
            mode=mode,
            runtime_status_label=runtime_status_label,
            runtime_status_severity=runtime_status_severity,
            lifecycle_state=lifecycle_state,
            coordinator_connectivity=coordinator_connectivity,
            worker_state=worker_state,
            active_count=active_count,
            idle_count=idle_count,
            warnings=warnings,
            token_posture=token_posture,
            running_vs_saved=running_vs_saved,
        )
        return _network_workers_dto(
            app_version=self.app_version,
            role=role,
            source="runtime_state_files",
            coordinator_inflight_path=str(inflight_path),
            worker_state_path=str(worker_state_path),
            cluster_log_path=str(cluster_log_path),
            state_files=state_files,
            rows=rows,
            active_count=active_count,
            idle_count=idle_count,
            total_count=len(rows),
            session_completed=session_completed,
            session_failed=session_failed,
            worker_state=worker_state,
            coordinator_connectivity=coordinator_connectivity,
            worker_progress=worker_progress,
            progress_bars=list(worker_progress.get("progress_bars") or []),
            lifecycle_state=lifecycle_state,
            runtime_status_label=runtime_status_label,
            runtime_status_severity=runtime_status_severity,
            operator_summary_lines=operator_summary_lines,
            token_posture=token_posture,
            running_vs_saved=running_vs_saved,
            diagnostic_layers=diagnostic_layers,
            warnings=warnings,
        )

__all__ = [
    "NetworkFacadeMixin",
]
